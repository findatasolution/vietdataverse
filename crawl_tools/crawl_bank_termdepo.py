"""
Bank Term Deposit Rates Crawler — ACB
Source: https://acb.com.vn/lai-suat-tien-gui (HTTP, no JS rendering needed)
Usage: python crawl_bank_termdepo.py [--force]
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import argparse
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
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

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
    'term_1m', 'term_2m', 'term_3m', 'term_6m',
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
        return None  # term_noterm column removed; demand-deposit rates not stored
    mapping = {
        1: 'term_1m', 2: 'term_2m', 3: 'term_3m', 6: 'term_6m',
        9: 'term_9m', 12: 'term_12m', 13: 'term_13m',
        15: 'term_18m', 18: 'term_18m', 24: 'term_24m', 36: 'term_36m'
    }
    return mapping.get(month)



# ============================================================================
# DB SAVE
# ============================================================================

def save_bank_data(bank_code, data, force=False):
    """Save bank data to DB. Deletes existing row first if force=True."""
    record = {
        'bank_code': bank_code,
        'date': date_str,
        'crawl_time': datetime.now(),
        'source': 'acb.com.vn',
        'group_name': 'finance',
    }
    for col in TERM_COLUMNS:
        if col in data:
            record[col] = data[col]

    with engine.connect() as conn:
        if not force:
            result = conn.execute(
                text("SELECT COUNT(*) FROM vn_macro_termdepo_daily WHERE bank_code = :bank AND date = :date"),
                {'bank': bank_code, 'date': date_str}
            )
            if result.scalar() > 0:
                print(f"    Data for {bank_code} on {date_str} already exists (use --force to overwrite)")
                return False

        if force:
            conn.execute(
                text("DELETE FROM vn_macro_termdepo_daily WHERE bank_code = :bank AND date = :date"),
                {'bank': bank_code, 'date': date_str}
            )

        columns = [k for k, v in record.items() if v is not None]
        placeholders = ', '.join([f':{c}' for c in columns])
        col_names = ', '.join(columns)
        filtered = {k: v for k, v in record.items() if v is not None}
        conn.execute(text(f"INSERT INTO vn_macro_termdepo_daily ({col_names}) VALUES ({placeholders})"), filtered)
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




# ============================================================================
# ORCHESTRATOR
# ============================================================================

def crawl_bank(bank_code, url, structured_parser):
    """Fetch via HTTP and parse with structured parser. Returns True on success."""
    print(f"\n--- [{bank_code}] ---")
    try:
        print(f"  Fetching with HTTP...")
        response = fetch_with_retry(url, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        print(f"  Fetched OK ({len(response.text)} chars, {len(soup.find_all('table'))} tables)")
    except Exception as e:
        print(f"  FETCH FAILED: {e}")
        return False

    try:
        data = structured_parser(soup)
        if validate_rates(data):
            n = len([k for k in data if k.startswith('term_')])
            rates_str = ', '.join([f'{k}: {v}%' for k, v in sorted(data.items())])
            print(f"  Parsed OK ({n} terms): {rates_str}")
            if save_bank_data(bank_code, data, force=args.force):
                print(f"  -> Saved to DB")
            return True
        else:
            print(f"  PARSE FAILED (insufficient/invalid data)")
            return False
    except Exception as e:
        print(f"  PARSE ERROR: {e}")
        return False


# ============================================================================
# MAIN
# ============================================================================

ok = crawl_bank(
    bank_code='ACB',
    url='https://acb.com.vn/lai-suat-tien-gui',
    structured_parser=parse_acb_structured,
)

print(f"\n{'='*60}")
print(f"  ACB: {'OK' if ok else 'FAILED'}")
print(f"  Completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")

if not ok:
    sys.exit(1)
