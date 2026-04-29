"""
One-time backfill for global_macro table:
1. Fix NASDAQ NULL on 2026-04-08 and 2026-04-09
2. Insert missing rows 2026-04-23 onwards

Run: python crawl_tools/backfill_global_macro.py
"""

import sys
import os
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pathlib import Path
import yfinance as yf
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / '.env')

GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
if not GLOBAL_INDICATOR_DB:
    sys.exit('GLOBAL_INDICATOR_DB not set')

engine = create_engine(GLOBAL_INDICATOR_DB)

print('=' * 60)
print('Global Macro Backfill')
print('=' * 60)

# ── Fetch yfinance data ───────────────────────────────────────────────────────
print('\nFetching yfinance data...')

gold_df   = yf.download('GC=F',  start='2026-04-07', end=date.today().isoformat(), progress=False, auto_adjust=True)['Close']
silver_df = yf.download('SI=F',  start='2026-04-07', end=date.today().isoformat(), progress=False, auto_adjust=True)['Close']
nasdaq_df = yf.download('^IXIC', start='2026-04-07', end=date.today().isoformat(), progress=False, auto_adjust=True)['Close']

# Flatten MultiIndex if present
gold_df   = gold_df.squeeze()
silver_df = silver_df.squeeze()
nasdaq_df = nasdaq_df.squeeze()

print(f'  Gold rows: {len(gold_df)}')
print(f'  Silver rows: {len(silver_df)}')
print(f'  NASDAQ rows: {len(nasdaq_df)}')


def get_val(series, d):
    """Get float value for a date, or None."""
    try:
        v = series.get(str(d))
        if v is None:
            # Try pandas Timestamp key
            import pandas as pd
            v = series.get(pd.Timestamp(d))
        return float(v) if v is not None else None
    except Exception:
        return None


with engine.connect() as conn:
    # ── 1. Fix NULL NASDAQ on 8 Apr and 9 Apr ────────────────────────────────
    print('\n[1/2] Fixing NASDAQ NULL on 2026-04-08 and 2026-04-09')
    for d in [date(2026, 4, 8), date(2026, 4, 9)]:
        nasdaq_val = get_val(nasdaq_df, d)
        if nasdaq_val is None:
            print(f'  {d}: yfinance returned None for NASDAQ — skipping')
            continue

        existing = conn.execute(
            text("SELECT nasdaq_price FROM global_macro WHERE date = :d"),
            {'d': d}
        ).fetchone()

        if existing is None:
            print(f'  {d}: row missing entirely — inserting')
            gold_val   = get_val(gold_df, d)
            silver_val = get_val(silver_df, d)
            conn.execute(text("""
                INSERT INTO global_macro (date, crawl_time, gold_price, silver_price, nasdaq_price)
                VALUES (:date, :ct, :gold, :silver, :nasdaq)
            """), {'date': d, 'ct': datetime.utcnow(),
                   'gold': gold_val, 'silver': silver_val, 'nasdaq': nasdaq_val})
        elif existing[0] is None:
            conn.execute(
                text("UPDATE global_macro SET nasdaq_price = :v WHERE date = :d"),
                {'v': nasdaq_val, 'd': d}
            )
            print(f'  {d}: updated NASDAQ NULL → {nasdaq_val:,.0f}')
        else:
            print(f'  {d}: NASDAQ already set ({existing[0]:,.0f}) — skipping')
    conn.commit()

    # ── 2. Insert missing rows from 2026-04-23 onwards ───────────────────────
    print('\n[2/2] Inserting missing rows 2026-04-23 → today')

    # Add UNIQUE constraint on date if missing (safe — idempotent)
    try:
        conn.execute(text('ALTER TABLE global_macro ADD CONSTRAINT global_macro_date_key UNIQUE (date)'))
        conn.commit()
        print('  Added UNIQUE constraint on date')
    except Exception:
        conn.rollback()

    # Find dates that have yfinance data but are absent from DB
    existing_dates = {
        r[0] for r in conn.execute(
            text("SELECT date FROM global_macro WHERE date >= '2026-04-23'")
        ).fetchall()
    }

    # Get all trading dates from yfinance (use NASDAQ index as market calendar)
    trading_dates = sorted({d.date() for d in nasdaq_df.index})

    inserted = 0
    for d in trading_dates:
        if d < date(2026, 4, 23):
            continue
        if d in existing_dates:
            print(f'  {d}: already exists — skipping')
            continue

        gold_val   = get_val(gold_df, d)
        silver_val = get_val(silver_df, d)
        nasdaq_val = get_val(nasdaq_df, d)

        if gold_val is None and silver_val is None and nasdaq_val is None:
            print(f'  {d}: all None — skipping')
            continue

        conn.execute(text("""
            INSERT INTO global_macro (date, crawl_time, gold_price, silver_price, nasdaq_price)
            VALUES (:date, :ct, :gold, :silver, :nasdaq)
            ON CONFLICT (date) DO NOTHING
        """), {'date': d, 'ct': datetime.utcnow(),
               'gold': gold_val, 'silver': silver_val, 'nasdaq': nasdaq_val})
        print(f'  {d}: inserted gold={gold_val:.1f} silver={silver_val:.2f} nasdaq={nasdaq_val:,.0f}')
        inserted += 1

    conn.commit()
    print(f'\nInserted {inserted} new rows')

print(f'\n{"="*60}')
print('Done')
print('=' * 60)
