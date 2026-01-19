"""
Test script for bank term deposit crawlers - Version 2
Better handling of JavaScript-heavy websites
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
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import requests
import re

date_str = datetime.now().strftime('%Y-%m-%d')
print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawl Test V2 - {date_str}")
print(f"{'='*60}")

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    if sys.platform == 'linux':
        chrome_options.binary_location = '/usr/bin/chromium-browser'
    return webdriver.Chrome(options=chrome_options)

results = {}

############## 1. ACB (HTTP)
print(f"\n{'='*60}")
print("1. ACB Bank (HTTP)")
print(f"{'='*60}")

try:
    response = requests.get('https://acb.com.vn/lai-suat-tien-gui',
                          headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    soup = BeautifulSoup(response.content, 'html.parser')

    acb_data = {}
    tables = soup.find_all('table')
    print(f"  Found {len(tables)} tables")

    if len(tables) >= 3:
        for row in tables[2].find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                term = cols[0].get_text(strip=True).upper()
                for col in cols[2:]:
                    txt = col.get_text(strip=True)
                    if txt and txt not in ['', '-', 'VND', 'USD']:
                        try:
                            rate = float(txt.replace('*', '').replace(',', '.').replace('%', ''))
                            if term == '1T': acb_data['term_1m'] = rate
                            elif term == '2T': acb_data['term_2m'] = rate
                            elif term == '3T': acb_data['term_3m'] = rate
                            elif term == '6T': acb_data['term_6m'] = rate
                            elif term == '9T': acb_data['term_9m'] = rate
                            elif term == '12T': acb_data['term_12m'] = rate
                            elif term == '13T': acb_data['term_13m'] = rate
                            elif term in ['15T', '18T']: acb_data['term_18m'] = rate
                            elif term == '24T': acb_data['term_24m'] = rate
                            elif term == '36T': acb_data['term_36m'] = rate
                        except: pass
                        break

    print(f"  ✅ ACB: {acb_data}")
    results['ACB'] = acb_data
except Exception as e:
    print(f"  ❌ ACB Error: {e}")
    results['ACB'] = {'error': str(e)}


############## 2. Techcombank - Try specific URL for rate page
print(f"\n{'='*60}")
print("2. Techcombank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    tcb_data = {}

    try:
        # Try the Vietnamese interest rate page
        print("  Loading Techcombank...")
        driver.get("https://techcombank.com/cong-cu-tien-ich/lai-suat")
        time.sleep(5)

        # Try to scroll to load content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(3)

        # Try clicking on "Tiết kiệm" or similar tab if exists
        try:
            tabs = driver.find_elements(By.XPATH, "//*[contains(text(), 'Tiết kiệm') or contains(text(), 'Tiền gửi')]")
            if tabs:
                print(f"  Found {len(tabs)} potential tabs, clicking first...")
                tabs[0].click()
                time.sleep(3)
        except:
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()

        # Debug: print a snippet of the text
        print(f"  Page text length: {len(text)} chars")

        # Look for rate patterns
        patterns = [
            (r'1\s*tháng[^\d]*(\d+[.,]\d+)', 'term_1m'),
            (r'3\s*tháng[^\d]*(\d+[.,]\d+)', 'term_3m'),
            (r'6\s*tháng[^\d]*(\d+[.,]\d+)', 'term_6m'),
            (r'12\s*tháng[^\d]*(\d+[.,]\d+)', 'term_12m'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        tcb_data[key] = rate
                except: pass

    finally:
        driver.quit()

    print(f"  ✅ TCB: {tcb_data}")
    results['TCB'] = tcb_data
except Exception as e:
    print(f"  ❌ TCB Error: {e}")
    results['TCB'] = {'error': str(e)}


############## 3. MB Bank - Try different URL
print(f"\n{'='*60}")
print("3. MB Bank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    mbb_data = {}

    try:
        # Try direct interest rate page
        print("  Loading MB Bank...")
        driver.get("https://www.mbbank.com.vn/lai-suat")  # Try different URL
        time.sleep(5)

        # Scroll
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()
        print(f"  Page text length: {len(text)} chars")

        # Try to find iframe or specific sections
        iframes = driver.find_elements(By.TAG_NAME, 'iframe')
        print(f"  Found {len(iframes)} iframes")

        patterns = [
            (r'1\s*tháng[^\d]*(\d+[.,]\d+)', 'term_1m'),
            (r'3\s*tháng[^\d]*(\d+[.,]\d+)', 'term_3m'),
            (r'6\s*tháng[^\d]*(\d+[.,]\d+)', 'term_6m'),
            (r'12\s*tháng[^\d]*(\d+[.,]\d+)', 'term_12m'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        mbb_data[key] = rate
                except: pass

    finally:
        driver.quit()

    print(f"  ✅ MBB: {mbb_data}")
    results['MBB'] = mbb_data
except Exception as e:
    print(f"  ❌ MBB Error: {e}")
    results['MBB'] = {'error': str(e)}


############## 4. VPBank - Check for specific element
print(f"\n{'='*60}")
print("4. VPBank (Selenium)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    vpb_data = {}

    try:
        print("  Loading VPBank...")
        # Try the rate comparison tool
        driver.get("https://www.vpbank.com.vn/cong-cu-tien-ich/bang-lai-suat")
        time.sleep(8)

        # Scroll and wait
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()
        print(f"  Page text length: {len(text)} chars")

        # Search for rate patterns
        patterns = [
            (r'1\s*tháng[^\d]*(\d+[.,]\d+)', 'term_1m'),
            (r'3\s*tháng[^\d]*(\d+[.,]\d+)', 'term_3m'),
            (r'6\s*tháng[^\d]*(\d+[.,]\d+)', 'term_6m'),
            (r'12\s*tháng[^\d]*(\d+[.,]\d+)', 'term_12m'),
            (r'24\s*tháng[^\d]*(\d+[.,]\d+)', 'term_24m'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        vpb_data[key] = rate
                except: pass

    finally:
        driver.quit()

    print(f"  ✅ VPB: {vpb_data}")
    results['VPB'] = vpb_data
except Exception as e:
    print(f"  ❌ VPB Error: {e}")
    results['VPB'] = {'error': str(e)}


############## 5. VietinBank (HTTP works)
print(f"\n{'='*60}")
print("5. VietinBank (HTTP)")
print(f"{'='*60}")

try:
    response = requests.get('https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn',
                          headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
    soup = BeautifulSoup(response.content, 'html.parser')

    ctg_data = {}
    tables = soup.find_all('table')
    print(f"  Found {len(tables)} tables")

    # Parse tables
    for table in tables:
        for row in table.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                term = cols[0].get_text(strip=True).upper()
                for col in cols[1:]:
                    txt = col.get_text(strip=True)
                    try:
                        rate = float(txt.replace('%', '').replace(',', '.'))
                        if 0 < rate < 20:
                            if '1 THÁNG' in term: ctg_data['term_1m'] = rate
                            elif '2 THÁNG' in term: ctg_data['term_2m'] = rate
                            elif '3 THÁNG' in term: ctg_data['term_3m'] = rate
                            elif '6 THÁNG' in term: ctg_data['term_6m'] = rate
                            elif '9 THÁNG' in term: ctg_data['term_9m'] = rate
                            elif '12 THÁNG' in term: ctg_data['term_12m'] = rate
                            elif '18 THÁNG' in term: ctg_data['term_18m'] = rate
                            elif '24 THÁNG' in term: ctg_data['term_24m'] = rate
                            break
                    except: pass

    print(f"  ✅ CTG: {ctg_data}")
    results['CTG'] = ctg_data
except Exception as e:
    print(f"  ❌ CTG Error: {e}")
    results['CTG'] = {'error': str(e)}


############## 6. Vietcombank - Longer wait, try different strategy
print(f"\n{'='*60}")
print("6. Vietcombank (Selenium - extended wait)")
print(f"{'='*60}")

try:
    driver = get_chrome_driver()
    vcb_data = {}

    try:
        print("  Loading Vietcombank (waiting 25s)...")
        driver.get("https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat")
        time.sleep(15)

        # Scroll down
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(5)

        # Try to find and click on savings deposit tab
        try:
            elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Tiết kiệm') or contains(text(), 'tiền gửi')]")
            if elements:
                print(f"  Found {len(elements)} clickable elements")
                elements[0].click()
                time.sleep(5)
        except:
            pass

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        text = soup.get_text()
        print(f"  Page text length: {len(text)} chars")

        # Debug: save page source
        # with open('vcb_debug.html', 'w', encoding='utf-8') as f:
        #     f.write(driver.page_source)

        # Check for no-term rate
        noterm = re.search(r'Không kỳ hạn[^\d]*(\d+[.,]\d+)', text, re.IGNORECASE)
        if noterm:
            try:
                rate = float(noterm.group(1).replace(',', '.'))
                if 0 < rate < 20:
                    vcb_data['term_noterm'] = rate
            except: pass

        patterns = [
            (r'1\s*tháng[^\d]*(\d+[.,]\d+)', 'term_1m'),
            (r'2\s*tháng[^\d]*(\d+[.,]\d+)', 'term_2m'),
            (r'3\s*tháng[^\d]*(\d+[.,]\d+)', 'term_3m'),
            (r'6\s*tháng[^\d]*(\d+[.,]\d+)', 'term_6m'),
            (r'9\s*tháng[^\d]*(\d+[.,]\d+)', 'term_9m'),
            (r'12\s*tháng[^\d]*(\d+[.,]\d+)', 'term_12m'),
            (r'24\s*tháng[^\d]*(\d+[.,]\d+)', 'term_24m'),
        ]

        for pattern, key in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    rate = float(match.group(1).replace(',', '.'))
                    if 0 < rate < 20:
                        vcb_data[key] = rate
                except: pass

    finally:
        driver.quit()

    print(f"  ✅ VCB: {vcb_data}")
    results['VCB'] = vcb_data
except Exception as e:
    print(f"  ❌ VCB Error: {e}")
    results['VCB'] = {'error': str(e)}


############## Summary
print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")

success_count = 0
for bank, data in results.items():
    if 'error' in data:
        print(f"  ❌ {bank}: Error")
    elif len(data) == 0:
        print(f"  ⚠️  {bank}: No rates found (website may use dynamic loading)")
    else:
        print(f"  ✅ {bank}: {len(data)} rates - {data}")
        success_count += 1

print(f"\n  Successfully crawled: {success_count}/6 banks")
print(f"{'='*60}")