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