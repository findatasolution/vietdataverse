"""
VNIndex Daily Price Crawler
Source: vnstock3 (VCI) — works from any IP
Table: vn_macro_vnindex_daily
Schedule: Daily 17:15 VN (10:15 UTC) Mon-Fri after HSX close
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"VNIndex Crawler — {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    sys.exit("CRAWLING_BOT_DB env var not set")
engine = create_engine(CRAWLING_BOT_DB)


def ensure_table():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_macro_vnindex_daily (
                id         SERIAL PRIMARY KEY,
                date       DATE      NOT NULL,
                open       FLOAT,
                high       FLOAT,
                low        FLOAT,
                close      FLOAT,
                volume     BIGINT,
                crawl_time TIMESTAMP NOT NULL,
                source     TEXT      NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (date)
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_vn_macro_vnindex_daily_date ON vn_macro_vnindex_daily (date)"
        ))
    print("Table vn_macro_vnindex_daily ready.")


def fetch_vnindex(start_date: str, end_date: str) -> list:
    # Layer 1: vnstock 3.5+ (KBS)
    try:
        from vnstock import Vnstock
        df = Vnstock().stock(symbol='VNINDEX', source='VCI').quote.history(
            start=start_date, end=end_date, interval='1D'
        )
        if df is not None and not df.empty:
            print(f"  vnstock VCI: {len(df)} rows")
            return _parse(df)
    except Exception as e:
        print(f"  vnstock VCI error: {e}")

    # Layer 2: vnstock3
    try:
        from vnstock3 import Vnstock as Vnstock3
        df = Vnstock3().stock(symbol='VNINDEX', source='VCI').quote.history(
            start=start_date, end=end_date, interval='1D'
        )
        if df is not None and not df.empty:
            print(f"  vnstock3 VCI: {len(df)} rows")
            return _parse(df)
    except Exception as e:
        print(f"  vnstock3 VCI error: {e}")

    return []


def _parse(df) -> list:
    records = []
    for _, row in df.iterrows():
        d = str(row.get('time', row.name))[:10]
        records.append({
            'date':   d,
            'open':   float(row['open'])   if row.get('open')   is not None else None,
            'high':   float(row['high'])   if row.get('high')   is not None else None,
            'low':    float(row['low'])    if row.get('low')    is not None else None,
            'close':  float(row['close'])  if row.get('close')  is not None else None,
            'volume': int(row['volume'])   if row.get('volume') is not None else None,
        })
    return records


def upsert(records: list, crawl_time: datetime):
    if not records:
        return 0
    with engine.begin() as conn:
        for r in records:
            conn.execute(text("""
                INSERT INTO vn_macro_vnindex_daily
                    (date, open, high, low, close, volume, crawl_time, source, group_name)
                VALUES
                    (:date, :open, :high, :low, :close, :volume, :crawl_time, 'vnstock3', 'stock')
                ON CONFLICT (date) DO UPDATE SET
                    open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                    close=EXCLUDED.close, volume=EXCLUDED.volume,
                    crawl_time=EXCLUDED.crawl_time, source=EXCLUDED.source
            """), {**r, 'crawl_time': crawl_time})
    return len(records)


def main():
    ensure_table()
    end_date   = date_str
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    print(f"\nFetching VNINDEX {start_date} → {end_date}")

    records = fetch_vnindex(start_date, end_date)
    if not records:
        print("No data returned — check vnstock source.")
        sys.exit(1)

    n = upsert(records, datetime.now())
    last = records[-1]
    print(f"Upserted {n} rows. Latest: date={last['date']} close={last['close']}")
    print(f"\nDone at {datetime.now().strftime('%H:%M:%S')}")


if __name__ == '__main__':
    main()
