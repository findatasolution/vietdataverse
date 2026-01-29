"""
Gold & Silver Price Crawler
Runs 2x daily: Morning (8:30 AM VN) and Afternoon (2:30 PM VN)
- Domestic silver prices from giabac.vn
- Domestic gold prices from 24h.com.vn
- Global gold/silver/NASDAQ from Yahoo Finance
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import requests
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup
import time
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"Gold & Silver Crawler - {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

# Database connections
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
if not GLOBAL_INDICATOR_DB:
    GLOBAL_INDICATOR_DB = 'postgresql://neondb_owner:npg_DTMVHjWIy21J@ep-frosty-forest-a19clsva-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
global_indicator_engine = create_engine(GLOBAL_INDICATOR_DB)


############## 1. Domestic Silver Prices (HTTP - no Selenium needed)
print(f"\n--- Crawling Silver Prices ---")

try:
    response_silver = requests.get("https://giabac.vn/", timeout=15)
    response_silver.raise_for_status()
    soup_silver = BeautifulSoup(response_silver.content, 'html.parser')

    buy_price = None
    sell_price = None

    price_table = soup_silver.find(id='priceTable')
    if price_table:
        rows = price_table.find_all('tr')
        print(f"  Found {len(rows)} rows in #priceTable")

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 4:
                product_name = cells[0].get_text(strip=True)
                if '1 lượng' in product_name.lower():
                    buy_text = cells[2].get_text(strip=True).replace(',', '').replace('.', '')
                    sell_text = cells[3].get_text(strip=True).replace(',', '').replace('.', '')
                    if buy_text and sell_text:
                        buy_price = float(buy_text)
                        sell_price = float(sell_text)
                        print(f"  Found silver price from: {product_name}")
                        break
    else:
        print("  #priceTable not found in HTML")

    if buy_price and sell_price:
        crawl_time = datetime.now()
        silver_record = {
            'date': date_str,
            'crawl_time': crawl_time,
            'buy_price': buy_price,
            'sell_price': sell_price
        }

        # Check if exists in same hour
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT COUNT(*) FROM vn_silver_phuquy_hist
                    WHERE date = :date
                    AND crawl_time >= :start_time
                    AND crawl_time < :end_time
                """),
                {
                    'date': date_str,
                    'start_time': crawl_time.replace(minute=0, second=0, microsecond=0),
                    'end_time': crawl_time.replace(minute=59, second=59, microsecond=999999)
                }
            )
            exists = result.scalar() > 0

        if exists:
            print(f"  Silver data for {date_str} {crawl_time.strftime('%H:%M')} already exists")
        else:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        INSERT INTO vn_silver_phuquy_hist (date, crawl_time, buy_price, sell_price)
                        VALUES (:date, :crawl_time, :buy_price, :sell_price)
                    """),
                    silver_record
                )
                conn.commit()
            print(f"  Pushed silver: {crawl_time.strftime('%H:%M')} | Buy {buy_price:,.0f} | Sell {sell_price:,.0f}")
    else:
        print(f"  No silver price found")

except Exception as e:
    import traceback
    print(f"  Error crawling Silver: {e}")
    print(f"  Traceback: {traceback.format_exc()}")


############## 1b. World Silver Spot Price (Kitco - backup source)
print(f"\n--- Crawling World Silver Spot (Kitco) ---")

try:
    response_kitco = requests.get("http://www.kitco.com/charts/silver", timeout=15,
                                   headers={'User-Agent': 'Mozilla/5.0'})
    response_kitco.raise_for_status()
    soup_kitco = BeautifulSoup(response_kitco.content, 'html.parser')

    # Extract silver price per ounce from Kitco
    world_silver_usd = None
    price_grid = soup_kitco.find(class_=lambda c: c and 'spotPriceGrid' in str(c))
    if price_grid:
        price_items = price_grid.find_all(class_=lambda c: c and 'convertPrice' in str(c))
        price_names = price_grid.find_all(class_=lambda c: c and 'priceName' in str(c))
        for name_el, price_el in zip(price_names, price_items):
            name_text = name_el.get_text(strip=True).lower()
            if name_text == 'ounce':
                price_text = price_el.get_text(strip=True).replace(',', '')
                try:
                    world_silver_usd = float(price_text)
                    print(f"  World silver: ${world_silver_usd:.2f}/oz")
                except ValueError:
                    pass
                break

    if world_silver_usd:
        crawl_time = datetime.now()

        # Create table if not exists and insert
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS world_silver_kitco_hist (
                    id SERIAL PRIMARY KEY,
                    date VARCHAR(10),
                    crawl_time TIMESTAMP,
                    price_usd_oz FLOAT
                )
            """))
            conn.commit()

            # Check duplicate
            result = conn.execute(
                text("SELECT COUNT(*) FROM world_silver_kitco_hist WHERE date = :date AND crawl_time >= :s AND crawl_time < :e"),
                {
                    'date': date_str,
                    's': crawl_time.replace(minute=0, second=0, microsecond=0),
                    'e': crawl_time.replace(minute=59, second=59, microsecond=999999)
                }
            )
            if result.scalar() > 0:
                print(f"  World silver for {date_str} this hour already exists")
            else:
                conn.execute(
                    text("INSERT INTO world_silver_kitco_hist (date, crawl_time, price_usd_oz) VALUES (:date, :crawl_time, :price)"),
                    {'date': date_str, 'crawl_time': crawl_time, 'price': world_silver_usd}
                )
                conn.commit()
                print(f"  Pushed world silver: ${world_silver_usd:.2f}/oz")
    else:
        print(f"  Could not parse Kitco silver price")

except Exception as e:
    print(f"  Error crawling Kitco silver: {e}")


############## 2. Domestic Gold Prices (HTTP)
print(f"\n--- Crawling Gold Prices ---")

url_gold = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'

try:
    response_gold = requests.get(url_gold, timeout=10)
    response_gold.raise_for_status()
    soup_gold = BeautifulSoup(response_gold.content, 'html.parser')
    crawl_time = datetime.now()
    gold_records = []
    tables_gold = soup_gold.find_all('table')

    for table in tables_gold:
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                brand_td = cols[0].find('h2')
                if not brand_td:
                    continue
                brand_type = brand_td.get_text(strip=True)

                try:
                    buy_span = cols[1].find('span', class_='fixW')
                    sell_span = cols[2].find('span', class_='fixW')

                    if not buy_span or not sell_span:
                        continue

                    buy_price = buy_span.get_text(strip=True).replace('.', '').replace(',', '')
                    sell_price = sell_span.get_text(strip=True).replace('.', '').replace(',', '')

                    buy_price = float(buy_price) * 1000
                    sell_price = float(sell_price) * 1000

                    gold_records.append({
                        'date': date_str,
                        'type': brand_type,
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'crawl_time': crawl_time
                    })
                except (ValueError, AttributeError):
                    continue

    if gold_records:
        print(f"  Crawled {len(gold_records)} gold brands for {date_str}")

        inserted = 0
        skipped = 0

        for record in gold_records:
            with engine.connect() as conn:
                result = conn.execute(
                    text("""
                        SELECT COUNT(*) FROM vn_gold_24h_hist
                        WHERE date = :date
                        AND type = :type
                        AND crawl_time >= :start_time
                        AND crawl_time < :end_time
                    """),
                    {
                        'date': record['date'],
                        'type': record['type'],
                        'start_time': crawl_time.replace(minute=0, second=0, microsecond=0),
                        'end_time': crawl_time.replace(minute=59, second=59, microsecond=999999)
                    }
                )

                if result.scalar() > 0:
                    skipped += 1
                    continue

                conn.execute(
                    text("""
                        INSERT INTO vn_gold_24h_hist (date, type, buy_price, sell_price, crawl_time)
                        VALUES (:date, :type, :buy_price, :sell_price, :crawl_time)
                    """),
                    record
                )
                conn.commit()
                inserted += 1

        print(f"  Pushed {inserted} gold records, skipped {skipped}")
    else:
        print(f"  No gold data found for {date_str}")

except Exception as e:
    print(f"  Error crawling gold prices: {e}")


############## 3. Global Macro Data from Yahoo Finance
print(f"\n--- Crawling Global Macro (Yahoo Finance) ---")

try:
    import yfinance as yf

    max_retries = 3
    retry_delay = 5

    gold_price = None
    silver_price = None
    nasdaq_price = None

    for attempt in range(max_retries):
        try:
            # Gold Futures
            gold = yf.Ticker("GC=F")
            gold_hist = gold.history(period="5d")
            if not gold_hist.empty:
                gold_price = float(gold_hist['Close'].iloc[-1])
                print(f"  Gold (GC=F): ${gold_price:.2f}")

            time.sleep(2)

            # Silver Futures
            silver = yf.Ticker("SI=F")
            silver_hist = silver.history(period="5d")
            if not silver_hist.empty:
                silver_price = float(silver_hist['Close'].iloc[-1])
                print(f"  Silver (SI=F): ${silver_price:.2f}")

            time.sleep(2)

            # NASDAQ
            nasdaq = yf.Ticker("^IXIC")
            nasdaq_hist = nasdaq.history(period="5d")
            if not nasdaq_hist.empty:
                nasdaq_price = float(nasdaq_hist['Close'].iloc[-1])
                print(f"  NASDAQ (^IXIC): {nasdaq_price:.2f}")

            break

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"  Retry {attempt + 1}/{max_retries} after error: {e}")
                time.sleep(retry_delay * (attempt + 1))
            else:
                raise

    if gold_price or silver_price or nasdaq_price:
        macro_data = {
            'date': date_str,
            'crawl_time': datetime.now(),
            'gold_price': gold_price,
            'silver_price': silver_price,
            'nasdaq_price': nasdaq_price
        }

        with global_indicator_engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM global_macro WHERE date = '{date_str}'"))
            exists = result.scalar() > 0

        if exists:
            print(f"  Global macro data for {date_str} already exists, skipping")
        else:
            macro_df = pd.DataFrame([macro_data])
            macro_df['date'] = pd.to_datetime(macro_df['date'])
            macro_df.to_sql('global_macro', global_indicator_engine, if_exists='append', index=False)
            print(f"  Pushed global macro data for {date_str}")
    else:
        print(f"  No global macro data retrieved")

except ImportError:
    print(f"  yfinance not installed, skipping global macro")
except Exception as e:
    print(f"  Error crawling global macro: {e}")


print(f"\n{'='*60}")
print(f"Gold & Silver Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")
