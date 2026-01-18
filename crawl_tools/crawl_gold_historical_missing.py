import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup
import time
from tqdm import tqdm
from datetime import datetime, timedelta

# Database connection
conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

# Define date range for missing data
start_date = "2023-09-10"
end_date = "2024-04-25"

# Generate date range
date_range = pd.date_range(start=start_date, end=end_date, freq='D')

print(f"Starting to crawl gold prices from {start_date} to {end_date}")
print(f"Total days to crawl: {len(date_range)}")
print("="*60)

def crawl_gold_price_24h(date_str):
    """
    Crawl all gold brand prices from 24h.com.vn for a specific date
    date_str format: 'YYYY-MM-DD'
    Returns: list of dicts with buy and sell prices for all gold brands
    """
    url = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        gold_records = []
        tables = soup.find_all('table')

        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Check if this row contains brand info
                    brand_td = cols[0].find('h2')
                    if not brand_td:
                        continue

                    brand_type = brand_td.get_text(strip=True)

                    try:
                        # Find price spans with class 'fixW'
                        buy_span = cols[1].find('span', class_='fixW')
                        sell_span = cols[2].find('span', class_='fixW')

                        if not buy_span or not sell_span:
                            continue

                        # Get price text and clean
                        buy_price = buy_span.get_text(strip=True).replace('.', '').replace(',', '')
                        sell_price = sell_span.get_text(strip=True).replace('.', '').replace(',', '')

                        # Convert to float and multiply by 1000 (prices are in thousands)
                        buy_price = float(buy_price) * 1000
                        sell_price = float(sell_price) * 1000

                        gold_records.append({
                            'date': date_str,
                            'type': brand_type,
                            'buy_price': buy_price,
                            'sell_price': sell_price
                        })
                    except (ValueError, AttributeError):
                        continue

        return gold_records

    except Exception as e:
        print(f"Error crawling {date_str}: {e}")
        return []

# Run the crawl with progress bar
total_inserted = 0
total_skipped = 0
total_errors = 0

for date in tqdm(date_range, desc="Crawling progress"):
    date_str = date.strftime('%Y-%m-%d')

    # Crawl data for this date
    results = crawl_gold_price_24h(date_str)

    if results:
        # Insert each record into database
        for record in results:
            try:
                with engine.connect() as conn:
                    # Check if record already exists
                    result = conn.execute(
                        text("SELECT COUNT(*) FROM vn_gold_24h_hist WHERE date = :date AND type = :type"),
                        {'date': record['date'], 'type': record['type']}
                    )

                    if result.scalar() > 0:
                        total_skipped += 1
                        continue

                    # Insert new record
                    conn.execute(
                        text("""
                            INSERT INTO vn_gold_24h_hist (date, type, buy_price, sell_price)
                            VALUES (:date, :type, :buy_price, :sell_price)
                        """),
                        record
                    )
                    conn.commit()
                    total_inserted += 1

            except Exception as e:
                print(f"\nError inserting record for {date_str} - {record['type']}: {e}")
                total_errors += 1
    else:
        total_errors += 1

    # Rate limiting to avoid overwhelming the server
    time.sleep(0.3)

    # Print progress every 50 days
    if (date - date_range[0]).days % 50 == 0 and date != date_range[0]:
        print(f"\nProgress: Inserted {total_inserted}, Skipped {total_skipped}, Errors {total_errors}")

print("\n" + "="*60)
print("Crawling completed!")
print(f"Total records inserted: {total_inserted}")
print(f"Total records skipped (already exist): {total_skipped}")
print(f"Total errors: {total_errors}")
print("="*60)

# Verify the data range in database
print("\nVerifying data in database...")
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
            WHERE date BETWEEN :start_date AND :end_date
        """),
        {'start_date': start_date, 'end_date': end_date}
    )

    row = result.fetchone()
    if row:
        print(f"Date range in DB: {row[0]} to {row[1]}")
        print(f"Total records: {row[2]}")
        print(f"Unique dates: {row[3]}")
        print(f"Unique gold types: {row[4]}")

print("\n✅ Script completed!")
