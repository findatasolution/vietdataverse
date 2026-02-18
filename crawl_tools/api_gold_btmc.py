"""
BTMC Gold Price Crawler
Source: http://api.btmc.vn/api/BTMCAPI/getpricebtmc
Schedule: 2x Daily (9:00 AM and 3:00 PM VN)

Stores BTMC gold prices into vn_gold_24h_hist table.
Product types stored with "BTMC " prefix for clear source identification.

Key products:
- BTMC SJC         → VÀNG MIẾNG SJC (Vàng SJC)
- BTMC VRTL        → VÀNG MIẾNG VRTL (Vàng Rồng Thăng Long)
- BTMC Nhẫn Trơn   → NHẪN TRÒN TRƠN (Vàng Rồng Thăng Long)
- BTMC Nguyên Liệu → VÀNG NGUYÊN LIỆU (Vàng thị trường)
- BTMC RTL 999.9   → TRANG SỨC VÀNG RỒNG THĂNG LONG 999.9
- BTMC RTL 99.9    → TRANG SỨC VÀNG RỒNG THĂNG LONG 99.9
- BTMC Đắc Lộc     → BẢN VÀNG ĐẮC LỘC
- BTMC Quà Mừng    → QUÀ MỪNG BẢN VỊ VÀNG

Prices are in VND per chỉ (1/10 lượng = 3.75g).
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
import json
from sqlalchemy import create_engine, text
from datetime import datetime
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"BTMC Gold Crawler - {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

# Database connection
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

# BTMC API config
BTMC_API_URL = 'http://api.btmc.vn/api/BTMCAPI/getpricebtmc'
BTMC_API_KEY = '3kd8ub1llcg9t45hnoh8hmn7t5kc2v'

# Map BTMC raw product names to clean type names for vn_gold_24h_hist
TYPE_MAP = {
    'VÀNG MIẾNG SJC': 'BTMC SJC',
    'VÀNG MIẾNG VRTL': 'BTMC VRTL',
    'NHẪN TRÒN TRƠN': 'BTMC Nhẫn Trơn',
    'VÀNG NGUYÊN LIỆU': 'BTMC Nguyên Liệu',
    'TRANG SỨC VÀNG RỒNG THĂNG LONG 999.9': 'BTMC RTL 999.9',
    'TRANG SỨC VÀNG RỒNG THĂNG LONG 99.9': 'BTMC RTL 99.9',
    'BẢN VÀNG ĐẮC LỘC': 'BTMC Đắc Lộc',
    'QUÀ MỪNG BẢN VỊ VÀNG': 'BTMC Quà Mừng',
}


def get_clean_type(raw_name):
    """Map raw BTMC product name to clean type for DB storage."""
    # Try exact prefix match (the raw name before the parenthesized part)
    name_upper = raw_name.strip().upper()
    for key, value in TYPE_MAP.items():
        if name_upper.startswith(key.upper()):
            return value
    # Fallback: store with BTMC prefix
    return f'BTMC {raw_name[:50]}'


def parse_btmc_response(data):
    """Parse BTMC API response into list of records."""
    records = []
    rows = data.get('DataList', {}).get('Data', [])

    for row in rows:
        idx = row.get('@row', '')
        if not idx:
            continue

        raw_name = row.get(f'@n_{idx}', '').strip()
        buy_str = row.get(f'@pb_{idx}', '0')
        sell_str = row.get(f'@ps_{idx}', '0')
        world_str = row.get(f'@pt_{idx}', '0')
        time_str = row.get(f'@d_{idx}', '')

        if not raw_name:
            continue

        try:
            buy_price = float(buy_str)
            sell_price = float(sell_str)
        except (ValueError, TypeError):
            print(f"  Skip row {idx}: invalid price data")
            continue

        # Skip if both prices are 0
        if buy_price == 0 and sell_price == 0:
            continue

        # Parse the BTMC timestamp (dd/mm/yyyy HH:MM)
        btmc_date = date_str  # default to today
        if time_str:
            try:
                parsed_dt = datetime.strptime(time_str, '%d/%m/%Y %H:%M')
                btmc_date = parsed_dt.strftime('%Y-%m-%d')
            except ValueError:
                pass

        clean_type = get_clean_type(raw_name)

        records.append({
            'date': btmc_date,
            'type': clean_type,
            'buy_price': buy_price,
            'sell_price': sell_price if sell_price > 0 else None,
            'crawl_time': current_date
        })

    return records


############## CRAWL BTMC GOLD PRICES
print(f"\n--- Crawling BTMC Gold Prices ---")

try:
    response = requests.get(
        BTMC_API_URL,
        params={'key': BTMC_API_KEY},
        timeout=15
    )
    response.raise_for_status()
    data = response.json()

    records = parse_btmc_response(data)

    if not records:
        print("  No valid records parsed from BTMC API")
    else:
        print(f"  Parsed {len(records)} products from BTMC API")

        inserted = 0
        skipped = 0

        for record in records:
            with engine.connect() as conn:
                # Dedup: check if same date + type + same hour already exists
                result = conn.execute(
                    text("""
                        SELECT COUNT(*) FROM vn_gold_24h_hist
                        WHERE date = :date
                        AND type = :type
                        AND crawl_time >= :start_time
                        AND crawl_time < :end_time
                    """),
                    {
                        'date': record['date'],
                        'type': record['type'],
                        'start_time': current_date.replace(minute=0, second=0, microsecond=0),
                        'end_time': current_date.replace(minute=59, second=59, microsecond=999999)
                    }
                )

                if result.scalar() > 0:
                    skipped += 1
                    continue

                conn.execute(
                    text("""
                        INSERT INTO vn_gold_24h_hist (date, type, buy_price, sell_price, crawl_time)
                        VALUES (:date, :type, :buy_price, :sell_price, :crawl_time)
                    """),
                    record
                )
                conn.commit()
                inserted += 1

        print(f"  Pushed {inserted} BTMC records, skipped {skipped} (duplicates)")

except requests.exceptions.RequestException as e:
    print(f"  HTTP Error calling BTMC API: {e}")
except json.JSONDecodeError as e:
    print(f"  JSON parse error from BTMC API: {e}")
except Exception as e:
    import traceback
    print(f"  Error crawling BTMC gold: {e}")
    print(f"  Traceback: {traceback.format_exc()}")

print(f"\n{'='*60}")
print(f"BTMC Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")
