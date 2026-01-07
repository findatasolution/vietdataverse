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
from utils import crawl_gold_price_24h

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

############## Domestic Silver Prices - only current day
url = "https://giabac.vn/SilverInfo/GetGoldPriceChartFromSQLData?days=7&type=L"
response = requests.get(url)
data = response.json()

try:
    # Create domestic_silver DataFrame with all 7 days
    domestic_silver = pd.DataFrame({
        'date': pd.to_datetime(data['Dates']),
        'buy_price': data['LastBuyPrices'],
        'sell_price': data['LastSellPrices']
    })
    domestic_silver = domestic_silver.sort_values(by='date').reset_index(drop=True)

    # Get only the last day (most recent)
    domestic_silver = domestic_silver.tail(1).reset_index(drop=True)

    # Check if date already exists before inserting
    check_date = domestic_silver['date'].iloc[0].strftime('%Y-%m-%d')
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM vn_silver_phuquy_hist WHERE date = '{check_date}'"))
        exists = result.scalar() > 0

    if exists:
        print(f"⚠️  Silver data for {check_date} already exists, skipping insert")
    else:
        domestic_silver.to_sql('vn_silver_phuquy_hist', engine, if_exists='append', index=False)
        print(f"✅ Pushed {len(domestic_silver)} silver record(s) for {check_date}")

except Exception as e:
    print(f"❌ Error crawling Silver: {e}")

############## Domestic Gold Price
gold_data = crawl_gold_price_24h(date_str)

if gold_data:
    print(f"✅ Successfully crawled DOJI HN gold price for {date_str}")

    # Create domestic_gold DataFrame (single row)
    domestic_gold = pd.DataFrame([gold_data])
    domestic_gold['date'] = pd.to_datetime(domestic_gold['date'])

    # Check if record already exists for this date
    from sqlalchemy import text
    check_date = date_str
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM vn_gold_24h_dojihn_hist WHERE date = '{check_date}'"))
        exists = result.scalar() > 0

    if exists:
        print(f"⚠️  DOJI HN gold data for {check_date} already exists, skipping insert")
    else:
        domestic_gold.to_sql('vn_gold_24h_dojihn_hist', engine, if_exists='append', index=False)
        print(f"✅ Pushed DOJI HN gold record for {check_date}")
else:
    print(f"❌ Failed to crawl DOJI HN gold data for {date_str}")

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