"""
VN30 Daily Stock Price (OHLCV) Crawler
Source: vnstock3 (SSI/TCBS data)
Schedule: Daily 17:15 VN (10:15 AM UTC) — after HSX close
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

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"VN30 OHLCV Crawler — {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

CRAWLING_CORP_DB = os.getenv('CRAWLING_CORP_DB')
if not CRAWLING_CORP_DB:
    raise ValueError("CRAWLING_CORP_DB environment variable not set")
engine = create_engine(CRAWLING_CORP_DB)

VN30_TICKERS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR',
    'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'NVL', 'PDR', 'PLX',
    'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VPB'
]


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_ohlcv_daily (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                date DATE NOT NULL,
                open FLOAT,
                high FLOAT,
                low FLOAT,
                close FLOAT,
                volume FLOAT,
                value FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (ticker, date)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vn30_ohlcv_daily_ticker_date
            ON vn30_ohlcv_daily (ticker, date)
        """))
        for col, definition in [
            ('source',     "TEXT NOT NULL DEFAULT 'vnstock3'"),
            ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'stock'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn30_ohlcv_daily ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.commit()
    print("Table vn30_ohlcv_daily ready.")


def fetch_ohlcv_vnstock(ticker: str, start_date: str, end_date: str) -> list:
    """Fetch OHLCV — tries vnstock (KBS) → vnstock3 (VCI) → legacy vnstock."""
    def _parse_rows(df, ticker, has_value=False):
        records = []
        for _, row in df.iterrows():
            records.append({
                'ticker': ticker,
                'date':   str(row.get('time', row.name))[:10],
                'open':   float(row['open'])   if row.get('open')   else None,
                'high':   float(row['high'])   if row.get('high')   else None,
                'low':    float(row['low'])    if row.get('low')    else None,
                'close':  float(row['close'])  if row.get('close')  else None,
                'volume': float(row['volume']) if row.get('volume') else None,
                'value':  float(row['value'])  if has_value and row.get('value') else None,
            })
        return records

    # --- Layer 1: vnstock 3.5+ (KBS source — works from any IP) ---
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol=ticker, source='KBS')
        df = stock.quote.history(start=start_date, end=end_date, interval='1D')
        if df is not None and not df.empty:
            return _parse_rows(df, ticker, has_value=False)
    except ImportError:
        pass
    except Exception as e:
        print(f"  vnstock KBS error for {ticker}: {e}")

    # --- Layer 2: vnstock3 (VCI source) ---
    try:
        from vnstock3 import Vnstock as Vnstock3
        stock = Vnstock3().stock(symbol=ticker, source='VCI')
        df = stock.quote.history(start=start_date, end=end_date, interval='1D')
        if df is not None and not df.empty:
            return _parse_rows(df, ticker, has_value=True)
    except ImportError:
        pass
    except Exception as e:
        print(f"  vnstock3 VCI error for {ticker}: {e}")

    # --- Layer 3: legacy vnstock (Python 3.9 local dev) ---
    try:
        import warnings
        warnings.filterwarnings('ignore')
        from vnstock import stock_historical_data
        df = stock_historical_data(
            symbol=ticker, start_date=start_date, end_date=end_date,
            resolution='1D', type='stock', beautify=True
        )
        if df is not None and not df.empty:
            return _parse_rows(df, ticker, has_value=False)
    except Exception as e:
        print(f"  legacy vnstock error for {ticker}: {e}")

    return []


def upsert_records(records: list[dict], crawl_time: datetime):
    """Bulk upsert via psycopg2 execute_values — single round-trip, no timeout on large datasets."""
    if not records:
        return 0
    from psycopg2.extras import execute_values
    rows = [
        (r['ticker'], r['date'], r.get('open'), r.get('high'), r.get('low'),
         r.get('close'), r.get('volume'), r.get('value'), crawl_time, 'vnstock3', 'stock')
        for r in records
    ]
    sql = """
        INSERT INTO vn30_ohlcv_daily
            (ticker, date, open, high, low, close, volume, value, crawl_time, source, group_name)
        VALUES %s
        ON CONFLICT (ticker, date) DO UPDATE SET
            open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
            close=EXCLUDED.close, volume=EXCLUDED.volume,
            value=EXCLUDED.value, crawl_time=EXCLUDED.crawl_time,
            source=EXCLUDED.source, group_name=EXCLUDED.group_name
    """
    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            execute_values(cur, sql, rows, page_size=500)
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(rows)


def main():
    ensure_table()

    # Crawl last 5 trading days as buffer (handles weekends/holidays)
    end_date = date_str
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    crawl_time = datetime.now()
    total_inserted = 0
    total_errors = 0

    for ticker in VN30_TICKERS:
        print(f"\n  [{ticker}] Fetching {start_date} → {end_date}")
        try:
            records = fetch_ohlcv_vnstock(ticker, start_date, end_date)
            if records:
                n = upsert_records(records, crawl_time)
                total_inserted += n
                last = records[-1]
                print(f"  [{ticker}] {n} records upserted. Latest close: {last.get('close')}")
            else:
                print(f"  [{ticker}] No data returned")
            time.sleep(0.5)   # polite delay
        except Exception as e:
            import traceback
            print(f"  [{ticker}] ERROR: {e}")
            print(f"  {traceback.format_exc()}")
            total_errors += 1

    print(f"\n{'='*60}")
    print(f"VN30 OHLCV Crawler done. Upserted: {total_inserted}, Errors: {total_errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
