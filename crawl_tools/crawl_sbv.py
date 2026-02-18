"""
SBV (State Bank of Vietnam) Rates Crawler
Runs daily at 9:30 AM VN
- SBV interbank rates from official API
- SBV policy rates (rediscount, refinancing)
- SBV central exchange rate (tỷ giá trung tâm USD/VND)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import pandas as pd
import requests
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"SBV Rates Crawler - {date_str}")
print(f"{'='*60}")

# Database connection
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)


############## 1. SBV Interbank Rates (API)
print(f"\n--- Crawling SBV Interbank Rates ---")

api_url = 'https://sbv.gov.vn/o/headless-delivery/v1.0/content-structures/3450260/structured-contents?pageSize=1&sort=datePublished:desc'
sbv_date = None

try:
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    api_data = response.json()

    if api_data and 'items' in api_data and len(api_data['items']) > 0:
        latest_item = api_data['items'][0]

        # Get date from ngayApDung field
        content_fields = latest_item.get('contentFields', [])
        for field in content_fields:
            if field.get('name') == 'ngayApDung':
                date_value = field.get('contentFieldValue', {}).get('data', '')
                date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                vn_date = date_obj + timedelta(hours=7)
                sbv_date = vn_date.strftime('%Y-%m-%d')
                break

        if not sbv_date:
            print("  Could not find ngayApDung field")
        else:
            print(f"  SBV interbank rate date: {sbv_date}")

            # Parse content fields
            interbank_data = {
                'date': sbv_date,
                'crawl_time': datetime.now()
            }

            # Term mapping
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

                    if thoihan in term_mapping:
                        col_name = term_mapping[thoihan]
                        interbank_data[f'ls_{col_name}'] = laisuat
                        interbank_data[f'doanhso_{col_name}'] = doanhso

            # Check if date already exists
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM vn_sbv_interbankrate WHERE date = '{sbv_date}'"))
                exists = result.scalar() > 0

            if exists:
                print(f"  SBV interbank rate for {sbv_date} already exists, skipping insert")
            else:
                interbank_df = pd.DataFrame([interbank_data])
                interbank_df['date'] = pd.to_datetime(interbank_df['date'])
                interbank_df.to_sql('vn_sbv_interbankrate', engine, if_exists='append', index=False)
                print(f"  Pushed SBV interbank rate for {sbv_date}")
    else:
        print("  No data returned from SBV API")

except Exception as e:
    print(f"  Error crawling SBV interbank rate: {e}")


############## 2. SBV Policy Rates (HTTP)
print(f"\n--- Crawling SBV Policy Rates ---")

try:
    sbv_rates_url = 'https://sbv.gov.vn/en/l%C3%A3i-su%E1%BA%A5t1'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(sbv_rates_url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    rediscount_rate = None
    refinancing_rate = None

    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 2:
                rate_type = cols[0].get_text(strip=True)
                rate_value_text = cols[1].get_text(strip=True)

                try:
                    rate_value = float(rate_value_text.replace('%', '').replace(',', '.').strip())
                except (ValueError, AttributeError):
                    continue

                if 'tái chiết khấu' in rate_type.lower() or 'rediscount' in rate_type.lower():
                    rediscount_rate = rate_value
                    print(f"  Found Rediscount Rate: {rediscount_rate}%")

                if 'tái cấp vốn' in rate_type.lower() or 'refinancing' in rate_type.lower():
                    refinancing_rate = rate_value
                    print(f"  Found Refinancing Rate: {refinancing_rate}%")

    if sbv_date and (rediscount_rate is not None or refinancing_rate is not None):
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM vn_sbv_interbankrate WHERE date = '{sbv_date}'"))
            exists = result.scalar() > 0

            if exists:
                update_query = text("""
                    UPDATE vn_sbv_interbankrate
                    SET rediscount_rate = :rediscount_rate,
                        refinancing_rate = :refinancing_rate
                    WHERE date = :date
                """)
                conn.execute(update_query, {
                    'rediscount_rate': rediscount_rate,
                    'refinancing_rate': refinancing_rate,
                    'date': sbv_date
                })
                conn.commit()
                print(f"  Updated SBV policy rates for {sbv_date}")
            else:
                print(f"  No SBV interbank record found for {sbv_date}, policy rates not updated")
    else:
        print("  Could not find rediscount or refinancing rates")

except Exception as e:
    print(f"  Error crawling SBV policy rates: {e}")


############## 3. SBV Central Exchange Rate (Tỷ giá trung tâm USD/VND)
print(f"\n--- Crawling SBV Central Exchange Rate ---")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
}

def parse_central_rate_structured(soup):
    """Layer 1: Parse the first table with 'Tỷ giá trung tâm' header."""
    tables = soup.find_all('table')
    for table in tables:
        rows = table.find_all('tr')
        # Check if this is the central rate table (has "Tỷ giá trung tâm" in header)
        table_text = table.get_text()
        if 'Tỷ giá trung tâm' not in table_text and 'Đô la Mỹ' not in table_text:
            continue

        data = {}
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if len(cols) >= 2:
                label = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)

                # USD/VND rate: "1 Đô la Mỹ =" -> "25.069 VND"
                if 'Đô la Mỹ' in label or 'USD' in label.upper():
                    # Extract number from "25.069 VND" or "25,069 VND"
                    rate_match = re.search(r'([\d.,]+)\s*VND', value)
                    if rate_match:
                        rate_str = rate_match.group(1).replace('.', '').replace(',', '.')
                        try:
                            data['usd_vnd_rate'] = float(rate_str)
                        except ValueError:
                            pass

                # Document number: "Số văn bản" -> "36/TB-NHNN"
                if 'văn bản' in label.lower() or 'document' in label.lower():
                    data['document_no'] = value

                # Issue date: "Ngày ban hành" -> "03/02/2026"
                if 'ban hành' in label.lower() or 'ngày' in label.lower():
                    # Parse date in format DD/MM/YYYY
                    date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', value)
                    if date_match:
                        day, month, year = date_match.groups()
                        data['issue_date'] = f"{year}-{month}-{day}"

        if 'usd_vnd_rate' in data:
            return data

    return {}


def parse_central_rate_heuristic(soup):
    """Layer 2: Fallback - search for USD/VND rate pattern anywhere in page."""
    page_text = soup.get_text()

    data = {}

    # Pattern: "Đô la Mỹ" followed by a number like 25.069 or 25,069
    # Could be: "1 Đô la Mỹ = 25.069 VND" or similar
    patterns = [
        r'Đô la Mỹ[^\d]*([\d.,]+)\s*VND',
        r'USD[^\d]*([\d]{2}[.,][\d]{3})\s*VND',
        r'1\s*(?:Đô la Mỹ|USD)\s*=\s*([\d.,]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
            rate_str = match.group(1).replace('.', '').replace(',', '.')
            try:
                rate = float(rate_str)
                # Sanity check: USD/VND rate should be between 20,000 and 30,000
                if 20000 <= rate <= 30000:
                    data['usd_vnd_rate'] = rate
                    break
            except ValueError:
                pass

    # Try to find date pattern near "ban hành"
    date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', page_text)
    if date_match:
        day, month, year = date_match.groups()
        data['issue_date'] = f"{year}-{month}-{day}"

    return data


def parse_central_rate_llm(html_text):
    """Layer 3: Use Gemini LLM to extract central exchange rate."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("    [LLM] GEMINI_API_KEY not set, skipping")
        return {}

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        truncated = html_text[:10000] if len(html_text) > 10000 else html_text

        prompt = f"""Extract the SBV (State Bank of Vietnam) central exchange rate for USD/VND from this webpage.
Return ONLY a valid JSON object (no markdown) with this structure:
{{
  "usd_vnd_rate": <rate as float, e.g. 25069.0>,
  "issue_date": "<date in YYYY-MM-DD format or null>",
  "document_no": "<document number string or null>"
}}
The rate should be the number of VND per 1 USD.

HTML:
{truncated}"""

        response = model.generate_content(prompt)
        result_text = response.text.strip()

        if result_text.startswith('```'):
            result_text = re.sub(r'^```\w*\n?', '', result_text)
            result_text = re.sub(r'\n?```$', '', result_text)
            result_text = result_text.strip()

        parsed = json.loads(result_text)

        data = {}
        if parsed.get('usd_vnd_rate'):
            rate = float(parsed['usd_vnd_rate'])
            if 20000 <= rate <= 30000:
                data['usd_vnd_rate'] = rate
        if parsed.get('issue_date'):
            data['issue_date'] = parsed['issue_date']
        if parsed.get('document_no'):
            data['document_no'] = parsed['document_no']

        return data

    except Exception as e:
        print(f"    [LLM] Gemini error: {e}")
        return {}


try:
    fx_url = 'https://sbv.gov.vn/vi/tỷ-giá'
    response = requests.get(fx_url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    html_text = response.text

    print(f"  Fetched OK ({len(html_text)} chars)")

    # Layer 1: Structured parser
    print(f"  Layer 1 (structured)...", end=' ')
    fx_data = parse_central_rate_structured(soup)

    if fx_data.get('usd_vnd_rate'):
        print(f"SUCCESS")
    else:
        print(f"FAILED")
        # Layer 2: Heuristic parser
        print(f"  Layer 2 (heuristic)...", end=' ')
        fx_data = parse_central_rate_heuristic(soup)

        if fx_data.get('usd_vnd_rate'):
            print(f"SUCCESS")
        else:
            print(f"FAILED")
            # Layer 3: LLM parser
            print(f"  Layer 3 (LLM/Gemini)...", end=' ')
            fx_data = parse_central_rate_llm(html_text)

            if fx_data.get('usd_vnd_rate'):
                print(f"SUCCESS")
            else:
                print(f"FAILED")

    if fx_data.get('usd_vnd_rate'):
        rate = fx_data['usd_vnd_rate']
        issue_date = fx_data.get('issue_date', date_str)
        document_no = fx_data.get('document_no', '')

        print(f"    USD/VND Central Rate: {rate:,.0f} VND")
        print(f"    Issue Date: {issue_date}")
        if document_no:
            print(f"    Document: {document_no}")

        # Save to database
        with engine.connect() as conn:
            # Check if table exists, create if not
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vn_sbv_centralrate (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    crawl_time TIMESTAMP NOT NULL,
                    type VARCHAR(20) NOT NULL DEFAULT 'USD',
                    source VARCHAR(20) NOT NULL DEFAULT 'Crawl',
                    bank VARCHAR(10) DEFAULT 'SBV',
                    usd_vnd_rate FLOAT,
                    buy_cash FLOAT,
                    buy_transfer FLOAT,
                    sell_rate FLOAT,
                    document_no VARCHAR(50),
                    UNIQUE(date, type, source, bank)
                )
            """))
            conn.commit()

            # Check if data for this date+type+source+bank exists
            result = conn.execute(
                text("SELECT COUNT(*) FROM vn_sbv_centralrate WHERE date = :date AND type = 'USD' AND source = 'Crawl' AND bank = 'SBV'"),
                {'date': issue_date}
            )
            exists = result.scalar() > 0

            if exists:
                print(f"    Central rate for {issue_date} already exists, skipping")
            else:
                conn.execute(text("""
                    INSERT INTO vn_sbv_centralrate (date, crawl_time, type, source, bank, usd_vnd_rate, document_no)
                    VALUES (:date, :crawl_time, 'USD', 'Crawl', 'SBV', :usd_vnd_rate, :document_no)
                """), {
                    'date': issue_date,
                    'crawl_time': datetime.now(),
                    'usd_vnd_rate': rate,
                    'document_no': document_no
                })
                conn.commit()
                print(f"    -> Saved to DB")
    else:
        print(f"  ALL LAYERS FAILED - could not extract central exchange rate")

except Exception as e:
    print(f"  Error crawling SBV central exchange rate: {e}")


print(f"\n{'='*60}")
print(f"SBV Rates Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")