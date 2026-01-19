import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
from sqlalchemy import create_engine, text

# Database connection
import os
from dotenv import load_dotenv
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

print("="*70)
print("CHECKING GOLD DATA IN vn_gold_24h_hist TABLE")
print("="*70)

# Check overall data
with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                COUNT(*) as total_records,
                COUNT(DISTINCT date) as unique_dates,
                COUNT(DISTINCT type) as unique_types
            FROM vn_gold_24h_hist
        """)
    )
    row = result.fetchone()
    print(f"\nOverall Statistics:")
    print(f"  Date range: {row[0]} to {row[1]}")
    print(f"  Total records: {row[2]:,}")
    print(f"  Unique dates: {row[3]:,}")
    print(f"  Unique gold types: {row[4]}")

# Check specific period 2023-09-10 to 2024-04-25
with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                COUNT(*) as total_records,
                COUNT(DISTINCT date) as unique_dates,
                COUNT(DISTINCT type) as unique_types
            FROM vn_gold_24h_hist
            WHERE date BETWEEN '2023-09-10' AND '2024-04-25'
        """)
    )
    row = result.fetchone()
    print(f"\nPeriod 2023-09-10 to 2024-04-25:")
    print(f"  Date range: {row[0]} to {row[1]}")
    print(f"  Total records: {row[2]:,}")
    print(f"  Unique dates: {row[3]:,}")
    print(f"  Unique gold types: {row[4]}")

# List all gold types
with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT DISTINCT type
            FROM vn_gold_24h_hist
            ORDER BY type
        """)
    )
    types = [row[0] for row in result.fetchall()]
    print(f"\nAll Gold Types:")
    for i, gold_type in enumerate(types, 1):
        print(f"  {i}. {gold_type}")

# Check missing dates in the period
with engine.connect() as conn:
    result = conn.execute(
        text("""
            WITH date_series AS (
                SELECT generate_series(
                    '2023-09-10'::date,
                    '2024-04-25'::date,
                    '1 day'::interval
                )::date AS expected_date
            )
            SELECT expected_date
            FROM date_series
            WHERE expected_date NOT IN (
                SELECT DISTINCT date
                FROM vn_gold_24h_hist
                WHERE date BETWEEN '2023-09-10' AND '2024-04-25'
            )
            ORDER BY expected_date
        """)
    )
    missing_dates = [row[0] for row in result.fetchall()]

    if missing_dates:
        print(f"\n⚠️  WARNING: Found {len(missing_dates)} missing dates:")
        for date in missing_dates[:10]:  # Show first 10
            print(f"  - {date}")
        if len(missing_dates) > 10:
            print(f"  ... and {len(missing_dates) - 10} more dates")
    else:
        print(f"\n✅ No missing dates! All dates from 2023-09-10 to 2024-04-25 are present.")

# Check records per date (should be around 7 types per date)
with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT
                date,
                COUNT(*) as num_types
            FROM vn_gold_24h_hist
            WHERE date BETWEEN '2023-09-10' AND '2024-04-25'
            GROUP BY date
            HAVING COUNT(*) < 5
            ORDER BY date
            LIMIT 10
        """)
    )
    incomplete_dates = list(result.fetchall())

    if incomplete_dates:
        print(f"\n⚠️  WARNING: Found {len(incomplete_dates)} dates with incomplete data (<5 types):")
        for date, num_types in incomplete_dates:
            print(f"  - {date}: {num_types} types")
    else:
        print(f"\n✅ All dates have sufficient gold types recorded.")

# Sample data from the period
print(f"\nSample Data (first 5 records from the period):")
with engine.connect() as conn:
    result = conn.execute(
        text("""
            SELECT date, type, buy_price, sell_price
            FROM vn_gold_24h_hist
            WHERE date BETWEEN '2023-09-10' AND '2024-04-25'
            ORDER BY date, type
            LIMIT 5
        """)
    )
    for row in result.fetchall():
        print(f"  {row[0]} | {row[1]:30s} | Buy: {row[2]:>12,.0f} | Sell: {row[3]:>12,.0f}")

print("\n" + "="*70)
print("VERIFICATION COMPLETE")
print("="*70)
