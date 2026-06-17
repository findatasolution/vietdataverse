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
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"Gold & Silver Crawler - {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

# Database connections
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    sys.exit("CRAWLING_BOT_DB env var not set")
engine = create_engine(CRAWLING_BOT_DB)

GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
if not GLOBAL_INDICATOR_DB:
    sys.exit("GLOBAL_INDICATOR_DB env var not set")
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

        # Check if exists in same hour from same source
        with engine.connect() as conn:
            result = conn.execute(
                text("""SELECT COUNT(*) FROM vn_macro_silver_daily
                        WHERE date = :date AND source = 'giabac.vn'
                        AND crawl_time >= :start_time AND crawl_time < :end_time"""),
                {
                    'date': date_str,
                    'start_time': crawl_time.replace(minute=0, second=0, microsecond=0),
                    'end_time': crawl_time.replace(minute=59, second=59, microsecond=999999)
                }
            )
            exists = result.scalar() > 0

        if exists:
            print(f"  Silver (giabac.vn) for {date_str} {crawl_time.strftime('%H:%M')} already exists")
        else:
            with engine.connect() as conn:
                conn.execute(
                    text("""INSERT INTO vn_macro_silver_daily (date, crawl_time, buy_price, sell_price, source, group_name)
                            VALUES (:date, :crawl_time, :buy_price, :sell_price, 'giabac.vn', 'commodity')"""),
                    {'date': date_str, 'crawl_time': crawl_time, 'buy_price': buy_price, 'sell_price': sell_price}
                )
                conn.commit()
            print(f"  Pushed silver (giabac.vn): Buy {buy_price:,.0f} | Sell {sell_price:,.0f}")
    else:
        print(f"  No silver price found")

except Exception as e:
    import traceback
    print(f"  Error crawling Silver: {e}")
    print(f"  Traceback: {traceback.format_exc()}")


############## 1b. Domestic Silver Backup (phuquygroup.vn)
print(f"\n--- Crawling Silver Backup (phuquygroup.vn) ---")

try:
    response_pq = requests.get("https://giabac.phuquygroup.vn/", timeout=15,
                                headers={'User-Agent': 'Mozilla/5.0'})
    response_pq.raise_for_status()
    soup_pq = BeautifulSoup(response_pq.content, 'html.parser')

    buy_price_pq = None
    sell_price_pq = None

    table_pq = soup_pq.find('table')
    if table_pq:
        rows_pq = table_pq.find_all('tr')
        for row in rows_pq:
            cells = row.find_all('td')
            if len(cells) >= 4:
                product_name = cells[0].get_text(strip=True)
                if '1' in product_name and ('LƯỢNG' in product_name.upper() or 'lượng' in product_name.lower()):
                    buy_text = cells[2].get_text(strip=True).replace(',', '').replace('.', '')
                    sell_text = cells[3].get_text(strip=True).replace(',', '').replace('.', '')
                    if buy_text and sell_text:
                        buy_price_pq = float(buy_text)
                        sell_price_pq = float(sell_text)
                        print(f"  Found: {product_name}")
                        break

    if buy_price_pq and sell_price_pq:
        crawl_time = datetime.now()

        with engine.connect() as conn:
            # Check duplicate for this source
            result = conn.execute(
                text("""SELECT COUNT(*) FROM vn_macro_silver_daily
                        WHERE date = :date AND source = 'phuquygroup.vn'
                        AND crawl_time >= :s AND crawl_time < :e"""),
                {
                    'date': date_str,
                    's': crawl_time.replace(minute=0, second=0, microsecond=0),
                    'e': crawl_time.replace(minute=59, second=59, microsecond=999999)
                }
            )
            if result.scalar() > 0:
                print(f"  Silver (phuquygroup.vn) for {date_str} this hour already exists")
            else:
                conn.execute(
                    text("""INSERT INTO vn_macro_silver_daily (date, crawl_time, buy_price, sell_price, source, group_name)
                            VALUES (:date, :crawl_time, :buy_price, :sell_price, 'phuquygroup.vn', 'commodity')"""),
                    {'date': date_str, 'crawl_time': crawl_time, 'buy_price': buy_price_pq, 'sell_price': sell_price_pq}
                )
                conn.commit()
                print(f"  Pushed backup silver: Buy {buy_price_pq:,.0f} | Sell {sell_price_pq:,.0f}")
    else:
        print(f"  No silver price found on phuquygroup.vn")

except Exception as e:
    print(f"  Error crawling phuquygroup silver: {e}")


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
                        SELECT COUNT(*) FROM vn_macro_gold_daily
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
                        INSERT INTO vn_macro_gold_daily (date, type, buy_price, sell_price, crawl_time, source, group_name)
                        VALUES (:date, :type, :buy_price, :sell_price, :crawl_time, '24h.com.vn', 'commodity')
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

# global_failed stays True until we successfully retrieve & persist data.
# It drives a non-zero exit at the end of the script so a silent yfinance
# outage (Yahoo rate-limits GitHub Actions IPs) turns the workflow RED instead
# of green-but-stale. See freshness guard in data-quality-check.yml.
global_failed = True
try:
    import yfinance as yf

    TICKERS = {
        'gold_price': 'GC=F',
        'silver_price': 'SI=F',
        'nasdaq_price': '^IXIC',
        'sp500_price': '^GSPC',
        'dowjones_price': '^DJI',
    }
    max_retries = 3
    retry_delay = 5

    # col -> { 'YYYY-MM-DD': close } across the whole returned window, so a run
    # that recovers after a gap backfills every missing trading day (not only today).
    series = {}
    for col, sym in TICKERS.items():
        for attempt in range(max_retries):
            try:
                hist = yf.Ticker(sym).history(period="1mo")
                if not hist.empty:
                    series[col] = {
                        idx.date().isoformat(): float(close)
                        for idx, close in hist['Close'].items()
                        if pd.notna(close)
                    }
                    print(f"  {sym}: {len(series[col])} days, latest {hist['Close'].iloc[-1]:.2f}")
                else:
                    print(f"  {sym}: empty response")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  Retry {attempt + 1}/{max_retries} for {sym}: {e}")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    raise
            finally:
                time.sleep(2)

    all_dates = sorted({d for s in series.values() for d in s})
    if not all_dates:
        raise RuntimeError("yfinance returned no data for any ticker (likely rate-limited)")

    inserted = 0
    with global_indicator_engine.connect() as conn:
        for d in all_dates:
            exists = conn.execute(
                text("SELECT COUNT(*) FROM global_macro WHERE date = :d"), {'d': d}
            ).scalar() > 0
            if exists:
                continue
            row = {
                'date': pd.to_datetime(d),
                'crawl_time': datetime.now(),
                'gold_price': series.get('gold_price', {}).get(d),
                'silver_price': series.get('silver_price', {}).get(d),
                'nasdaq_price': series.get('nasdaq_price', {}).get(d),
                'sp500_price': series.get('sp500_price', {}).get(d),
                'dowjones_price': series.get('dowjones_price', {}).get(d),
                'source': 'Yahoo Finance',
                'group_name': 'commodity',
            }
            pd.DataFrame([row]).to_sql('global_macro', global_indicator_engine,
                                       if_exists='append', index=False)
            inserted += 1
            print(f"  Inserted global macro for {d}")

    print(f"  Global macro: {inserted} new row(s), latest available {all_dates[-1]}")
    global_failed = False  # got real data and persisted it

except ImportError:
    print(f"  yfinance not installed — cannot crawl global macro")
except Exception as e:
    print(f"  ERROR crawling global macro: {e}")


print(f"\n{'='*60}")
print(f"Gold & Silver Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")

# Gold/silver are already persisted above; fail loudly only on the global section
# so a stale Yahoo Finance feed surfaces as a red workflow instead of passing silently.
if global_failed:
    print("\n❌ Global macro (Yahoo Finance) crawl failed — exiting non-zero to flag staleness")
    sys.exit(1)
