"""
SBV (State Bank of Vietnam) Rates Crawler
Runs daily at 9:30 AM VN
- SBV interbank rates from official API
- SBV policy rates (rediscount, refinancing)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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


print(f"\n{'='*60}")
print(f"SBV Rates Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")