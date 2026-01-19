"""
Standalone Silver Price Crawler
Can be run multiple times per day to capture intraday price movements
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
from sqlalchemy import create_engine, text
import time

# Database connection
import os
from dotenv import load_dotenv
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

# Setup Chrome
chrome_options = Options()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.add_argument('--disable-gpu')
if sys.platform == 'linux':
    chrome_options.binary_location = '/usr/bin/chromium-browser'

driver = webdriver.Chrome(options=chrome_options)

try:
    print("============================================================")
    print("Silver Price Crawler - Phu Quy")
    print("============================================================")

    driver.get('https://giabac.vn/')
    time.sleep(2)

    # Click "Lượng" button to filter by unit
    buttons = driver.find_elements(By.TAG_NAME, 'button')
    for btn in buttons:
        if 'Lượng' in btn.text or 'luong' in btn.text.lower():
            btn.click()
            time.sleep(2)
            break

    # Get prices
    price_div = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, 'priceDiv'))
    )
    price_elements = price_div.find_elements(By.CSS_SELECTOR, 'p.text-24px')

    if len(price_elements) >= 2:
        buy_price = float(price_elements[0].text.strip().replace(',', '').replace('.', ''))
        sell_price = float(price_elements[1].text.strip().replace(',', '').replace('.', ''))

        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        # Insert into database (ON CONFLICT DO NOTHING to avoid duplicates)
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO vn_silver_phuquy_hist (date, crawl_time, buy_price, sell_price)
                    VALUES (:date, :crawl_time, :buy_price, :sell_price)
                    ON CONFLICT (date, crawl_time) DO NOTHING
                """),
                {
                    'date': date_str,
                    'crawl_time': now,
                    'buy_price': buy_price,
                    'sell_price': sell_price
                }
            )
            conn.commit()

        print(f"✅ Silver crawled at {time_str}")
        print(f"   Buy:  {buy_price:,.0f} VND")
        print(f"   Sell: {sell_price:,.0f} VND")
        print("============================================================")
    else:
        print("❌ Failed to extract prices from page")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
finally:
    driver.quit()
