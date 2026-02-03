"""
Bank Term Deposit Rates Crawler — Adaptive 3-Layer Architecture
  Layer 1: Structured Parser  (hardcoded per bank, fast, free)
  Layer 2: Heuristic Parser   (score all tables, extract best, free)
  Layer 3: LLM Parser         (Gemini 2.5 Flash, handles ANY HTML change)

Banks: ACB, SHB, CTG (VietinBank), VCB (Vietcombank)
Usage: python crawl_bank_termdepo.py [--force]
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
import json
import os
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

# CLI arguments
parser = argparse.ArgumentParser(description='Bank Term Deposit Rates Crawler')
parser.add_argument('--force', action='store_true', help='Bypass duplicate check, overwrite existing data')
args = parser.parse_args()

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"Bank Term Deposit Crawler - {date_str}")
if args.force:
    print(f"  MODE: --force (will overwrite existing data)")
print(f"{'='*60}")

# Database connection
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    print("ERROR: CRAWLING_BOT_DB environment variable not set")
    sys.exit(1)
engine = create_engine(CRAWLING_BOT_DB)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

TERM_COLUMNS = [
    'term_noterm', 'term_1m', 'term_2m', 'term_3m', 'term_6m',
    'term_9m', 'term_12m', 'term_13m', 'term_18m', 'term_24m', 'term_36m'
]


# ============================================================================
# SHARED UTILITIES
# ============================================================================

def fetch_with_retry(url, headers=None, timeout=15, max_retries=3, backoff=5):
    """Fetch URL with retry and exponential backoff."""
    hdrs = {**HEADERS, **(headers or {})}
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=hdrs, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as e:
            if attempt < max_retries - 1:
                delay = backoff * (attempt + 1)
                print(f"    Retry {attempt+1}/{max_retries} after {delay}s: {e}")
                time.sleep(delay)
            else:
                raise


def fetch_with_selenium(url, wait_selector=None, timeout=20):
    """Fetch URL using headless Chrome. Returns HTML string."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'user-agent={HEADERS["User-Agent"]}')

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout + 10)
        driver.get(url)

        if wait_selector:
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
            )
        else:
            time.sleep(5)  # Default wait for JS rendering

        return driver.page_source
    finally:
        if driver:
            driver.quit()


def validate_rates(data):
    """Validate extracted rate data. Returns True if ≥3 valid rates in range 0.1-20%."""
    term_keys = [k for k in data if k.startswith('term_') and data[k] is not None]
    if len(term_keys) < 3:
        return False
    for key in term_keys:
        val = data[key]
        if not isinstance(val, (int, float)):
            return False
        if val < 0.1 or val > 20.0:
            return False
    return True


def normalize_text(t):
    """Normalize Vietnamese text for matching."""
    t = unicodedata.normalize('NFC', t)
    t = t.replace('\xa0', ' ').replace('\r', '').replace('\n', ' ')
    return ' '.join(t.split()).strip().lower()


def extract_rate_from_text(t):
    """Extract a rate value (0.1-20.0) from text. Returns float or None."""
    t = t.strip().replace(',', '.').replace('%', '').replace('*', '')
    try:
        val = float(t)
        if 0.1 <= val <= 20.0:
            return val
    except (ValueError, AttributeError):
        pass
    m = re.search(r'(\d{1,2}\.\d{1,2})', t)
    if m:
        val = float(m.group(1))
        if 0.1 <= val <= 20.0:
            return val
    return None


def extract_month_from_text(t):
    """Extract month number from term text. Returns int or None. 0 = no-term."""
    t = normalize_text(t)

    # "không kỳ hạn" = demand deposit
    if 'không kỳ hạn' in t or 'khong ky han' in t:
        return 0

    # ACB format: "1T", "12T"
    m = re.match(r'^(\d+)\s*t$', t.strip())
    if m:
        return int(m.group(1))

    # "từ X tháng..." — extract the first number before "tháng"
    m = re.search(r'(?:từ\s+)?(\d+)\s*tháng', t)
    if m:
        return int(m.group(1))

    # Bare number that matches a known term
    m = re.match(r'^(\d+)\s*$', t.strip())
    if m:
        num = int(m.group(1))
        if num in [1, 2, 3, 6, 9, 12, 13, 15, 18, 24, 36]:
            return num

    return None


def month_to_column(month):
    """Map month number to DB column name."""
    if month == 0:
        return 'term_noterm'
    mapping = {
        1: 'term_1m', 2: 'term_2m', 3: 'term_3m', 6: 'term_6m',
        9: 'term_9m', 12: 'term_12m', 13: 'term_13m',
        15: 'term_18m', 18: 'term_18m', 24: 'term_24m', 36: 'term_36m'
    }
    return mapping.get(month)


def score_table(table):
    """Score a table element by likelihood of containing interest rate data."""
    score = 0
    cells = table.find_all(['td', 'th'])
    for cell in cells:
        txt = cell.get_text(strip=True)
        # Rate-like numbers
        if re.search(r'\b\d{1,2}[.,]\d{1,2}\s*%?\b', txt):
            try:
                num = float(re.search(r'(\d{1,2}[.,]\d{1,2})', txt).group(1).replace(',', '.'))
                if 0.1 <= num <= 20.0:
                    score += 2
            except Exception:
                pass
        txt_lower = txt.lower()
        # Term keywords
        if re.search(r'\b\d+\s*t(háng)?\b', txt_lower):
            score += 3
        if 'tháng' in txt_lower or 'thang' in txt_lower:
            score += 1
        if '%' in txt or 'vnd' in txt_lower or 'lãi suất' in txt_lower:
            score += 1
    return score


# ============================================================================
# LAYER 2: HEURISTIC PARSER
# ============================================================================

def heuristic_parse(soup):
    """Score all tables, extract term-rate pairs from the best one."""
    tables = soup.find_all('table')
    if not tables:
        return {}

    scored = [(score_table(t), i, t) for i, t in enumerate(tables)]
    scored.sort(key=lambda x: x[0], reverse=True)

    for sc, idx, table in scored[:3]:
        if sc < 5:
            break

        data = {}
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue

            term_text = cols[0].get_text(strip=True)
            month = extract_month_from_text(term_text)
            if month is None:
                continue
            col_name = month_to_column(month)
            if not col_name:
                continue

            # Find rate from remaining columns (take first valid)
            for col in cols[1:]:
                rate = extract_rate_from_text(col.get_text(strip=True))
                if rate is not None:
                    data[col_name] = rate
                    break

        if validate_rates(data):
            return data

    return {}


# ============================================================================
# LAYER 3: LLM PARSER (Gemini)
# ============================================================================

def llm_parse(html_text, bank_name):
    """Use Gemini 2.5 Flash to extract rates from HTML."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print(f"    [LLM] GEMINI_API_KEY not set, skipping")
        return {}

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Truncate to control token cost
        truncated = html_text[:15000] if len(html_text) > 15000 else html_text

        prompt = f"""Extract Vietnamese bank term deposit interest rates from this {bank_name} webpage HTML.
Return ONLY a valid JSON object (no markdown, no explanation) with this structure:
{{
  "term_1m": <rate as float percentage or null>,
  "term_2m": <rate as float percentage or null>,
  "term_3m": <rate as float percentage or null>,
  "term_6m": <rate as float percentage or null>,
  "term_9m": <rate as float percentage or null>,
  "term_12m": <rate as float percentage or null>,
  "term_13m": <rate as float percentage or null>,
  "term_18m": <rate as float percentage or null>,
  "term_24m": <rate as float percentage or null>,
  "term_36m": <rate as float percentage or null>,
  "term_noterm": <rate as float percentage or null>
}}
Rates should be in percentage form (e.g., 5.2 not 0.052). VND rates only.
If a term is not found, use null.

HTML:
{truncated}"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()

        # Clean markdown code blocks if present
        if result_text.startswith('```'):
            result_text = re.sub(r'^```\w*\n?', '', result_text)
            result_text = re.sub(r'\n?```$', '', result_text)
            result_text = result_text.strip()

        parsed = json.loads(result_text)

        data = {}
        for key, val in parsed.items():
            if key.startswith('term_') and val is not None:
                try:
                    fval = float(val)
                    if 0.1 <= fval <= 20.0:
                        data[key] = fval
                except (ValueError, TypeError):
                    pass
        return data

    except Exception as e:
        print(f"    [LLM] Gemini error: {e}")
        return {}


# ============================================================================
# DB SAVE
# ============================================================================

def save_bank_data(bank_code, data, force=False):
    """Save bank data to DB. Deletes existing row first if force=True."""
    record = {
        'bank_code': bank_code,
        'date': date_str,
        'crawl_time': datetime.now(),
    }
    for col in TERM_COLUMNS:
        if col in data:
            record[col] = data[col]

    with engine.connect() as conn:
        if not force:
            result = conn.execute(
                text("SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = :bank AND date = :date"),
                {'bank': bank_code, 'date': date_str}
            )
            if result.scalar() > 0:
                print(f"    Data for {bank_code} on {date_str} already exists (use --force to overwrite)")
                return False

        if force:
            conn.execute(
                text("DELETE FROM vn_bank_termdepo WHERE bank_code = :bank AND date = :date"),
                {'bank': bank_code, 'date': date_str}
            )

        # Generate next id (table has no auto-increment)
        next_id = conn.execute(text("SELECT COALESCE(MAX(id), 0) + 1 FROM vn_bank_termdepo")).scalar()
        record['id'] = next_id

        columns = [k for k, v in record.items() if v is not None]
        placeholders = ', '.join([f':{c}' for c in columns])
        col_names = ', '.join(columns)
        filtered = {k: v for k, v in record.items() if v is not None}
        conn.execute(text(f"INSERT INTO vn_bank_termdepo ({col_names}) VALUES ({placeholders})"), filtered)
        conn.commit()

    return True


# ============================================================================
# BANK-SPECIFIC STRUCTURED PARSERS (Layer 1)
# ============================================================================

def parse_acb_structured(soup):
    """ACB: Find table containing 'nT' format terms (1T, 3T, 12T) instead of hardcoded index."""
    tables = soup.find_all('table')

    # Find the right table by searching for ACB's "T" term format
    target_table = None
    for table in tables:
        table_text = table.get_text()
        if re.search(r'\b\d+T\b', table_text):
            target_table = table
            break

    if not target_table:
        return {}

    data = {}
    rows = target_table.find_all('tr')
    for row in rows:
        cols = row.find_all('td')
        if len(cols) < 3:
            continue

        term_text = cols[0].get_text(strip=True).upper().strip()

        # Skip header-like rows
        if 'THÁNG' in term_text and 'TRUYỀN' in term_text:
            continue
        if 'LÃI' in term_text and 'KỲ' in term_text:
            continue

        # Find rate value from columns (skip non-rate text)
        rate = None
        for col_idx in range(1, len(cols)):
            cell_text = cols[col_idx].get_text(strip=True)
            if cell_text and cell_text not in ['', '-', 'VND', 'USD']:
                rate = extract_rate_from_text(cell_text)
                if rate is not None:
                    break

        if rate is None:
            continue

        # Map ACB term format "nT" to columns
        m = re.match(r'^(\d+)T$', term_text)
        if m:
            month = int(m.group(1))
            col = month_to_column(month)
            if col:
                data[col] = rate

    return data


def parse_shb_structured(soup):
    """SHB: Parse table with 'X tháng' format."""
    tables = soup.find_all('table')
    if not tables:
        return {}

    data = {}
    table = tables[0]
    rows = table.find_all('tr')

    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 2:
            continue

        term_text = normalize_text(cols[0].get_text(strip=True))
        rate = extract_rate_from_text(cols[1].get_text(strip=True))
        if rate is None:
            continue

        month = extract_month_from_text(term_text)
        if month is not None:
            col = month_to_column(month)
            if col:
                data[col] = rate

    return data


def parse_ctg_structured(soup):
    """CTG/VietinBank: Parse table with relaxed regex instead of exact text match."""
    tables = soup.find_all('table')
    if not tables:
        return {}

    data = {}
    table = tables[0]
    rows = table.find_all('tr')

    for row in rows:
        cols = row.find_all(['td', 'th'])
        if len(cols) < 2:
            continue

        term_text = normalize_text(cols[0].get_text(strip=True))
        rate = extract_rate_from_text(cols[1].get_text(strip=True))
        if rate is None:
            continue

        # Relaxed regex matching (handles wording changes)
        if 'không kỳ hạn' in term_text:
            data['term_noterm'] = rate
        elif re.search(r'(?:từ\s+)?1\s*tháng', term_text) and re.search(r'(?:dưới|đến)\s*2', term_text):
            data['term_1m'] = rate
        elif re.search(r'(?:từ\s+)?2\s*tháng', term_text) and re.search(r'(?:dưới|đến)\s*3', term_text):
            data['term_2m'] = rate
        elif re.search(r'(?:từ\s+)?3\s*tháng', term_text) and re.search(r'(?:dưới|đến)\s*[456]', term_text):
            data['term_3m'] = rate
        elif re.search(r'(?:từ\s+)?6\s*tháng', term_text) and re.search(r'(?:dưới|đến)\s*[789]', term_text):
            data['term_6m'] = rate
        elif re.search(r'(?:từ\s+)?9\s*tháng', term_text) and re.search(r'(?:dưới|đến)\s*1[0-2]', term_text):
            data['term_9m'] = rate
        elif re.search(r'^12\s*tháng$', term_text.strip()):
            data['term_12m'] = rate
        elif re.search(r'trên\s*12\s*tháng', term_text) and '13' in term_text:
            data['term_13m'] = rate
        elif re.search(r'(?:từ\s+)?18\s*tháng', term_text):
            data['term_18m'] = rate
        elif re.search(r'(?:từ\s+)?24\s*tháng', term_text):
            data['term_24m'] = rate
        elif re.search(r'(?:^|\s)36\s*tháng', term_text.strip()):
            data['term_36m'] = rate

    return data


def parse_vcb_structured(soup):
    """VCB: Try hidden input JSON first (legacy), then parse rendered tables."""
    # Legacy method: hidden input with embedded JSON
    json_input = soup.find('input', {'id': 'currentDataInterestRate'})
    if json_input and json_input.get('value'):
        try:
            rate_json = json.loads(json_input['value'])
            tenor_map = {
                'Demand': 'term_noterm', '1-months': 'term_1m', '2-months': 'term_2m',
                '3-months': 'term_3m', '6-months': 'term_6m', '9-months': 'term_9m',
                '12-months': 'term_12m', '18-months': 'term_18m',
                '24-months': 'term_24m', '36-months': 'term_36m'
            }
            data = {}
            for item in rate_json.get('Data', []):
                if item.get('currencyCode') == 'VND' and item.get('tenorType') == 'FixedDeposit':
                    tenor = item.get('tenor')
                    rate = item.get('rates')
                    if tenor in tenor_map and rate is not None:
                        data[tenor_map[tenor]] = round(rate * 100, 2)
            if validate_rates(data):
                print("    (via hidden JSON input)")
                return data
        except (json.JSONDecodeError, KeyError):
            pass

    # New method: parse rendered tables (works with Selenium-fetched HTML)
    tables = soup.find_all('table')
    for table in tables:
        data = {}
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) < 2:
                continue
            term_text = normalize_text(cols[0].get_text(strip=True))
            month = extract_month_from_text(term_text)
            if month is None:
                continue
            col = month_to_column(month)
            if not col:
                continue
            for c in cols[1:]:
                rate = extract_rate_from_text(c.get_text(strip=True))
                if rate is not None:
                    data[col] = rate
                    break
        if validate_rates(data):
            print("    (via rendered table)")
            return data

    return {}


# ============================================================================
# ORCHESTRATOR
# ============================================================================

def crawl_bank(bank_code, url, structured_parser, fetch_method='http', extra_headers=None):
    """Run 3-layer parsing chain for a bank. Returns True on success."""
    print(f"\n--- [{bank_code}] ---")

    html = None
    soup = None

    # === FETCH ===
    try:
        if fetch_method == 'selenium':
            print(f"  Fetching with Selenium...")
            html = fetch_with_selenium(url, wait_selector='table', timeout=20)
            soup = BeautifulSoup(html, 'html.parser')
        else:
            try:
                print(f"  Fetching with HTTP...")
                response = fetch_with_retry(url, headers=extra_headers, timeout=15)
                html = response.text
                soup = BeautifulSoup(response.content, 'html.parser')
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 403:
                    print(f"    HTTP 403 — falling back to Selenium...")
                    html = fetch_with_selenium(url, wait_selector='table', timeout=20)
                    soup = BeautifulSoup(html, 'html.parser')
                else:
                    raise
    except Exception as e:
        print(f"  FETCH FAILED: {e}")
        return False

    print(f"  Fetched OK ({len(html)} chars, {len(soup.find_all('table'))} tables)")

    # === LAYER 1: Structured parser ===
    print(f"  Layer 1 (structured)...", end=' ')
    try:
        data = structured_parser(soup)
        if validate_rates(data):
            n = len([k for k in data if k.startswith('term_')])
            rates_str = ', '.join([f'{k}: {v}%' for k, v in sorted(data.items())])
            print(f"SUCCESS ({n} terms)")
            print(f"    {rates_str}")
            if save_bank_data(bank_code, data, force=args.force):
                print(f"    -> Saved to DB")
            return True
        else:
            print(f"FAILED (insufficient data)")
    except Exception as e:
        print(f"ERROR: {e}")

    # === LAYER 2: Heuristic parser ===
    print(f"  Layer 2 (heuristic)...", end=' ')
    try:
        data = heuristic_parse(soup)
        if validate_rates(data):
            n = len([k for k in data if k.startswith('term_')])
            rates_str = ', '.join([f'{k}: {v}%' for k, v in sorted(data.items())])
            print(f"SUCCESS ({n} terms)")
            print(f"    {rates_str}")
            if save_bank_data(bank_code, data, force=args.force):
                print(f"    -> Saved to DB")
            return True
        else:
            print(f"FAILED")
    except Exception as e:
        print(f"ERROR: {e}")

    # === LAYER 3: LLM parser (Gemini) ===
    print(f"  Layer 3 (LLM/Gemini)...", end=' ')
    try:
        # Feed the best table HTML to Gemini (or page text if no tables)
        tables = soup.find_all('table')
        if tables:
            scored = [(score_table(t), t) for t in tables]
            scored.sort(key=lambda x: x[0], reverse=True)
            llm_input = str(scored[0][1])
        else:
            llm_input = soup.get_text()[:15000]

        data = llm_parse(llm_input, bank_code)
        if validate_rates(data):
            n = len([k for k in data if k.startswith('term_')])
            rates_str = ', '.join([f'{k}: {v}%' for k, v in sorted(data.items())])
            print(f"SUCCESS ({n} terms)")
            print(f"    {rates_str}")
            if save_bank_data(bank_code, data, force=args.force):
                print(f"    -> Saved to DB")
            return True
        else:
            print(f"FAILED")
    except Exception as e:
        print(f"ERROR: {e}")

    print(f"  ALL LAYERS FAILED for {bank_code}")
    return False


# ============================================================================
# MAIN
# ============================================================================

results = {}

# ACB — HTTP works fine, search for table with "nT" format
results['ACB'] = crawl_bank(
    bank_code='ACB',
    url='https://acb.com.vn/lai-suat-tien-gui',
    structured_parser=parse_acb_structured,
    fetch_method='http',
)

# SHB — may return 403, auto-fallback to Selenium
results['SHB'] = crawl_bank(
    bank_code='SHB',
    url='https://ibanking.shb.com.vn/Rate/TideRate',
    structured_parser=parse_shb_structured,
    fetch_method='http',
    extra_headers={'Referer': 'https://ibanking.shb.com.vn/'},
)

# CTG / VietinBank — HTTP works, relaxed regex matching
results['CTG'] = crawl_bank(
    bank_code='CTG',
    url='https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn',
    structured_parser=parse_ctg_structured,
    fetch_method='http',
)

# VCB / Vietcombank — requires Selenium (page uses JS rendering now)
results['VCB'] = crawl_bank(
    bank_code='VCB',
    url='https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat',
    structured_parser=parse_vcb_structured,
    fetch_method='selenium',
)

# === SUMMARY ===
print(f"\n{'='*60}")
print(f"RESULTS")
print(f"{'='*60}")
for bank, success in results.items():
    print(f"  {bank}: {'OK' if success else 'FAILED'}")

total_ok = sum(1 for v in results.values() if v)
total = len(results)
print(f"\n  {total_ok}/{total} banks succeeded")
print(f"  Completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")

if total_ok == 0:
    print("\nERROR: All banks failed!")
    sys.exit(1)
