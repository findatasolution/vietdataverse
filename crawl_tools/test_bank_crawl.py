"""
Test script for bank term deposit crawlers
Tests: ACB, TCB (Techcombank), MBB (MB Bank), VPB (VPBank), CTG (VietinBank), VCB (Vietcombank)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import requests
import re

# Test date
date_str = datetime.now().strftime('%Y-%m-%d')
print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawl Test - {date_str}")
print(f"{'='*60}")

# Common Selenium setup
def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    if sys.platform == 'linux':
        chrome_options.binary_location = '/usr/bin/chromium-browser'
    return webdriver.Chrome(options=chrome_options)

# Common pattern for Vietnamese terms
term_patterns = {
    'term_1m': r'1\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_2m': r'2\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_3m': r'3\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_6m': r'6\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_9m': r'9\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_12m': r'12\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_18m': r'18\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_24m': r'24\s*tháng[^\d]*(\d+[.,]\d+)',
    'term_36m': r'36\s*tháng[^\d]*(\d+[.,]\d+)',
}

results = {}

############## 1. ACB (HTTP - no Selenium needed)
print(f"\n{'='*60}")
print("1. Testing ACB Bank (HTTP)")
print(f"{'='*60}")

try:
    acb_url = 'https://acb.com.vn/lai-suat-tien-gui'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    response = requests.get(acb_url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    acb_data = {'bank_code': 'ACB'}
    tables = soup.find_all('table')
    print(f"  Found {len(tables)} tables")

    if len(tables) >= 3:
        table = tables[2]
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 3:
                term_text = str(cols[0].get_text(strip=True)).upper()
                if 'THÁNG' in term_text and 'TRUYỀN' in term_text:
                    continue

                rate_text = None
                for col_idx in range(2, len(cols)):
                    text_content = str(cols[col_idx].get_text(strip=True))
                    if text_content and text_content not in ['', '-', 'VND', 'USD']:
                        rate_text = text_content
                        break

                if rate_text:
                    try:
                        rate = float(rate_text.replace('*', '').replace(',', '.').replace('%', '').strip())
                        if term_text == '1T': acb_data['term_1m'] = rate
                        elif term_text == '3T': acb_data['term_3m'] = rate
                        elif term_text == '6T': acb_data['term_6m'] = rate
                        elif term_text == '12T': acb_data['term_12m'] = rate
                        elif term_text == '24T': acb_data['term_24m'] = rate
                    except ValueError:
                        pass

    rates_found = {k: v for k, v in acb_data.items() if k.startswith('term_')}
    print(f"  ✅ ACB rates found: {rates_found}")
    results['ACB'] = rates_found

except Exception as e:
    print(f"  ❌ ACB Error: {e}")
    results['ACB'] = {'error': str(e)}


############## 2. Techcombank (Selenium)
print(f"\n{'='*60}")
print("2. Testing Techcombank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    tcb_data = {'bank_code': 'TCB'}

    try:
        print("  Loading page...")
        driver.get("https://techcombank.com/cong-cu-tien-ich/lai-suat")
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text_content = soup.get_text()
        tables = soup.find_all('table')
        print(f"  Found {len(tables)} tables")

        for key, pattern in term_patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        tcb_data[key] = rate
                except ValueError:
                    pass
    finally:
        driver.quit()

    rates_found = {k: v for k, v in tcb_data.items() if k.startswith('term_')}
    print(f"  ✅ TCB rates found: {rates_found}")
    results['TCB'] = rates_found

except Exception as e:
    print(f"  ❌ TCB Error: {e}")
    results['TCB'] = {'error': str(e)}


############## 3. MB Bank (Selenium)
print(f"\n{'='*60}")
print("3. Testing MB Bank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    mbb_data = {'bank_code': 'MBB'}

    try:
        print("  Loading page...")
        driver.get("https://www.mbbank.com.vn/Fee")
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text_content = soup.get_text()
        tables = soup.find_all('table')
        print(f"  Found {len(tables)} tables")

        for key, pattern in term_patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        mbb_data[key] = rate
                except ValueError:
                    pass
    finally:
        driver.quit()

    rates_found = {k: v for k, v in mbb_data.items() if k.startswith('term_')}
    print(f"  ✅ MBB rates found: {rates_found}")
    results['MBB'] = rates_found

except Exception as e:
    print(f"  ❌ MBB Error: {e}")
    results['MBB'] = {'error': str(e)}


############## 4. VPBank (Selenium)
print(f"\n{'='*60}")
print("4. Testing VPBank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    vpb_data = {'bank_code': 'VPB'}

    try:
        print("  Loading page...")
        driver.get("https://www.vpbank.com.vn/ca-nhan/tiet-kiem")
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text_content = soup.get_text()
        tables = soup.find_all('table')
        print(f"  Found {len(tables)} tables")

        for key, pattern in term_patterns.items():
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        vpb_data[key] = rate
                except ValueError:
                    pass
    finally:
        driver.quit()

    rates_found = {k: v for k, v in vpb_data.items() if k.startswith('term_')}
    print(f"  ✅ VPB rates found: {rates_found}")
    results['VPB'] = rates_found

except Exception as e:
    print(f"  ❌ VPB Error: {e}")
    results['VPB'] = {'error': str(e)}


############## 5. VietinBank (HTTP + Selenium fallback)
print(f"\n{'='*60}")
print("5. Testing VietinBank (HTTP/Selenium)")
print(f"{'='*60}")

try:
    ctg_data = {'bank_code': 'CTG'}
    ctg_url = 'https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # Try HTTP first
    print("  Trying HTTP...")
    response = requests.get(ctg_url, headers=headers, timeout=15)
    soup = BeautifulSoup(response.content, 'html.parser')
    tables = soup.find_all('table')
    print(f"  Found {len(tables)} tables (HTTP)")

    # If no tables, try Selenium
    if len(tables) == 0:
        print("  No tables via HTTP, trying Selenium...")
        driver = get_chrome_driver()
        try:
            driver.get(ctg_url)
            time.sleep(10)
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            tables = soup.find_all('table')
            print(f"  Found {len(tables)} tables (Selenium)")
        finally:
            driver.quit()

    text_content = soup.get_text()
    for key, pattern in term_patterns.items():
        match = re.search(pattern, text_content, re.IGNORECASE)
        if match:
            try:
                rate = float(match.group(1).replace(',', '.'))
                if 0 < rate < 20:
                    ctg_data[key] = rate
            except ValueError:
                pass

    rates_found = {k: v for k, v in ctg_data.items() if k.startswith('term_')}
    print(f"  ✅ CTG rates found: {rates_found}")
    results['CTG'] = rates_found

except Exception as e:
    print(f"  ❌ CTG Error: {e}")
    results['CTG'] = {'error': str(e)}


############## 6. Vietcombank (Selenium - slow)
print(f"\n{'='*60}")
print("6. Testing Vietcombank (Selenium - slow website)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    vcb_data = {'bank_code': 'VCB'}

    try:
        print("  Loading page (this takes ~20 seconds)...")
        driver.get("https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat")
        time.sleep(20)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text_content = soup.get_text()
        tables = soup.find_all('table')
        print(f"  Found {len(tables)} tables")

        # Check for "Không kỳ hạn"
        noterm_match = re.search(r'Không kỳ hạn.*?(\d+[.,]\d+)', text_content, re.IGNORECASE)
        if noterm_match:
            try:
                rate = float(noterm_match.group(1).replace(',', '.'))
                if 0 < rate < 20:
                    vcb_data['term_noterm'] = rate
            except ValueError:
                pass

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
        driver.quit()

    rates_found = {k: v for k, v in vcb_data.items() if k.startswith('term_')}
    print(f"  ✅ VCB rates found: {rates_found}")
    results['VCB'] = rates_found

except Exception as e:
    print(f"  ❌ VCB Error: {e}")
    results['VCB'] = {'error': str(e)}


############## Summary
print(f"\n{'='*60}")
print("SUMMARY - Bank Term Deposit Crawl Test Results")
print(f"{'='*60}")

for bank, data in results.items():
    if 'error' in data:
        print(f"  ❌ {bank}: Error - {data['error']}")
    elif len(data) == 0:
        print(f"  ⚠️  {bank}: No rates found")
    else:
        print(f"  ✅ {bank}: {len(data)} rates found - {data}")

print(f"\n{'='*60}")
print("Test completed!")
print(f"{'='*60}")