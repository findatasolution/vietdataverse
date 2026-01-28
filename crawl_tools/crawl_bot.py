# import sys
# import io
# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# import pandas as pd
# import requests
# import json
# from sqlalchemy import create_engine
# from bs4 import BeautifulSoup
# import time
# from datetime import datetime
# from sqlalchemy import text
# from selenium import webdriver
# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.chrome.options import Options

# current_date = datetime.now()
# date_str = current_date.strftime('%Y-%m-%d')

# # Import os for environment variables
# import os
# from dotenv import load_dotenv

# # Load environment variables from root directory
# from pathlib import Path
# root_dir = Path(__file__).resolve().parent.parent.parent
# load_dotenv(dotenv_path=root_dir / '.env')

# # Crawling bot DB for domestic data (gold, silver, SBV, bank deposits)
# CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
# if not CRAWLING_BOT_DB:
#     # Fallback for GitHub Actions which may not have .env
#     CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
# engine = create_engine(CRAWLING_BOT_DB)

# # New DB for global macro data
# GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
# if not GLOBAL_INDICATOR_DB:
#     # Fallback for GitHub Actions
#     GLOBAL_INDICATOR_DB = 'postgresql://neondb_owner:npg_DTMVHjWIy21J@ep-frosty-forest-a19clsva-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
# global_indicator_engine = create_engine(GLOBAL_INDICATOR_DB)

# ############## Domestic Silver Prices - crawl with Selenium
# try:
#     # Setup headless Chrome
#     chrome_options = Options()
#     chrome_options.add_argument('--headless')
#     chrome_options.add_argument('--no-sandbox')
#     chrome_options.add_argument('--disable-dev-shm-usage')
#     chrome_options.add_argument('--disable-gpu')
#     if sys.platform == 'linux':
#         chrome_options.binary_location = '/usr/bin/chromium-browser'

#     driver = webdriver.Chrome(options=chrome_options)
#     buy_price = None
#     sell_price = None

#     try:
#         driver.get("https://giabac.vn/")
#         time.sleep(2)  # Wait for page load

#         # Click "Lượng" button to filter by unit
#         buttons = driver.find_elements(By.TAG_NAME, "button")
#         for btn in buttons:
#             if "Lượng" in btn.text or "luong" in btn.text.lower():
#                 btn.click()
#                 time.sleep(2)  # Wait for price update
#                 break

#         # Get price from priceDiv
#         price_div = WebDriverWait(driver, 10).until(
#             EC.presence_of_element_located((By.ID, "priceDiv"))
#         )
#         price_elements = price_div.find_elements(By.CSS_SELECTOR, "p.text-24px")

#         if len(price_elements) >= 2:
#             buy_text = price_elements[0].text.strip().replace(',', '').replace('.', '')
#             sell_text = price_elements[1].text.strip().replace(',', '').replace('.', '')
#             buy_price = float(buy_text)
#             sell_price = float(sell_text)

#     finally:
#         driver.quit()

#     if buy_price and sell_price:
#         crawl_time = datetime.now()
#         silver_record = {
#             'date': date_str,
#             'crawl_time': crawl_time,
#             'buy_price': buy_price,
#             'sell_price': sell_price
#         }

#         # Check if exists in same hour
#         with engine.connect() as conn:
#             result = conn.execute(
#                 text("""
#                     SELECT COUNT(*) FROM vn_silver_phuquy_hist
#                     WHERE date = :date
#                     AND crawl_time >= :start_time
#                     AND crawl_time < :end_time
#                 """),
#                 {
#                     'date': date_str,
#                     'start_time': crawl_time.replace(minute=0, second=0, microsecond=0),
#                     'end_time': crawl_time.replace(minute=59, second=59, microsecond=999999)
#                 }
#             )
#             exists = result.scalar() > 0

#         if exists:
#             print(f"⚠️  Silver data for {date_str} {crawl_time.strftime('%H:%M')} already exists")
#         else:
#             with engine.connect() as conn:
#                 conn.execute(
#                     text("""
#                         INSERT INTO vn_silver_phuquy_hist (date, crawl_time, buy_price, sell_price)
#                         VALUES (:date, :crawl_time, :buy_price, :sell_price)
#                     """),
#                     silver_record
#                 )
#                 conn.commit()
#             print(f"✅ Pushed silver: {crawl_time.strftime('%H:%M')} | Buy {buy_price:,.0f} | Sell {sell_price:,.0f}")
#     else:
#         print(f"❌ No silver price found in div#priceDiv")

# except Exception as e:
#     print(f"❌ Error crawling Silver: {e}")

# ############## Domestic Gold Price - All brands
# url_gold = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'

# try:
#     response_gold = requests.get(url_gold, timeout=10)
#     response_gold.raise_for_status()
#     soup_gold = BeautifulSoup(response_gold.content, 'html.parser')

#     gold_records = []
#     tables_gold = soup_gold.find_all('table')

#     for table in tables_gold:
#         rows = table.find_all('tr')
#         for row in rows:
#             cols = row.find_all('td')
#             if len(cols) >= 3:
#                 brand_td = cols[0].find('h2')
#                 if not brand_td:
#                     continue
#                 brand_type = brand_td.get_text(strip=True)

#                 try:
#                     buy_span = cols[1].find('span', class_='fixW')
#                     sell_span = cols[2].find('span', class_='fixW')

#                     if not buy_span or not sell_span:
#                         continue

#                     buy_price = buy_span.get_text(strip=True).replace('.', '').replace(',', '')
#                     sell_price = sell_span.get_text(strip=True).replace('.', '').replace(',', '')

#                     buy_price = float(buy_price) * 1000
#                     sell_price = float(sell_price) * 1000

#                     gold_records.append({
#                         'date': date_str,
#                         'type': brand_type,
#                         'buy_price': buy_price,
#                         'sell_price': sell_price
#                     })
#                 except (ValueError, AttributeError):
#                     continue

#     if gold_records:
#         print(f"✅ Crawled {len(gold_records)} gold brands for {date_str}")

#         inserted = 0
#         skipped = 0

#         for record in gold_records:
#             with engine.connect() as conn:
#                 result = conn.execute(
#                     text("SELECT COUNT(*) FROM vn_gold_24h_hist WHERE date = :date AND type = :type"),
#                     {'date': record['date'], 'type': record['type']}
#                 )

#                 if result.scalar() > 0:
#                     skipped += 1
#                     continue

#                 conn.execute(
#                     text("""
#                         INSERT INTO vn_gold_24h_hist (date, type, buy_price, sell_price)
#                         VALUES (:date, :type, :buy_price, :sell_price)
#                     """),
#                     record
#                 )
#                 conn.commit()
#                 inserted += 1

#         print(f"✅ Pushed {inserted} gold records, skipped {skipped}")
#     else:
#         print(f"❌ No gold data found for {date_str}")

# except Exception as e:
#     print(f"❌ Error crawling gold prices: {e}")

# ############## SBV interbank
# api_url = 'https://sbv.gov.vn/o/headless-delivery/v1.0/content-structures/3450260/structured-contents?pageSize=1&sort=datePublished:desc'

# try:
#     response = requests.get(api_url, timeout=10)
#     response.raise_for_status()
#     api_data = response.json()

#     if api_data and 'items' in api_data and len(api_data['items']) > 0:
#         latest_item = api_data['items'][0]

#         # Get date from ngayApDung field (this is the actual application date)
#         sbv_date = None
#         content_fields = latest_item.get('contentFields', [])
#         for field in content_fields:
#             if field.get('name') == 'ngayApDung':
#                 date_value = field.get('contentFieldValue', {}).get('data', '')
#                 # Format: 2025-12-23T17:00:00Z -> convert to local date
#                 sbv_date = date_value.split('T')[0]  # Extract YYYY-MM-DD
#                 # Adjust for timezone (Vietnam is UTC+7)
#                 from datetime import datetime, timedelta
#                 date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
#                 # Convert to Vietnam time
#                 vn_date = date_obj + timedelta(hours=7)
#                 sbv_date = vn_date.strftime('%Y-%m-%d')
#                 break

#         if not sbv_date:
#             print("❌ Could not find ngayApDung field")
#         else:
#             # Check if this date matches today
#             if sbv_date == date_str:
#                 print(f"⚠️  SBV interbank rate for {sbv_date} already matches today, no changes")
#             else:
#                 print(f"✅ New SBV interbank rate date found: {sbv_date}")

#                 # Parse content fields
#                 interbank_data = {
#                     'date': sbv_date,
#                     'crawl_time': datetime.now()
#                 }

#                 # Term mapping to column names
#                 term_mapping = {
#                     'Qua đêm': 'quadem',
#                     '1 Tuần': '1w',
#                     '2 Tuần': '2w',
#                     '1 Tháng': '1m',
#                     '3 Tháng': '3m',
#                     '6 Tháng': '6m',
#                     '9 Tháng': '9m'
#                 }

#                 for field in content_fields:
#                     if field.get('name') == 'laiSuatThiTruongNganHangs':
#                         # Each field is one timeframe (overnight, 1 week, etc.)
#                         thoihan = None
#                         laisuat = None
#                         doanhso = None

#                         nested_fields = field.get('nestedContentFields', [])
#                         for nested_field in nested_fields:
#                             field_name = nested_field.get('name', '')
#                             field_value = nested_field.get('contentFieldValue', {}).get('data', '')

#                             if field_name == 'thoihan':
#                                 thoihan = field_value
#                             elif field_name == 'laiSuatBQLienNganHang':
#                                 try:
#                                     laisuat = float(str(field_value).replace(',', '.')) if field_value else None
#                                 except (ValueError, TypeError):
#                                     laisuat = None
#                             elif field_name == 'doanhSo':
#                                 try:
#                                     doanhso = float(str(field_value).replace(',', '.')) if field_value else None
#                                 except (ValueError, TypeError):
#                                     doanhso = None

#                         # Map to column names
#                         if thoihan in term_mapping:
#                             col_name = term_mapping[thoihan]
#                             interbank_data[f'ls_{col_name}'] = laisuat
#                             interbank_data[f'doanhso_{col_name}'] = doanhso

#                 print(f"Debug - Crawled data: {interbank_data}")

#                 # Create DataFrame and insert
#                 interbank_df = pd.DataFrame([interbank_data])
#                 interbank_df['date'] = pd.to_datetime(interbank_df['date'])

#                 # Check if date already exists
#                 with engine.connect() as conn:
#                     result = conn.execute(text(f"SELECT COUNT(*) FROM vn_sbv_interbankrate WHERE date = '{sbv_date}'"))
#                     exists = result.scalar() > 0

#                 if exists:
#                     print(f"⚠️  SBV interbank rate for {sbv_date} already exists, skipping insert")
#                 else:
#                     interbank_df.to_sql('vn_sbv_interbankrate', engine, if_exists='append', index=False)
#                     print(f"✅ Pushed SBV interbank rate for {sbv_date}")
#     else:
#         print("❌ No data returned from SBV API")

# except Exception as e:
#     print(f"❌ Error crawling SBV interbank rate: {e}")

# ############## SBV Policy Rates (Rediscount & Refinancing)
# try:
#     sbv_rates_url = 'https://sbv.gov.vn/en/l%C3%A3i-su%E1%BA%A5t1'
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#     }
#     response = requests.get(sbv_rates_url, headers=headers, timeout=15)
#     response.raise_for_status()
#     soup = BeautifulSoup(response.content, 'html.parser')

#     # Initialize rates
#     rediscount_rate = None
#     refinancing_rate = None

#     # Find the table containing policy rates
#     tables = soup.find_all('table')

#     for table in tables:
#         rows = table.find_all('tr')
#         for row in rows:
#             cols = row.find_all('td')
#             if len(cols) >= 2:
#                 rate_type = cols[0].get_text(strip=True)
#                 rate_value_text = cols[1].get_text(strip=True)

#                 # Extract numeric value (e.g., "3.000%" -> 3.0)
#                 try:
#                     rate_value = float(rate_value_text.replace('%', '').replace(',', '.').strip())
#                 except (ValueError, AttributeError):
#                     continue

#                 # Check for rediscount rate
#                 if 'tái chiết khấu' in rate_type.lower() or 'rediscount' in rate_type.lower():
#                     rediscount_rate = rate_value
#                     print(f"Found Rediscount Rate: {rediscount_rate}%")

#                 # Check for refinancing rate
#                 if 'tái cấp vốn' in rate_type.lower() or 'refinancing' in rate_type.lower():
#                     refinancing_rate = rate_value
#                     print(f"Found Refinancing Rate: {refinancing_rate}%")

#     if rediscount_rate is not None or refinancing_rate is not None:
#         # Update vn_sbv_interbankrate table with policy rates
#         with engine.connect() as conn:
#             # Check if record exists for sbv_date
#             result = conn.execute(text(f"SELECT COUNT(*) FROM vn_sbv_interbankrate WHERE date = '{sbv_date}'"))
#             exists = result.scalar() > 0

#             if exists:
#                 # Update existing record with policy rates
#                 update_query = text("""
#                     UPDATE vn_sbv_interbankrate
#                     SET rediscount_rate = :rediscount_rate,
#                         refinancing_rate = :refinancing_rate
#                     WHERE date = :date
#                 """)
#                 conn.execute(update_query, {
#                     'rediscount_rate': rediscount_rate,
#                     'refinancing_rate': refinancing_rate,
#                     'date': sbv_date
#                 })
#                 conn.commit()
#                 print(f"✅ Updated SBV policy rates (rediscount: {rediscount_rate}%, refinancing: {refinancing_rate}%) for {sbv_date}")
#             else:
#                 print(f"⚠️  No SBV interbank record found for {sbv_date}, policy rates not updated")
#     else:
#         print("❌ Could not find rediscount or refinancing rates on SBV page")

# except Exception as e:
#     print(f"❌ Error crawling SBV policy rates: {e}")
#     import traceback
#     traceback.print_exc()

# ############## Bank Term Deposit Rates
# # Note: Vietcombank website requires JavaScript rendering,
# # skipped for now (would need Selenium/Playwright)

# # ACB
# try:
#     acb_url = 'https://acb.com.vn/lai-suat-tien-gui'
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#     }
#     response = requests.get(acb_url, headers=headers, timeout=10)
#     response.raise_for_status()
#     soup = BeautifulSoup(response.content, 'html.parser')

#     acb_data = {
#         'bank_code': 'ACB',
#         'date': date_str,
#         'crawl_time': datetime.now()
#     }

#     tables = soup.find_all('table')

#     # ACB uses Table 2 for term deposit rates (based on website structure analysis)
#     if len(tables) >= 3:
#         table = tables[2]
#         rows = table.find_all('tr')

#         for row in rows:
#             cols = row.find_all('td')
#             if len(cols) >= 3:
#                 term_text = str(cols[0].get_text(strip=True)).upper()

#                 # Skip header rows
#                 if 'THÁNG' in term_text.upper() and 'TRUYỀN' in term_text.upper():
#                     continue
#                 if 'LÃI' in term_text.upper() and 'KỲ' in term_text.upper():
#                     continue

#                 # Get VND rate from column 2 onwards (skip USD column)
#                 rate_text = None
#                 for col_idx in range(2, len(cols)):
#                     text_content = str(cols[col_idx].get_text(strip=True))
#                     # Skip headers and empty cells
#                     if text_content and text_content not in ['', '-', 'VND', 'USD', 'Lãicuối kỳ', 'Lãiquý', 'Lãitháng', 'Lãi trả trước', 'Tích LũyTương Lai']:
#                         rate_text = text_content
#                         break

#                 if not rate_text:
#                     continue

#                 try:
#                     # Remove asterisks and special characters before parsing
#                     clean_rate = rate_text.replace('*', '').replace(',', '.').replace('%', '').strip()
#                     rate = float(clean_rate)

#                     # ACB uses format: 1T, 2T, 3T, 6T, 9T, 12T, etc.
#                     if term_text == '1T':
#                         acb_data['term_1m'] = rate
#                     elif term_text == '2T':
#                         acb_data['term_2m'] = rate
#                     elif term_text == '3T':
#                         acb_data['term_3m'] = rate
#                     elif term_text == '6T':
#                         acb_data['term_6m'] = rate
#                     elif term_text == '9T':
#                         acb_data['term_9m'] = rate
#                     elif term_text == '12T':
#                         acb_data['term_12m'] = rate
#                     elif term_text == '13T':
#                         acb_data['term_13m'] = rate
#                     elif term_text in ['15T', '18T']:
#                         acb_data['term_18m'] = rate
#                     elif term_text == '24T':
#                         acb_data['term_24m'] = rate
#                     elif term_text == '36T':
#                         acb_data['term_36m'] = rate

#                 except (ValueError, AttributeError, TypeError):
#                     continue

#     has_data = any(key.startswith('term_') for key in acb_data.keys())

#     if has_data:
#         with engine.connect() as conn:
#             result = conn.execute(text(f"SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'ACB' AND date = '{date_str}'"))
#             exists = result.scalar() > 0

#         if exists:
#             print(f"⚠️  ACB term deposit data for {date_str} already exists, skipping insert")
#         else:
#             acb_df = pd.DataFrame([acb_data])
#             acb_df['date'] = pd.to_datetime(acb_df['date'])
#             acb_df.to_sql('vn_bank_termdepo', engine, if_exists='append', index=False)
#             print(f"✅ Pushed ACB term deposit rates for {date_str}")
#             rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in acb_data.items() if k.startswith('term_')]
#             print(f"   Rates: {rates_list}")
#     else:
#         print(f"⚠️  No ACB term deposit data found (website may have changed structure)")

# except Exception as e:
#     print(f"❌ Error crawling ACB term deposit: {e}")


# ############## Techcombank, MB Bank, VPBank - DISABLED
# # These banks use React/Angular SPA with complex client-side rendering
# # that cannot be easily scraped. Testing confirmed no rates can be extracted.
# # TODO: Research API endpoints or use third-party data aggregators
# print("\n" + "="*60)
# print("Skipping TCB, MBB, VPB (React/Angular SPA - needs API research)")
# print("="*60)
# print("  Techcombank (TCB): React SPA - no public API found")
# print("  MB Bank (MBB): AngularJS with dynamic content")
# print("  VPBank (VPB): React SPA - no public API found")


# ############## VietinBank Term Deposit Rates (HTTP - may work without Selenium)
# print("\n" + "="*60)
# print("Crawling VietinBank Term Deposit Rates")
# print("="*60)

# try:
#     ctg_url = 'https://www.vietinbank.vn/ca-nhan/cong-cu-tien-ich/lai-suat-khcn'
#     headers = {
#         'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
#     }

#     # Try HTTP first, fallback to Selenium if needed
#     response = requests.get(ctg_url, headers=headers, timeout=15)
#     response.raise_for_status()
#     soup_ctg = BeautifulSoup(response.content, 'html.parser')

#     ctg_data = {
#         'bank_code': 'CTG',  # VietinBank stock code
#         'date': date_str,
#         'crawl_time': datetime.now()
#     }

#     tables = soup_ctg.find_all('table')
#     print(f"  Found {len(tables)} tables (HTTP)")

#     # If no tables found via HTTP, try Selenium
#     if len(tables) == 0:
#         print("  No tables found via HTTP, trying Selenium...")
#         chrome_options_ctg = Options()
#         chrome_options_ctg.add_argument('--headless')
#         chrome_options_ctg.add_argument('--no-sandbox')
#         chrome_options_ctg.add_argument('--disable-dev-shm-usage')
#         chrome_options_ctg.add_argument('--disable-gpu')
#         if sys.platform == 'linux':
#             chrome_options_ctg.binary_location = '/usr/bin/chromium-browser'

#         driver_ctg = webdriver.Chrome(options=chrome_options_ctg)
#         try:
#             driver_ctg.get(ctg_url)
#             time.sleep(10)
#             soup_ctg = BeautifulSoup(driver_ctg.page_source, 'html.parser')
#             tables = soup_ctg.find_all('table')
#             print(f"  Found {len(tables)} tables (Selenium)")
#         finally:
#             driver_ctg.quit()

#     import re
#     text_content = soup_ctg.get_text()

#     # Pattern matching for VietinBank rates
#     term_patterns = {
#         'term_1m': r'1\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_2m': r'2\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_3m': r'3\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_6m': r'6\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_9m': r'9\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_12m': r'12\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_18m': r'18\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_24m': r'24\s*tháng[^\d]*(\d+[.,]\d+)',
#         'term_36m': r'36\s*tháng[^\d]*(\d+[.,]\d+)',
#     }

#     for key, pattern in term_patterns.items():
#         match = re.search(pattern, text_content, re.IGNORECASE)
#         if match:
#             try:
#                 rate = float(match.group(1).replace(',', '.'))
#                 if 0 < rate < 20:
#                     ctg_data[key] = rate
#                     print(f"    Found {key}: {rate}%")
#             except ValueError:
#                 pass

#     # Parse tables
#     for table in tables:
#         rows = table.find_all('tr')
#         for row in rows:
#             cols = row.find_all(['td', 'th'])
#             if len(cols) >= 2:
#                 term_text = cols[0].get_text(strip=True).upper()

#                 for col in cols[1:]:
#                     rate_text = col.get_text(strip=True)
#                     try:
#                         rate = float(rate_text.replace('%', '').replace(',', '.').strip())
#                         if 0 < rate < 20:
#                             if '1 THÁNG' in term_text and ctg_data.get('term_1m') is None:
#                                 ctg_data['term_1m'] = rate
#                             elif '3 THÁNG' in term_text and ctg_data.get('term_3m') is None:
#                                 ctg_data['term_3m'] = rate
#                             elif '6 THÁNG' in term_text and ctg_data.get('term_6m') is None:
#                                 ctg_data['term_6m'] = rate
#                             elif '12 THÁNG' in term_text and ctg_data.get('term_12m') is None:
#                                 ctg_data['term_12m'] = rate
#                             elif '24 THÁNG' in term_text and ctg_data.get('term_24m') is None:
#                                 ctg_data['term_24m'] = rate
#                             break
#                     except ValueError:
#                         continue

#     has_ctg_data = any(key.startswith('term_') for key in ctg_data.keys())

#     if has_ctg_data:
#         with engine.connect() as conn:
#             result = conn.execute(text(f"SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'CTG' AND date = '{date_str}'"))
#             exists = result.scalar() > 0

#         if exists:
#             print(f"⚠️  VietinBank term deposit data for {date_str} already exists, skipping insert")
#         else:
#             ctg_df = pd.DataFrame([ctg_data])
#             ctg_df['date'] = pd.to_datetime(ctg_df['date'])
#             ctg_df.to_sql('vn_bank_termdepo', engine, if_exists='append', index=False)
#             print(f"✅ Pushed VietinBank term deposit rates for {date_str}")
#             rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in ctg_data.items() if k.startswith('term_')]
#             print(f"   Rates: {rates_list}")
#     else:
#         print(f"⚠️  No VietinBank term deposit data found")

# except Exception as e:
#     print(f"❌ Error crawling VietinBank term deposit: {e}")


# ############## Vietcombank Term Deposit Rates (Selenium required - slow website)
# print("\n" + "="*60)
# print("Crawling Vietcombank Term Deposit Rates")
# print("="*60)

# try:
#     # Setup headless Chrome for VCB
#     chrome_options_vcb = Options()
#     chrome_options_vcb.add_argument('--headless')
#     chrome_options_vcb.add_argument('--no-sandbox')
#     chrome_options_vcb.add_argument('--disable-dev-shm-usage')
#     chrome_options_vcb.add_argument('--disable-gpu')
#     if sys.platform == 'linux':
#         chrome_options_vcb.binary_location = '/usr/bin/chromium-browser'

#     driver_vcb = webdriver.Chrome(options=chrome_options_vcb)

#     vcb_data = {
#         'bank_code': 'VCB',
#         'date': date_str,
#         'crawl_time': datetime.now(),
#         'term_noterm': None,
#         'term_1m': None,
#         'term_2m': None,
#         'term_3m': None,
#         'term_6m': None,
#         'term_9m': None,
#         'term_12m': None,
#         'term_13m': None,
#         'term_18m': None,
#         'term_24m': None,
#         'term_36m': None
#     }

#     try:
#         print("  Loading Vietcombank interest rates page...")
#         driver_vcb.get("https://www.vietcombank.com.vn/vi-VN/KHCN/Cong-cu-Tien-ich/KHCN---Lai-suat")
#         print("  Waiting for page to render (20 seconds - VCB is slow)...")
#         time.sleep(20)  # VCB needs longer wait

#         soup_vcb = BeautifulSoup(driver_vcb.page_source, 'html.parser')

#         tables = soup_vcb.find_all('table')
#         print(f"  Found {len(tables)} tables")

#         import re
#         text_content = soup_vcb.get_text()

#         # Pattern matching for VCB rates
#         # VCB pattern: "Không kỳ hạn" followed by rate
#         noterm_match = re.search(r'Không kỳ hạn.*?(\d+[.,]\d+)\s*%?', text_content, re.IGNORECASE)
#         if noterm_match:
#             try:
#                 rate = float(noterm_match.group(1).replace(',', '.'))
#                 if 0 < rate < 20:
#                     vcb_data['term_noterm'] = rate
#                     print(f"    Found term_noterm: {rate}%")
#             except ValueError:
#                 pass

#         term_patterns = {
#             'term_1m': r'1\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_2m': r'2\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_3m': r'3\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_6m': r'6\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_9m': r'9\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_12m': r'12\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_13m': r'13\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_18m': r'18\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_24m': r'24\s*tháng[^\d]*(\d+[.,]\d+)',
#             'term_36m': r'36\s*tháng[^\d]*(\d+[.,]\d+)',
#         }

#         for key, pattern in term_patterns.items():
#             match = re.search(pattern, text_content, re.IGNORECASE)
#             if match:
#                 try:
#                     rate = float(match.group(1).replace(',', '.'))
#                     if 0 < rate < 20:
#                         vcb_data[key] = rate
#                         print(f"    Found {key}: {rate}%")
#                 except ValueError:
#                     pass

#         # Parse tables for more accurate data
#         for table in tables:
#             rows = table.find_all('tr')
#             for row in rows:
#                 cols = row.find_all(['td', 'th'])
#                 if len(cols) >= 2:
#                     term_text = cols[0].get_text(strip=True).upper()

#                     # Skip headers
#                     if 'KỲ HẠN' in term_text or 'LÃI SUẤT' in term_text:
#                         continue

#                     # Find VND rate
#                     for col in cols[1:]:
#                         col_text = col.get_text(strip=True)
#                         try:
#                             rate = float(col_text.replace('%', '').replace(',', '.').replace('*', '').strip())
#                             if 0 < rate < 20:
#                                 if 'KHÔNG KỲ HẠN' in term_text and vcb_data.get('term_noterm') is None:
#                                     vcb_data['term_noterm'] = rate
#                                 elif '1 THÁNG' in term_text and vcb_data.get('term_1m') is None:
#                                     vcb_data['term_1m'] = rate
#                                 elif '2 THÁNG' in term_text and vcb_data.get('term_2m') is None:
#                                     vcb_data['term_2m'] = rate
#                                 elif '3 THÁNG' in term_text and vcb_data.get('term_3m') is None:
#                                     vcb_data['term_3m'] = rate
#                                 elif '6 THÁNG' in term_text and vcb_data.get('term_6m') is None:
#                                     vcb_data['term_6m'] = rate
#                                 elif '9 THÁNG' in term_text and vcb_data.get('term_9m') is None:
#                                     vcb_data['term_9m'] = rate
#                                 elif '12 THÁNG' in term_text and vcb_data.get('term_12m') is None:
#                                     vcb_data['term_12m'] = rate
#                                 elif '13 THÁNG' in term_text and vcb_data.get('term_13m') is None:
#                                     vcb_data['term_13m'] = rate
#                                 elif '18 THÁNG' in term_text and vcb_data.get('term_18m') is None:
#                                     vcb_data['term_18m'] = rate
#                                 elif '24 THÁNG' in term_text and vcb_data.get('term_24m') is None:
#                                     vcb_data['term_24m'] = rate
#                                 elif '36 THÁNG' in term_text and vcb_data.get('term_36m') is None:
#                                     vcb_data['term_36m'] = rate
#                                 break
#                         except ValueError:
#                             continue

#     finally:
#         driver_vcb.quit()

#     has_vcb_data = any(value is not None for key, value in vcb_data.items() if key.startswith('term_'))

#     if has_vcb_data:
#         with engine.connect() as conn:
#             result = conn.execute(text(f"SELECT COUNT(*) FROM vn_bank_termdepo WHERE bank_code = 'VCB' AND date = '{date_str}'"))
#             exists = result.scalar() > 0

#         if exists:
#             print(f"⚠️  VCB term deposit data for {date_str} already exists, skipping insert")
#         else:
#             vcb_df = pd.DataFrame([vcb_data])
#             vcb_df['date'] = pd.to_datetime(vcb_df['date'])
#             vcb_df.to_sql('vn_bank_termdepo', engine, if_exists='append', index=False)
#             print(f"✅ Pushed Vietcombank term deposit rates for {date_str}")
#             rates_list = [f'{k.replace("term_", "").upper()}: {v}%' for k, v in vcb_data.items() if k.startswith('term_') and v is not None]
#             print(f"   Rates: {rates_list}")
#     else:
#         print(f"⚠️  No Vietcombank term deposit data found")

# except Exception as e:
#     print(f"❌ Error crawling Vietcombank term deposit: {e}")


# ############## Global Macro Data from Yahoo Finance
# print("\n" + "="*60)
# print("Crawling Global Macro Data from Yahoo Finance")
# print("="*60)

# try:
#     import yfinance as yf

#     # Define tickers
#     # GC=F: Gold Futures ($/oz)
#     # SI=F: Silver Futures ($/oz)
#     # ^IXIC: NASDAQ Composite Index
#     tickers = {
#         'gold': 'GC=F',      # Gold Futures
#         'silver': 'SI=F',    # Silver Futures
#         'nasdaq': '^IXIC'    # NASDAQ Composite
#     }

#     global_macro_data = {
#         'date': date_str,
#         'crawl_time': datetime.now(),
#         'gold_price': None,
#         'silver_price': None,
#         'nasdaq_price': None
#     }

#     # Helper function to fetch with retry logic
#     def fetch_with_retry(ticker_symbol, max_retries=3, initial_delay=2):
#         """Fetch ticker data with exponential backoff retry"""
#         for attempt in range(max_retries):
#             try:
#                 ticker = yf.Ticker(ticker_symbol)
#                 hist = ticker.history(period='1d')
#                 if not hist.empty:
#                     return float(hist['Close'].iloc[-1])
#                 else:
#                     print(f"    Attempt {attempt + 1}/{max_retries}: No data returned for {ticker_symbol}")
#             except Exception as e:
#                 error_msg = str(e)
#                 if "Rate limited" in error_msg or "Too Many Requests" in error_msg:
#                     if attempt < max_retries - 1:
#                         delay = initial_delay * (2 ** attempt)  # Exponential backoff
#                         print(f"    Rate limited, waiting {delay}s before retry {attempt + 2}/{max_retries}...")
#                         time.sleep(delay)
#                         continue
#                     else:
#                         raise Exception(f"Rate limited after {max_retries} attempts")
#                 else:
#                     raise e
#         return None

#     # Fetch gold price with retry
#     try:
#         print("  Fetching Gold Futures (GC=F)...")
#         gold_price = fetch_with_retry(tickers['gold'])
#         if gold_price:
#             global_macro_data['gold_price'] = gold_price
#             print(f"  ✅ Gold (GC=F): ${global_macro_data['gold_price']:.2f}/oz")
#         else:
#             print(f"  ⚠️  No gold price data available")
#     except Exception as e:
#         print(f"  ❌ Failed to fetch gold price: {e}")

#     # Wait between requests to avoid rate limiting
#     time.sleep(1)

#     # Fetch silver price with retry
#     try:
#         print("  Fetching Silver Futures (SI=F)...")
#         silver_price = fetch_with_retry(tickers['silver'])
#         if silver_price:
#             global_macro_data['silver_price'] = silver_price
#             print(f"  ✅ Silver (SI=F): ${global_macro_data['silver_price']:.2f}/oz")
#         else:
#             print(f"  ⚠️  No silver price data available")
#     except Exception as e:
#         print(f"  ❌ Failed to fetch silver price: {e}")

#     # Wait between requests to avoid rate limiting
#     time.sleep(1)

#     # Fetch NASDAQ price with retry
#     try:
#         print("  Fetching NASDAQ Composite (^IXIC)...")
#         nasdaq_price = fetch_with_retry(tickers['nasdaq'])
#         if nasdaq_price:
#             global_macro_data['nasdaq_price'] = nasdaq_price
#             print(f"  ✅ NASDAQ (^IXIC): {global_macro_data['nasdaq_price']:,.2f}")
#         else:
#             print(f"  ⚠️  No NASDAQ price data available")
#     except Exception as e:
#         print(f"  ❌ Failed to fetch NASDAQ price: {e}")

#     # Check if we have at least one data point
#     has_data = any(global_macro_data[key] is not None for key in ['gold_price', 'silver_price', 'nasdaq_price'])

#     if has_data:
#         # Check if data already exists for today in NEW DB
#         with global_indicator_engine.connect() as conn:
#             result = conn.execute(text(f"SELECT COUNT(*) FROM global_macro WHERE date = '{date_str}'"))
#             exists = result.scalar() > 0

#         if exists:
#             print(f"⚠️  Global macro data for {date_str} already exists, skipping insert")
#         else:
#             # Insert into NEW database (global_indicator)
#             macro_df = pd.DataFrame([global_macro_data])
#             macro_df['date'] = pd.to_datetime(macro_df['date'])
#             macro_df.to_sql('global_macro', global_indicator_engine, if_exists='append', index=False)
#             print(f"✅ Pushed global macro data to global_indicator DB for {date_str}")
#     else:
#         print(f"⚠️  No global macro data fetched")

# except ImportError:
#     print("❌ yfinance library not installed. Run: pip install yfinance")
# except Exception as e:
#     print(f"❌ Error crawling global macro data: {e}")