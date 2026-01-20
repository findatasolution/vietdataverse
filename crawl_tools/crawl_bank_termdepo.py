"""
Bank Term Deposit Rates Crawler
Runs weekly: Every Monday at 9:00 AM VN
- ACB (HTTP)
- VietinBank/CTG (HTTP)
- Vietcombank/VCB (Selenium)
- TCB, MBB, VPB: Disabled (React/Angular SPA)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup
import time
import re
import unicodedata
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawler - {date_str}")
print(f"{'='*60}")

# Database connection
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


############## 1. ACB Bank (HTTP)
print(f"\n--- Crawling ACB Term Deposit Rates ---")

try:
    acb_url = 'https://acb.com.vn/lai-suat-tien-gui'
    response = requests.get(acb_url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    acb_data = {
        'bank_code': 'ACB',
        'date': date_str,
        'crawl_time': datetime.now()
    }

    tables = soup.find_all('table')

    if len(tables) >= 3:
        table = tables[2]
        rows = table.find_all('tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                term_text = str(cols[0].get_text(strip=True)).upper()

                if 'THÁNG' in term_text.upper() and 'TRUYỀN' in term_text.upper():
                    continue
                if 'LÃI' in term_text.upper() and 'KỲ' in term_text.upper():
                    continue

                rate_text = None
                for col_idx in range(2, len(cols)):
                    text_content = str(cols[col_idx].get_text(strip=True))
                    if text_content and text_content not in ['', '-', 'VND', 'USD', 'Lãicuối kỳ', 'Lãiquý', 'Lãitháng', 'Lãi trả trước', 'Tích LũyTương Lai']:
                        rate_text = text_content
                        break

                if not rate_text:
                    continue

                try:
                    clean_rate = rate_text.replace('*', '').replace(',', '.').replace('%', '').strip()
                    rate = float(clean_rate)

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
            result = conn.execute(text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'ACB' AND date = :date"), {'date': date_str})
            exists = result.scalar() > 0

            if exists:
                print(f"  ACB term deposit data for {date_str} already exists, skipping")
            else:
                conn.execute(text("""
                    INSERT INTO vn_bank_termdepo (bank_code, date, crawl_time, term_1m, term_2m, term_3m, term_6m, term_9m, term_12m, term_13m, term_18m, term_24m, term_36m)
                    VALUES (:bank_code, :date, :crawl_time, :term_1m, :term_2m, :term_3m, :term_6m, :term_9m, :term_12m, :term_13m, :term_18m, :term_24m, :term_36m)
                """), acb_data)
                conn.commit()
                rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in acb_data.items() if k.startswith('term_')]
                print(f"  Pushed ACB rates: {rates_list}")
    else:
        print(f"  No ACB term deposit data found")

except Exception as e:
    print(f"  Error crawling ACB: {e}")


############## 2. Disabled banks notice
print(f"\n--- TCB, MBB, VPB: DISABLED ---")
print("  Techcombank (TCB): React SPA - no public API")
print("  MB Bank (MBB): AngularJS with dynamic content")
print("  VPBank (VPB): React SPA - no public API")


############## 3. VietinBank/CTG (HTTP - parse table directly)
print(f"\n--- Crawling VietinBank Term Deposit Rates ---")

try:
    ctg_url = 'https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn'

    response = requests.get(ctg_url, headers=headers, timeout=15)
    response.raise_for_status()
    soup_ctg = BeautifulSoup(response.content, 'html.parser')

    ctg_data = {
        'bank_code': 'CTG',
        'date': date_str,
        'crawl_time': datetime.now()
    }

    tables = soup_ctg.find_all('table')
    print(f"  Found {len(tables)} tables")

    # Parse first table (interest rate table)
    if tables:
        table = tables[0]
        rows = table.find_all('tr')

        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                # Normalize text: Unicode NFC, replace non-breaking space, lowercase
                term_text = unicodedata.normalize('NFC', cols[0].get_text(strip=True)).replace('\xa0', ' ').lower()
                rate_text = cols[1].get_text(strip=True)  # VND column

                # Extract rate value
                try:
                    rate = float(rate_text.replace('%', '').replace(',', '.').strip())
                except (ValueError, AttributeError):
                    continue

                if rate <= 0 or rate > 20:
                    continue

                # Map term text to database columns using exact patterns
                # Row 1: "Không kỳ hạn" -> term_noterm
                if term_text == 'không kỳ hạn':
                    ctg_data['term_noterm'] = rate
                    print(f"    term_noterm: {rate}%")
                # Row 3: "Từ 1 tháng đến dưới 2 tháng" -> term_1m
                elif term_text.startswith('từ 1 tháng') and 'dưới 2 tháng' in term_text:
                    ctg_data['term_1m'] = rate
                    print(f"    term_1m: {rate}%")
                # Row 4: "Từ 2 tháng đến dưới 3 tháng" -> term_2m
                elif term_text.startswith('từ 2 tháng') and 'dưới 3 tháng' in term_text:
                    ctg_data['term_2m'] = rate
                    print(f"    term_2m: {rate}%")
                # Row 5: "Từ 3 tháng đến dưới 4 tháng" -> term_3m
                elif term_text.startswith('từ 3 tháng') and 'dưới 4 tháng' in term_text:
                    ctg_data['term_3m'] = rate
                    print(f"    term_3m: {rate}%")
                # Row 8: "Từ 6 tháng đến dưới 7 tháng" -> term_6m
                elif term_text.startswith('từ 6 tháng') and 'dưới 7 tháng' in term_text:
                    ctg_data['term_6m'] = rate
                    print(f"    term_6m: {rate}%")
                # Row 11: "Từ 9 tháng đến dưới 10 tháng" -> term_9m
                elif term_text.startswith('từ 9 tháng') and 'dưới 10 tháng' in term_text:
                    ctg_data['term_9m'] = rate
                    print(f"    term_9m: {rate}%")
                # Row 14: "12 tháng" (exact) -> term_12m
                elif term_text == '12 tháng':
                    ctg_data['term_12m'] = rate
                    print(f"    term_12m: {rate}%")
                # Row 15: "Trên 12 tháng đến 13 tháng" -> term_13m
                elif term_text.startswith('trên 12 tháng') and '13 tháng' in term_text:
                    ctg_data['term_13m'] = rate
                    print(f"    term_13m: {rate}%")
                # Row 17: "Từ 18 tháng đến dưới 24 tháng" -> term_18m
                elif term_text.startswith('từ 18 tháng'):
                    ctg_data['term_18m'] = rate
                    print(f"    term_18m: {rate}%")
                # Row 18: "Từ 24 tháng đến dưới 36 tháng" -> term_24m
                elif term_text.startswith('từ 24 tháng'):
                    ctg_data['term_24m'] = rate
                    print(f"    term_24m: {rate}%")
                # Row 19: "36 tháng" (exact) -> term_36m
                elif term_text == '36 tháng':
                    ctg_data['term_36m'] = rate
                    print(f"    term_36m: {rate}%")

    has_ctg_data = any(key.startswith('term_') for key in ctg_data.keys())

    if has_ctg_data:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'CTG' AND date = :date"), {'date': date_str})
            exists = result.scalar() > 0

            if exists:
                print(f"  VietinBank data for {date_str} already exists, skipping")
            else:
                # Build dynamic insert based on available columns
                columns = ['bank_code', 'date', 'crawl_time'] + [k for k in ctg_data.keys() if k.startswith('term_')]
                placeholders = ', '.join([f':{c}' for c in columns])
                col_names = ', '.join(columns)
                conn.execute(text(f"INSERT INTO vn_bank_termdepo ({col_names}) VALUES ({placeholders})"), ctg_data)
                conn.commit()
                rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in ctg_data.items() if k.startswith('term_')]
                print(f"  Pushed VietinBank rates: {rates_list}")
    else:
        print(f"  No VietinBank term deposit data found")

except Exception as e:
    print(f"  Error crawling VietinBank: {e}")


############## 4. Vietcombank/VCB (Selenium required)
print(f"\n--- Crawling Vietcombank Term Deposit Rates ---")

try:
    chrome_options_vcb = Options()
    chrome_options_vcb.add_argument('--headless')
    chrome_options_vcb.add_argument('--no-sandbox')
    chrome_options_vcb.add_argument('--disable-dev-shm-usage')
    chrome_options_vcb.add_argument('--disable-gpu')
    if sys.platform == 'linux':
        chrome_options_vcb.binary_location = '/usr/bin/chromium-browser'

    driver_vcb = webdriver.Chrome(options=chrome_options_vcb)

    vcb_data = {
        'bank_code': 'VCB',
        'date': date_str,
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
        print("  Loading Vietcombank page (20s wait)...")
        driver_vcb.get("https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat")
        time.sleep(20)

        soup_vcb = BeautifulSoup(driver_vcb.page_source, 'html.parser')
        text_content = soup_vcb.get_text()

        # No-term rate
        noterm_match = re.search(r'Không kỳ hạn.*?(\d+[.,]\d+)\s*%?', text_content, re.IGNORECASE)
        if noterm_match:
            try:
                rate = float(noterm_match.group(1).replace(',', '.'))
                if 0 < rate < 20:
                    vcb_data['term_noterm'] = rate
            except ValueError:
                pass

        # Term patterns
        term_patterns = {
            'term_1m': r'1\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_2m': r'2\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_3m': r'3\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_6m': r'6\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_9m': r'9\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_12m': r'12\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_13m': r'13\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_18m': r'18\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_24m': r'24\s*tháng[^\d]*(\d+[.,]\d+)',
            'term_36m': r'36\s*tháng[^\d]*(\d+[.,]\d+)',
        }

        for key, pattern in term_patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        vcb_data[key] = rate
                except ValueError:
                    pass

    finally:
        driver_vcb.quit()

    has_vcb_data = any(value is not None for key, value in vcb_data.items() if key.startswith('term_'))

    if has_vcb_data:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'VCB' AND date = :date"), {'date': date_str})
            exists = result.scalar() > 0

            if exists:
                print(f"  Vietcombank data for {date_str} already exists, skipping")
            else:
                # Filter out None values and build insert
                insert_data = {k: v for k, v in vcb_data.items() if v is not None or k in ['bank_code', 'date', 'crawl_time']}
                columns = list(insert_data.keys())
                placeholders = ', '.join([f':{c}' for c in columns])
                col_names = ', '.join(columns)
                conn.execute(text(f"INSERT INTO vn_bank_termdepo ({col_names}) VALUES ({placeholders})"), insert_data)
                conn.commit()
                rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in vcb_data.items() if k.startswith('term_') and v is not None]
                print(f"  Pushed Vietcombank rates: {rates_list}")
    else:
        print(f"  No Vietcombank term deposit data found")

except Exception as e:
    print(f"  Error crawling Vietcombank: {e}")


print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")