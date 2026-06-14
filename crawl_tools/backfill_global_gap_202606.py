"""
One-time backfill for global_macro table:
Insert missing rows for 2026-04-29 -> today (gap caused by broken yfinance==0.2.49
in crawl_gold_silver.py, fixed by bumping to yfinance==1.4.1 in requirements.txt).

Run: python crawl_tools/backfill_global_gap_202606.py
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

START = '2026-04-25'  # small overlap with existing data to confirm dedup via ON CONFLICT
END = (date.today() + pd.Timedelta(days=1)).isoformat()

print('=' * 60)
print('Global Macro Gap Backfill (2026-04-29 -> today)')
print('=' * 60)

print('\nFetching yfinance data...')
series = {}
for label, symbol in [
    ('gold', 'GC=F'),
    ('silver', 'SI=F'),
    ('nasdaq', '^IXIC'),
    ('sp500', '^GSPC'),
    ('dowjones', '^DJI'),
]:
    df = yf.download(symbol, start=START, end=END, progress=False, auto_adjust=True)['Close']
    df = df.squeeze()
    series[label] = df
    print(f'  {label} ({symbol}) rows: {len(df)}')


def get_val(s, d):
    try:
        v = s.get(pd.Timestamp(d))
        return float(v) if v is not None and not pd.isna(v) else None
    except Exception:
        return None


trading_dates = sorted({d.date() for d in series['nasdaq'].index})

with engine.connect() as conn:
    existing_dates = {
        r[0] for r in conn.execute(
            text("SELECT date FROM global_macro WHERE date >= :start"),
            {'start': START}
        ).fetchall()
    }

    inserted = 0
    for d in trading_dates:
        if d in existing_dates:
            continue

        vals = {label: get_val(s, d) for label, s in series.items()}
        if all(v is None for v in vals.values()):
            print(f'  {d}: all None — skipping')
            continue

        conn.execute(text("""
            INSERT INTO global_macro (date, crawl_time, gold_price, silver_price, nasdaq_price, sp500_price, dowjones_price)
            VALUES (:date, :ct, :gold, :silver, :nasdaq, :sp500, :dowjones)
            ON CONFLICT (date) DO NOTHING
        """), {
            'date': d, 'ct': datetime.utcnow(),
            'gold': vals['gold'], 'silver': vals['silver'], 'nasdaq': vals['nasdaq'],
            'sp500': vals['sp500'], 'dowjones': vals['dowjones'],
        })
        print(f"  {d}: inserted gold={vals['gold']} silver={vals['silver']} nasdaq={vals['nasdaq']} sp500={vals['sp500']} dowjones={vals['dowjones']}")
        inserted += 1

    conn.commit()
    print(f'\nInserted {inserted} new rows')

with engine.connect() as conn:
    r = conn.execute(text('SELECT MIN(date), MAX(date), COUNT(*) FROM global_macro')).fetchone()
    print(f'\nFinal range: {r[0]} -> {r[1]}, {r[2]} rows')

print('=' * 60)
print('Done')
print('=' * 60)
