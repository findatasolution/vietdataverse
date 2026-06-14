"""
One-time backfill for global_macro table:
1. Add sp500_price (S&P 500, ^GSPC) and dowjones_price (Dow Jones, ^DJI) columns
2. Backfill historical values for all existing rows

Run: python crawl_tools/backfill_global_indices.py
"""

import sys
import os
from datetime import datetime, date
from dotenv import load_dotenv
from pathlib import Path
import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / '.env')

GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
if not GLOBAL_INDICATOR_DB:
    sys.exit('GLOBAL_INDICATOR_DB not set')

engine = create_engine(GLOBAL_INDICATOR_DB)

print('=' * 60)
print('Global Macro - Add S&P 500 / Dow Jones columns + backfill')
print('=' * 60)

with engine.connect() as conn:
    print('\n[1/3] Adding columns sp500_price, dowjones_price (if missing)')
    for col in ('sp500_price', 'dowjones_price'):
        try:
            conn.execute(text(f'ALTER TABLE global_macro ADD COLUMN {col} NUMERIC'))
            conn.commit()
            print(f'  Added column {col}')
        except Exception:
            conn.rollback()
            print(f'  Column {col} already exists — skipping')

    min_d, max_d = conn.execute(text('SELECT MIN(date), MAX(date) FROM global_macro')).fetchone()

print(f'\n[2/3] Fetching yfinance data for ^GSPC and ^DJI ({min_d} -> {max_d})')

sp500_df = yf.download('^GSPC', start=str(min_d), end=str(max_d + pd.Timedelta(days=1)), progress=False, auto_adjust=True)['Close'].squeeze()
dji_df = yf.download('^DJI', start=str(min_d), end=str(max_d + pd.Timedelta(days=1)), progress=False, auto_adjust=True)['Close'].squeeze()

print(f'  S&P 500 rows: {len(sp500_df)}')
print(f'  Dow Jones rows: {len(dji_df)}')


def get_val(series, d):
    try:
        v = series.get(pd.Timestamp(d))
        return float(v) if v is not None and not pd.isna(v) else None
    except Exception:
        return None


print('\n[3/3] Updating rows')
updated = 0
with engine.connect() as conn:
    dates = [r[0] for r in conn.execute(text('SELECT date FROM global_macro ORDER BY date')).fetchall()]
    for d in dates:
        sp500_val = get_val(sp500_df, d)
        dji_val = get_val(dji_df, d)
        if sp500_val is None and dji_val is None:
            continue
        conn.execute(text("""
            UPDATE global_macro SET sp500_price = :sp500, dowjones_price = :dji
            WHERE date = :d
        """), {'sp500': sp500_val, 'dji': dji_val, 'd': d})
        updated += 1
    conn.commit()

print(f'  Updated {updated}/{len(dates)} rows')
print(f'\n{"="*60}')
print('Done')
print('=' * 60)
