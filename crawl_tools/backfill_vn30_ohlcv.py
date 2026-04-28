"""
ONE-TIME backfill: vn30_ohlcv_daily từ 2015-01-01 đến hôm nay.
Chạy 1 lần rồi xóa file này.

Usage:
    cd crawl_tools
    python backfill_vn30_ohlcv.py

Note: KBS rate limit 20 req/min (guest). ~30-60 phút cho 30 tickers × 10 năm.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os, time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import psycopg2

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

CRAWLING_CORP_DB = os.getenv('CRAWLING_CORP_DB')
if not CRAWLING_CORP_DB:
    raise ValueError("CRAWLING_CORP_DB not set")
engine = create_engine(CRAWLING_CORP_DB)

VN30_TICKERS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR',
    'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'NVL', 'PDR', 'PLX',
    'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VPB'
]

BACKFILL_START = '2015-01-01'
BACKFILL_END   = datetime.now().strftime('%Y-%m-%d')
YEARS          = list(range(2015, datetime.now().year + 1))


def fetch_ohlcv(ticker: str, start: str, end: str) -> list:
    def _rows(df, has_value=False):
        out = []
        for _, row in df.iterrows():
            out.append({
                'ticker': ticker,
                'date':   str(row.get('time', row.name))[:10],
                'open':   float(row['open'])   if row.get('open')   else None,
                'high':   float(row['high'])   if row.get('high')   else None,
                'low':    float(row['low'])    if row.get('low')    else None,
                'close':  float(row['close'])  if row.get('close')  else None,
                'volume': float(row['volume']) if row.get('volume') else None,
                'value':  float(row['value'])  if has_value and row.get('value') else None,
            })
        return out

    # Layer 1: KBS
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol=ticker, source='KBS')
        for attempt in range(4):
            try:
                df = stock.quote.history(start=start, end=end, interval='1D')
                if df is not None and not df.empty:
                    return _rows(df)
                break
            except Exception as e:
                msg = str(e).lower()
                if any(x in msg for x in ['rate limit', 'giới hạn', '429', 'tối đa']):
                    wait = 60 + attempt * 30
                    print(f"    KBS rate limit — waiting {wait}s (attempt {attempt+1}/4)...")
                    time.sleep(wait)
                else:
                    print(f"    KBS error: {e}")
                    break
    except ImportError:
        pass

    # Layer 2: VCI
    try:
        from vnstock3 import Vnstock as Vnstock3
        df = Vnstock3().stock(symbol=ticker, source='VCI').quote.history(start=start, end=end, interval='1D')
        if df is not None and not df.empty:
            return _rows(df, has_value=True)
    except Exception as e:
        print(f"    VCI error: {e}")

    return []


def upsert(records: list, crawl_time: datetime) -> int:
    if not records:
        return 0
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        rows = [(r['ticker'], r['date'], r['open'], r['high'], r['low'],
                 r['close'], r['volume'], r['value'], crawl_time,
                 'vnstock3', 'stock') for r in records]
        psycopg2.extras.execute_values(cur, """
            INSERT INTO vn30_ohlcv_daily
                (ticker, date, open, high, low, close, volume, value, crawl_time, source, group_name)
            VALUES %s
            ON CONFLICT (ticker, date) DO UPDATE SET
                open=EXCLUDED.open, high=EXCLUDED.high, low=EXCLUDED.low,
                close=EXCLUDED.close, volume=EXCLUDED.volume, value=EXCLUDED.value,
                crawl_time=EXCLUDED.crawl_time
        """, rows, page_size=500)
        raw.commit()
        return len(rows)
    finally:
        cur.close()
        raw.close()


def main():
    crawl_time = datetime.now()
    grand_total = 0
    errors = 0

    print(f"\n{'='*60}")
    print(f"VN30 OHLCV Backfill — {BACKFILL_START} → {BACKFILL_END}")
    print(f"Tickers: {len(VN30_TICKERS)}, Years: {YEARS[0]}–{YEARS[-1]}")
    print(f"{'='*60}")

    for i, ticker in enumerate(VN30_TICKERS, 1):
        print(f"\n[{i}/{len(VN30_TICKERS)}] {ticker}")
        ticker_total = 0
        try:
            for year in YEARS:
                start = f'{year}-01-01'
                end   = f'{year}-12-31' if year < datetime.now().year else BACKFILL_END
                try:
                    records = fetch_ohlcv(ticker, start, end)
                    n = upsert(records, crawl_time)
                    ticker_total += n
                    print(f"    {year}: {n} records")
                except Exception as e:
                    print(f"    {year}: ERROR — {e}")
                time.sleep(4)   # ~15 req/min, under KBS 20/min limit
            grand_total += ticker_total
            print(f"  → {ticker} done: {ticker_total} records total")
        except Exception as e:
            print(f"  → {ticker} FAILED: {e}")
            errors += 1
        time.sleep(5)

    print(f"\n{'='*60}")
    print(f"Backfill done. Total: {grand_total} records, Errors: {errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    import psycopg2.extras
    main()
