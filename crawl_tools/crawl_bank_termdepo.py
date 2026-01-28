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


############## 2. SHB Bank (HTTP - table works directly)
print(f"\n--- Crawling SHB Term Deposit Rates ---")

try:
    shb_url = 'https://ibanking.shb.com.vn/Rate/TideRate'
    response = requests.get(shb_url, headers=headers, timeout=15)
    response.raise_for_status()
    soup_shb = BeautifulSoup(response.content, 'html.parser')

    shb_data = {
        'bank_code': 'SHB',
        'date': date_str,
        'crawl_time': datetime.now()
    }

    tables = soup_shb.find_all('table')
    print(f"  Found {len(tables)} tables")

    if tables:
        table = tables[0]
        rows = table.find_all('tr')

        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                # Normalize and clean term text (format: "1 \r\nTháng")
                term_text = unicodedata.normalize('NFC', cols[0].get_text(strip=True)).replace('\xa0', ' ').replace('\r', '').replace('\n', ' ').lower()
                term_text = ' '.join(term_text.split())  # Normalize whitespace
                rate_text = cols[1].get_text(strip=True)  # VND column

                try:
                    rate = float(rate_text.replace('%', '').replace(',', '.').strip())
                except (ValueError, AttributeError):
                    continue

                if rate <= 0 or rate > 20:
                    continue

                # Map term text to database columns
                # SHB format: "1 tháng", "2 tháng", "12 tháng", etc.
                if term_text == '1 tháng':
                    shb_data['term_1m'] = rate
                    print(f"    term_1m: {rate}%")
                elif term_text == '2 tháng':
                    shb_data['term_2m'] = rate
                    print(f"    term_2m: {rate}%")
                elif term_text == '3 tháng':
                    shb_data['term_3m'] = rate
                    print(f"    term_3m: {rate}%")
                elif term_text == '6 tháng':
                    shb_data['term_6m'] = rate
                    print(f"    term_6m: {rate}%")
                elif term_text == '9 tháng':
                    shb_data['term_9m'] = rate
                    print(f"    term_9m: {rate}%")
                elif term_text == '12 tháng':
                    shb_data['term_12m'] = rate
                    print(f"    term_12m: {rate}%")
                elif term_text == '13 tháng':
                    shb_data['term_13m'] = rate
                    print(f"    term_13m: {rate}%")
                elif term_text == '18 tháng':
                    shb_data['term_18m'] = rate
                    print(f"    term_18m: {rate}%")
                elif term_text == '24 tháng':
                    shb_data['term_24m'] = rate
                    print(f"    term_24m: {rate}%")
                elif term_text == '36 tháng':
                    shb_data['term_36m'] = rate
                    print(f"    term_36m: {rate}%")

    has_shb_data = any(key.startswith('term_') for key in shb_data.keys())

    if has_shb_data:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'SHB' AND date = :date"), {'date': date_str})
            exists = result.scalar() > 0

            if exists:
                print(f"  SHB data for {date_str} already exists, skipping")
            else:
                columns = ['bank_code', 'date', 'crawl_time'] + [k for k in shb_data.keys() if k.startswith('term_')]
                placeholders = ', '.join([f':{c}' for c in columns])
                col_names = ', '.join(columns)
                conn.execute(text(f"INSERT INTO vn_bank_termdepo ({col_names}) VALUES ({placeholders})"), shb_data)
                conn.commit()
                rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in shb_data.items() if k.startswith('term_')]
                print(f"  Pushed SHB rates: {rates_list}")
    else:
        print(f"  No SHB term deposit data found")

except Exception as e:
    print(f"  Error crawling SHB: {e}")


############## Disabled banks notice
print(f"\n--- TCB, MBB, VPB, TPB: DISABLED ---")
print("  Techcombank (TCB): React SPA - no public API")
print("  MB Bank (MBB): AngularJS with dynamic content")
print("  VPBank (VPB): React SPA - no public API")
print("  TPBank (TPB): SPA with dynamic content")


############## 3. VietinBank/CTG (HTTP)
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


############## 4. Vietcombank/VCB (HTTP + JSON - No Selenium needed!)
print(f"\n--- Crawling Vietcombank Term Deposit Rates ---")

try:
    import json

    # VCB embeds rate data as JSON in a hidden input field
    vcb_url = "https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat"
    response = requests.get(vcb_url, headers=headers, timeout=30)
    response.raise_for_status()

    # Extract JSON from hidden input #currentDataInterestRate
    soup_vcb = BeautifulSoup(response.content, 'html.parser')
    json_input = soup_vcb.find('input', {'id': 'currentDataInterestRate'})

    vcb_data = {
        'bank_code': 'VCB',
        'date': date_str,
        'crawl_time': datetime.now()
    }

    if json_input and json_input.get('value'):
        rate_json = json.loads(json_input['value'])
        print(f"  Found {rate_json.get('Count', 0)} rate entries in JSON")

        # Map tenor to DB columns (only VND FixedDeposit rates)
        tenor_map = {
            'Demand': 'term_noterm',
            '1-months': 'term_1m',
            '2-months': 'term_2m',
            '3-months': 'term_3m',
            '6-months': 'term_6m',
            '9-months': 'term_9m',
            '12-months': 'term_12m',
            '18-months': 'term_18m',
            '24-months': 'term_24m',
            '36-months': 'term_36m'
        }

        for item in rate_json.get('Data', []):
            # Only get VND FixedDeposit rates
            if item.get('currencyCode') == 'VND' and item.get('tenorType') == 'FixedDeposit':
                tenor = item.get('tenor')
                rate = item.get('rates')

                if tenor in tenor_map and rate is not None:
                    # Convert from decimal (0.052) to percentage (5.2)
                    rate_pct = round(rate * 100, 2)
                    vcb_data[tenor_map[tenor]] = rate_pct
                    print(f"    {tenor_map[tenor]}: {rate_pct}%")

    has_vcb_data = any(key.startswith('term_') for key in vcb_data.keys())

    if has_vcb_data:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'VCB' AND date = :date"), {'date': date_str})
            exists = result.scalar() > 0

            if exists:
                print(f"  Vietcombank data for {date_str} already exists, skipping")
            else:
                columns = ['bank_code', 'date', 'crawl_time'] + [k for k in vcb_data.keys() if k.startswith('term_')]
                placeholders = ', '.join([f':{c}' for c in columns])
                col_names = ', '.join(columns)
                conn.execute(text(f"INSERT INTO vn_bank_termdepo ({col_names}) VALUES ({placeholders})"), vcb_data)
                conn.commit()
                rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in vcb_data.items() if k.startswith('term_')]
                print(f"  Pushed Vietcombank rates: {rates_list}")
    else:
        print(f"  No Vietcombank term deposit data found")

except Exception as e:
    print(f"  Error crawling Vietcombank: {e}")


print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")