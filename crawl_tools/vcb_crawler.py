"""
Vietcombank Term Deposit Rates Crawler
Fetches VND term deposit rates from VCB website using Selenium
Runs weekly via GitHub Actions
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
import pandas as pd

# Database connection
conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str,
                      pool_size=5,
                      max_overflow=10,
                      pool_timeout=10,
                      pool_recycle=300,
                      pool_pre_ping=True)

print("=" * 60)
print("Vietcombank Term Deposit Rates Crawler")
print("=" * 60)

# Selenium setup
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
if sys.platform == 'linux':
    chrome_options.binary_location = '/usr/bin/chromium-browser'

driver = webdriver.Chrome(options=chrome_options)

vcb_data = {
    'bank_code': 'VCB',
    'date': datetime.now().strftime('%Y-%m-%d'),
    'crawl_time': datetime.now(),
    'term_noterm': None,
    'term_1m': None,
    'term_2m': None,
    'term_3m': None,
    'term_6m': None,
    'term_9m': None,
    'term_12m': None,
    'term_13m': None,
    'term_18m': None,
    'term_24m': None,
    'term_36m': None
}

try:
    print("\n1. Loading VCB interest rates page...")
    driver.get("https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat")

    # Wait for page to fully load with longer timeout
    print("2. Waiting for page content to render (30 seconds)...")
    time.sleep(30)  # VCB is very slow, wait longer

    # Try multiple strategies to find the rate table
    print("3. Searching for interest rate data...")

    # Strategy 1: Look for table with specific text
    try:
        rate_table = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//table[contains(., 'Tiết kiệm') or contains(., 'Không kỳ hạn')]"))
        )
        print("✅ Found rate table using Strategy 1")
    except:
        print("⚠️  Strategy 1 failed, trying Strategy 2...")

        # Strategy 2: Look for divs/sections containing rate info
        try:
            rate_section = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'rate') or contains(@class, 'interest')]"))
            )
            print("✅ Found rate section using Strategy 2")
        except:
            print("⚠️  Strategy 2 failed, trying Strategy 3...")

            # Strategy 3: Just parse all content
            rate_section = driver.find_element(By.TAG_NAME, "body")
            print("⚠️  Using full page content (Strategy 3)")

    # Parse the page source
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Look for tables
    tables = soup.find_all('table')
    print(f"4. Found {len(tables)} tables on page")

    if len(tables) == 0:
        # Try to find data in divs/spans
        print("5. No tables found, searching for rate data in text...")

        # Look for patterns like "1 tháng: 2.0%", "3 tháng: 3.0%"
        text_content = soup.get_text()

        # Parse for Vietnamese rate patterns
        import re

        # Pattern: "Không kỳ hạn" followed by rate
        noterm_match = re.search(r'Không kỳ hạn.*?(\d+[.,]\d+)\s*%', text_content, re.IGNORECASE)
        if noterm_match:
            vcb_data['term_noterm'] = float(noterm_match.group(1).replace(',', '.'))
            print(f"   Found No-term: {vcb_data['term_noterm']}%")

        # Pattern: "1 tháng" followed by rate
        patterns = {
            'term_1m': r'1\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_2m': r'2\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_3m': r'3\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_6m': r'6\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_9m': r'9\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_12m': r'12\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_18m': r'18\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_24m': r'24\s*tháng.*?(\d+[.,]\d+)\s*%',
            'term_36m': r'36\s*tháng.*?(\d+[.,]\d+)\s*%',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                vcb_data[key] = float(match.group(1).replace(',', '.'))
                print(f"   Found {key}: {vcb_data[key]}%")

    else:
        # Parse tables
        print("5. Parsing tables for VND term deposit rates...")

        for table_idx, table in enumerate(tables):
            rows = table.find_all('tr')
            print(f"\n   Table {table_idx}: {len(rows)} rows")

            for row_idx, row in enumerate(rows):
                cols = row.find_all(['td', 'th'])
                if len(cols) >= 2:
                    term_text = cols[0].get_text(strip=True).upper()

                    # Skip headers
                    if 'KỲ HẠN' in term_text or 'LÃI SUẤT' in term_text:
                        continue

                    # Find VND rate (usually 2nd or 3rd column)
                    rate_value = None
                    for col_idx in range(1, len(cols)):
                        col_text = cols[col_idx].get_text(strip=True)
                        # Look for number with % or decimal
                        if any(char.isdigit() for char in col_text):
                            # Clean and extract rate
                            clean_text = col_text.replace('%', '').replace(',', '.').replace('*', '').strip()
                            try:
                                rate_value = float(clean_text)
                                break
                            except ValueError:
                                continue

                    if rate_value is None:
                        continue

                    # Map term to database column
                    if 'KHÔNG KỲ HẠN' in term_text or 'KHÔNG THỜ' in term_text:
                        vcb_data['term_noterm'] = rate_value
                        print(f"      No-term: {rate_value}%")
                    elif '1 THÁNG' in term_text or '1T' == term_text:
                        vcb_data['term_1m'] = rate_value
                        print(f"      1M: {rate_value}%")
                    elif '2 THÁNG' in term_text or '2T' == term_text:
                        vcb_data['term_2m'] = rate_value
                        print(f"      2M: {rate_value}%")
                    elif '3 THÁNG' in term_text or '3T' == term_text:
                        vcb_data['term_3m'] = rate_value
                        print(f"      3M: {rate_value}%")
                    elif '6 THÁNG' in term_text or '6T' == term_text:
                        vcb_data['term_6m'] = rate_value
                        print(f"      6M: {rate_value}%")
                    elif '9 THÁNG' in term_text or '9T' == term_text:
                        vcb_data['term_9m'] = rate_value
                        print(f"      9M: {rate_value}%")
                    elif '12 THÁNG' in term_text or '12T' == term_text:
                        vcb_data['term_12m'] = rate_value
                        print(f"      12M: {rate_value}%")
                    elif '13 THÁNG' in term_text or '13T' == term_text:
                        vcb_data['term_13m'] = rate_value
                        print(f"      13M: {rate_value}%")
                    elif '18 THÁNG' in term_text or '18T' == term_text:
                        vcb_data['term_18m'] = rate_value
                        print(f"      18M: {rate_value}%")
                    elif '24 THÁNG' in term_text or '24T' == term_text:
                        vcb_data['term_24m'] = rate_value
                        print(f"      24M: {rate_value}%")
                    elif '36 THÁNG' in term_text or '36T' == term_text:
                        vcb_data['term_36m'] = rate_value
                        print(f"      36M: {rate_value}%")

    # Check if we found any data
    has_data = any(value is not None for key, value in vcb_data.items() if key.startswith('term_'))

    if has_data:
        print("\n6. Checking if data already exists in database...")
        date_str = vcb_data['date']

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'VCB' AND date = :date"),
                {'date': date_str}
            )
            exists = result.scalar() > 0

        if exists:
            print(f"⚠️  VCB term deposit data for {date_str} already exists, skipping insert")
        else:
            print("7. Inserting data into database...")
            vcb_df = pd.DataFrame([vcb_data])
            vcb_df['date'] = pd.to_datetime(vcb_df['date'])
            vcb_df.to_sql('vn_bank_termdepo', engine, if_exists='append', index=False)

            print(f"✅ Successfully pushed VCB term deposit rates for {date_str}")

            # Print summary
            rates_list = []
            if vcb_data['term_noterm']:
                rates_list.append(f"NoTerm: {vcb_data['term_noterm']}%")
            for key in ['term_1m', 'term_2m', 'term_3m', 'term_6m', 'term_9m', 'term_12m', 'term_13m', 'term_18m', 'term_24m', 'term_36m']:
                if vcb_data[key]:
                    rates_list.append(f"{key.replace('term_', '').upper()}: {vcb_data[key]}%")
            print(f"   Rates: {', '.join(rates_list)}")
    else:
        print("\n❌ No VCB term deposit data found")
        print("   This may indicate:")
        print("   - Website structure has changed")
        print("   - Page did not load completely")
        print("   - Selectors need to be updated")

        # Save debug HTML
        with open('vcb_debug_failed.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("   Saved page source to vcb_debug_failed.html for debugging")

except Exception as e:
    print(f"\n❌ Error crawling VCB: {e}")
    import traceback
    traceback.print_exc()

    # Save debug info
    try:
        with open('vcb_error_debug.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("   Saved error page source to vcb_error_debug.html")
    except:
        pass

finally:
    print("\n8. Cleaning up...")
    driver.quit()
    print("✅ VCB crawler completed")
    print("=" * 60)
