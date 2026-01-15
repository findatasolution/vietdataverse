import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import requests
import json
from sqlalchemy import create_engine
from bs4 import BeautifulSoup
import time
from datetime import datetime
from sqlalchemy import text
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

############## Domestic Silver Prices - crawl with Selenium
try:
    # Setup headless Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.binary_location = '/usr/bin/chromium-browser' if sys.platform == 'linux' else None

    driver = webdriver.Chrome(options=chrome_options)
    buy_price = None
    sell_price = None

    try:
        driver.get("https://giabac.vn/")
        time.sleep(2)  # Wait for page load

        # Click "Lượng" button to filter by unit
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            if "Lượng" in btn.text or "luong" in btn.text.lower():
                btn.click()
                time.sleep(2)  # Wait for price update
                break

        # Get price from priceDiv
        price_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "priceDiv"))
        )
        price_elements = price_div.find_elements(By.CSS_SELECTOR, "p.text-24px")

        if len(price_elements) >= 2:
            buy_text = price_elements[0].text.strip().replace(',', '').replace('.', '')
            sell_text = price_elements[1].text.strip().replace(',', '').replace('.', '')
            buy_price = float(buy_text)
            sell_price = float(sell_text)

    finally:
        driver.quit()

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
            print(f"⚠️  Silver data for {date_str} {crawl_time.strftime('%H:%M')} already exists")
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
            print(f"✅ Pushed silver: {crawl_time.strftime('%H:%M')} | Buy {buy_price:,.0f} | Sell {sell_price:,.0f}")
    else:
        print(f"❌ No silver price found in div#priceDiv")

except Exception as e:
    print(f"❌ Error crawling Silver: {e}")

############## Domestic Gold Price - All brands
url_gold = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'

try:
    response_gold = requests.get(url_gold, timeout=10)
    response_gold.raise_for_status()
    soup_gold = BeautifulSoup(response_gold.content, 'html.parser')

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
                        'sell_price': sell_price
                    })
                except (ValueError, AttributeError):
                    continue

    if gold_records:
        print(f"✅ Crawled {len(gold_records)} gold brands for {date_str}")

        inserted = 0
        skipped = 0

        for record in gold_records:
            with engine.connect() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM vn_gold_24h_hist WHERE date = :date AND type = :type"),
                    {'date': record['date'], 'type': record['type']}
                )

                if result.scalar() > 0:
                    skipped += 1
                    continue

                conn.execute(
                    text("""
                        INSERT INTO vn_gold_24h_hist (date, type, buy_price, sell_price)
                        VALUES (:date, :type, :buy_price, :sell_price)
                    """),
                    record
                )
                conn.commit()
                inserted += 1

        print(f"✅ Pushed {inserted} gold records, skipped {skipped}")
    else:
        print(f"❌ No gold data found for {date_str}")

except Exception as e:
    print(f"❌ Error crawling gold prices: {e}")

############## SBV interbank
api_url = 'https://sbv.gov.vn/o/headless-delivery/v1.0/content-structures/3450260/structured-contents?pageSize=1&sort=datePublished:desc'

try:
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    api_data = response.json()

    if api_data and 'items' in api_data and len(api_data['items']) > 0:
        latest_item = api_data['items'][0]

        # Get date from ngayApDung field (this is the actual application date)
        sbv_date = None
        content_fields = latest_item.get('contentFields', [])
        for field in content_fields:
            if field.get('name') == 'ngayApDung':
                date_value = field.get('contentFieldValue', {}).get('data', '')
                # Format: 2025-12-23T17:00:00Z -> convert to local date
                sbv_date = date_value.split('T')[0]  # Extract YYYY-MM-DD
                # Adjust for timezone (Vietnam is UTC+7)
                from datetime import datetime, timedelta
                date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                # Convert to Vietnam time
                vn_date = date_obj + timedelta(hours=7)
                sbv_date = vn_date.strftime('%Y-%m-%d')
                break

        if not sbv_date:
            print("❌ Could not find ngayApDung field")
        else:
            # Check if this date matches today
            if sbv_date == date_str:
                print(f"⚠️  SBV interbank rate for {sbv_date} already matches today, no changes")
            else:
                print(f"✅ New SBV interbank rate date found: {sbv_date}")

                # Parse content fields
                interbank_data = {
                    'date': sbv_date,
                    'crawl_time': datetime.now()
                }

                # Term mapping to column names
                term_mapping = {
                    'Qua đêm': 'quadem',
                    '1 Tuần': '1w',
                    '2 Tuần': '2w',
                    '1 Tháng': '1m',
                    '3 Tháng': '3m',
                    '6 Tháng': '6m',
                    '9 Tháng': '9m'
                }

                for field in content_fields:
                    if field.get('name') == 'laiSuatThiTruongNganHangs':
                        # Each field is one timeframe (overnight, 1 week, etc.)
                        thoihan = None
                        laisuat = None
                        doanhso = None

                        nested_fields = field.get('nestedContentFields', [])
                        for nested_field in nested_fields:
                            field_name = nested_field.get('name', '')
                            field_value = nested_field.get('contentFieldValue', {}).get('data', '')

                            if field_name == 'thoihan':
                                thoihan = field_value
                            elif field_name == 'laiSuatBQLienNganHang':
                                try:
                                    laisuat = float(str(field_value).replace(',', '.')) if field_value else None
                                except (ValueError, TypeError):
                                    laisuat = None
                            elif field_name == 'doanhSo':
                                try:
                                    doanhso = float(str(field_value).replace(',', '.')) if field_value else None
                                except (ValueError, TypeError):
                                    doanhso = None

                        # Map to column names
                        if thoihan in term_mapping:
                            col_name = term_mapping[thoihan]
                            interbank_data[f'ls_{col_name}'] = laisuat
                            interbank_data[f'doanhso_{col_name}'] = doanhso

                print(f"Debug - Crawled data: {interbank_data}")

                # Create DataFrame and insert
                interbank_df = pd.DataFrame([interbank_data])
                interbank_df['date'] = pd.to_datetime(interbank_df['date'])

                # Check if date already exists
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT COUNT(*) FROM vn_sbv_interbankrate WHERE date = '{sbv_date}'"))
                    exists = result.scalar() > 0

                if exists:
                    print(f"⚠️  SBV interbank rate for {sbv_date} already exists, skipping insert")
                else:
                    interbank_df.to_sql('vn_sbv_interbankrate', engine, if_exists='append', index=False)
                    print(f"✅ Pushed SBV interbank rate for {sbv_date}")
    else:
        print("❌ No data returned from SBV API")

except Exception as e:
    print(f"❌ Error crawling SBV interbank rate: {e}")

############## Bank Term Deposit Rates
# Note: Vietcombank website requires JavaScript rendering,
# skipped for now (would need Selenium/Playwright)

# ACB
try:
    acb_url = 'https://acb.com.vn/lai-suat-tien-gui'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(acb_url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    acb_data = {
        'bank_code': 'ACB',
        'date': date_str,
        'crawl_time': datetime.now()
    }

    tables = soup.find_all('table')

    # ACB uses Table 2 for term deposit rates (based on website structure analysis)
    if len(tables) >= 3:
        table = tables[2]
        rows = table.find_all('tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                term_text = str(cols[0].get_text(strip=True)).upper()

                # Skip header rows
                if 'THÁNG' in term_text.upper() and 'TRUYỀN' in term_text.upper():
                    continue
                if 'LÃI' in term_text.upper() and 'KỲ' in term_text.upper():
                    continue

                # Get VND rate from column 2 onwards (skip USD column)
                rate_text = None
                for col_idx in range(2, len(cols)):
                    text_content = str(cols[col_idx].get_text(strip=True))
                    # Skip headers and empty cells
                    if text_content and text_content not in ['', '-', 'VND', 'USD', 'Lãicuối kỳ', 'Lãiquý', 'Lãitháng', 'Lãi trả trước', 'Tích LũyTương Lai']:
                        rate_text = text_content
                        break

                if not rate_text:
                    continue

                try:
                    # Remove asterisks and special characters before parsing
                    clean_rate = rate_text.replace('*', '').replace(',', '.').replace('%', '').strip()
                    rate = float(clean_rate)

                    # ACB uses format: 1T, 2T, 3T, 6T, 9T, 12T, etc.
                    if term_text == '1T':
                        acb_data['term_1m'] = rate
                    elif term_text == '2T':
                        acb_data['term_2m'] = rate
                    elif term_text == '3T':
                        acb_data['term_3m'] = rate
                    elif term_text == '6T':
                        acb_data['term_6m'] = rate
                    elif term_text == '9T':
                        acb_data['term_9m'] = rate
                    elif term_text == '12T':
                        acb_data['term_12m'] = rate
                    elif term_text == '13T':
                        acb_data['term_13m'] = rate
                    elif term_text in ['15T', '18T']:
                        acb_data['term_18m'] = rate
                    elif term_text == '24T':
                        acb_data['term_24m'] = rate
                    elif term_text == '36T':
                        acb_data['term_36m'] = rate

                except (ValueError, AttributeError, TypeError):
                    continue

    has_data = any(key.startswith('term_') for key in acb_data.keys())

    if has_data:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'ACB' AND date = '{date_str}'"))
            exists = result.scalar() > 0

        if exists:
            print(f"⚠️  ACB term deposit data for {date_str} already exists, skipping insert")
        else:
            acb_df = pd.DataFrame([acb_data])
            acb_df['date'] = pd.to_datetime(acb_df['date'])
            acb_df.to_sql('vn_bank_termdepo', engine, if_exists='append', index=False)
            print(f"✅ Pushed ACB term deposit rates for {date_str}")
            rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in acb_data.items() if k.startswith('term_')]
            print(f"   Rates: {rates_list}")
    else:
        print(f"⚠️  No ACB term deposit data found (website may have changed structure)")

except Exception as e:
    print(f"❌ Error crawling ACB term deposit: {e}")


############## Global Macro Data from Yahoo Finance
print("\n" + "="*60)
print("Crawling Global Macro Data from Yahoo Finance")
print("="*60)

try:
    import yfinance as yf

    # Define tickers
    # GC=F: Gold Futures ($/oz)
    # SI=F: Silver Futures ($/oz)
    # ^IXIC: NASDAQ Composite Index
    tickers = {
        'gold': 'GC=F',      # Gold Futures
        'silver': 'SI=F',    # Silver Futures
        'nasdaq': '^IXIC'    # NASDAQ Composite
    }

    global_macro_data = {
        'date': date_str,
        'crawl_time': datetime.now(),
        'gold_price': None,
        'silver_price': None,
        'nasdaq_price': None
    }

    # Helper function to fetch with retry logic
    def fetch_with_retry(ticker_symbol, max_retries=3, initial_delay=2):
        """Fetch ticker data with exponential backoff retry"""
        for attempt in range(max_retries):
            try:
                ticker = yf.Ticker(ticker_symbol)
                hist = ticker.history(period='1d')
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
                else:
                    print(f"    Attempt {attempt + 1}/{max_retries}: No data returned for {ticker_symbol}")
            except Exception as e:
                error_msg = str(e)
                if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
                    if attempt < max_retries - 1:
                        delay = initial_delay * (2 ** attempt)  # Exponential backoff
                        print(f"    Rate limited, waiting {delay}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"Rate limited after {max_retries} attempts")
                else:
                    raise e
        return None

    # Fetch gold price with retry
    try:
        print("  Fetching Gold Futures (GC=F)...")
        gold_price = fetch_with_retry(tickers['gold'])
        if gold_price:
            global_macro_data['gold_price'] = gold_price
            print(f"  ✅ Gold (GC=F): ${global_macro_data['gold_price']:.2f}/oz")
        else:
            print(f"  ⚠️  No gold price data available")
    except Exception as e:
        print(f"  ❌ Failed to fetch gold price: {e}")

    # Wait between requests to avoid rate limiting
    time.sleep(1)

    # Fetch silver price with retry
    try:
        print("  Fetching Silver Futures (SI=F)...")
        silver_price = fetch_with_retry(tickers['silver'])
        if silver_price:
            global_macro_data['silver_price'] = silver_price
            print(f"  ✅ Silver (SI=F): ${global_macro_data['silver_price']:.2f}/oz")
        else:
            print(f"  ⚠️  No silver price data available")
    except Exception as e:
        print(f"  ❌ Failed to fetch silver price: {e}")

    # Wait between requests to avoid rate limiting
    time.sleep(1)

    # Fetch NASDAQ price with retry
    try:
        print("  Fetching NASDAQ Composite (^IXIC)...")
        nasdaq_price = fetch_with_retry(tickers['nasdaq'])
        if nasdaq_price:
            global_macro_data['nasdaq_price'] = nasdaq_price
            print(f"  ✅ NASDAQ (^IXIC): {global_macro_data['nasdaq_price']:,.2f}")
        else:
            print(f"  ⚠️  No NASDAQ price data available")
    except Exception as e:
        print(f"  ❌ Failed to fetch NASDAQ price: {e}")

    # Check if we have at least one data point
    has_data = any(global_macro_data[key] is not None for key in ['gold_price', 'silver_price', 'nasdaq_price'])

    if has_data:
        # Check if data already exists for today
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM global_macro WHERE date = '{date_str}'"))
            exists = result.scalar() > 0

        if exists:
            print(f"⚠️  Global macro data for {date_str} already exists, skipping insert")
        else:
            # Insert into database
            macro_df = pd.DataFrame([global_macro_data])
            macro_df['date'] = pd.to_datetime(macro_df['date'])
            macro_df.to_sql('global_macro', engine, if_exists='append', index=False)
            print(f"✅ Pushed global macro data for {date_str}")
    else:
        print(f"⚠️  No global macro data fetched")

except ImportError:
    print("❌ yfinance library not installed. Run: pip install yfinance")
except Exception as e:
    print(f"❌ Error crawling global macro data: {e}")