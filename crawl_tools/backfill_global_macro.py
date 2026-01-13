"""
Backfill historical global_macro data from Yahoo Finance
This script fetches historical data for the past 1 year and populates the global_macro table
Run this once to populate historical data before daily automation takes over
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlalchemy import create_engine, text
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import time

# Database connection
conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

# Define tickers
tickers = {
    'gold': 'GC=F',      # Gold Futures
    'silver': 'SI=F',    # Silver Futures
    'nasdaq': '^IXIC'    # NASDAQ Composite
}

print("="*60)
print("Backfilling Global Macro Historical Data")
print("="*60)

# Fetch 1 year of historical data
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

print(f"\nFetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
print(f"This will take approximately 30 seconds due to rate limiting...\n")

try:
    # Fetch all tickers with retry logic
    def fetch_ticker_history(ticker_symbol, start, end, max_retries=3):
        """Fetch historical data with exponential backoff retry"""
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(start=start, end=end)
                if not hist.empty:
                    return hist['Close']
                else:
                    print(f"  Attempt {attempt + 1}/{max_retries}: No data for {ticker_symbol}")
            except Exception as e:
                error_msg = str(e)
                if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                    if attempt < max_retries - 1:
                        delay = 5 * (2 ** attempt)
                        print(f"  Rate limited for {ticker_symbol}, waiting {delay}s...")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Rate limited after {max_retries} attempts")
                else:
                    raise e
        return None

    # Fetch Gold
    print("Fetching Gold Futures (GC=F)...")
    gold_data = fetch_ticker_history(tickers['gold'], start_date, end_date)
    time.sleep(2)  # Polite delay

    # Fetch Silver
    print("Fetching Silver Futures (SI=F)...")
    silver_data = fetch_ticker_history(tickers['silver'], start_date, end_date)
    time.sleep(2)

    # Fetch NASDAQ
    print("Fetching NASDAQ Composite (^IXIC)...")
    nasdaq_data = fetch_ticker_history(tickers['nasdaq'], start_date, end_date)
    time.sleep(2)

    # Merge all data into single DataFrame
    print("\nMerging datasets...")
    df = pd.DataFrame({
        'gold_price': gold_data,
        'silver_price': silver_data,
        'nasdaq_price': nasdaq_data
    })

    # Reset index to get dates as column
    df = df.reset_index()
    df = df.rename(columns={'Date': 'date'})

    # Add crawl_time
    df['crawl_time'] = datetime.now()

    # Convert date to date only (remove time component)
    df['date'] = pd.to_datetime(df['date']).dt.date

    # Remove rows where all prices are NaN
    df = df.dropna(subset=['gold_price', 'silver_price', 'nasdaq_price'], how='all')

    print(f"\nPrepared {len(df)} rows of historical data")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nSample data:")
    print(df.head())

    # Check existing data in database
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM global_macro"))
        existing_count = result.scalar()
        print(f"\nExisting records in database: {existing_count}")

    # Insert data (skip duplicates)
    print("\nInserting data into global_macro table...")
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            with engine.connect() as conn:
                # Check if date already exists
                check = conn.execute(
                    text("SELECT COUNT(*) FROM global_macro WHERE date = :date"),
                    {'date': row['date']}
                )
                if check.scalar() > 0:
                    skipped += 1
                    continue

                # Insert new record
                conn.execute(
                    text("""
                        INSERT INTO global_macro (date, crawl_time, gold_price, silver_price, nasdaq_price)
                        VALUES (:date, :crawl_time, :gold_price, :silver_price, :nasdaq_price)
                    """),
                    {
                        'date': row['date'],
                        'crawl_time': row['crawl_time'],
                        'gold_price': float(row['gold_price']) if pd.notna(row['gold_price']) else None,
                        'silver_price': float(row['silver_price']) if pd.notna(row['silver_price']) else None,
                        'nasdaq_price': float(row['nasdaq_price']) if pd.notna(row['nasdaq_price']) else None
                    }
                )
                conn.commit()
                inserted += 1

                if inserted % 10 == 0:
                    print(f"  Inserted {inserted} rows...")
        except Exception as e:
            print(f"  ⚠️ Error inserting {row['date']}: {e}")
            continue

    print(f"\n✅ Backfill complete!")
    print(f"  - Inserted: {inserted} new records")
    print(f"  - Skipped: {skipped} existing records")

    # Show final count
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM global_macro"))
        total_count = result.scalar()
        print(f"  - Total records: {total_count}")

        # Show date range
        result = conn.execute(text("SELECT MIN(date), MAX(date) FROM global_macro"))
        min_date, max_date = result.fetchone()
        print(f"  - Date range: {min_date} to {max_date}")

except Exception as e:
    print(f"\n❌ Error during backfill: {e}")
    import traceback
    traceback.print_exc()