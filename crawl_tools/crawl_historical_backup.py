import pandas as pd

import requests
import json
from sqlalchemy import create_engine


conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)
start_date = "2000-01-01"
end_date = pd.to_datetime("today").strftime("%Y-%m-%d")

# Crawl domestic silver prices from giabac.vn (1 year history)
url = "https://giabac.vn/SilverInfo/GetGoldPriceChartFromSQLData?days=30&type=L"
response = requests.get(url)
data = response.json()

# Create domestic_silver DataFrame
domestic_silver = pd.DataFrame({
    'date': pd.to_datetime(data['Dates']),
    'buy_price': data['LastBuyPrices'],
    'sell_price': data['LastSellPrices']
})

domestic_silver = domestic_silver.sort_values(by='date').reset_index(drop=True)
domestic_silver = domestic_silver.reset_index(drop=True)
domestic_silver.to_sql('vn_gold_24h_dojihn_hist', engine, if_exists='append', index=False)
print(f"✅ Pushed {len(domestic_silver)} records")



###############GOLD
# Crawl gold prices from 24h.com.vn
from bs4 import BeautifulSoup
import requests
import time
from tqdm import tqdm

def crawl_gold_price_24h(date_str):
    """
    Crawl DOJI HN gold prices from 24h.com.vn for a specific date
    date_str format: 'YYYY-MM-DD'
    Returns: dict with buy and sell prices for DOJI HN gold
    """
    url = f'https://www.24h.com.vn/gia-vang-hom-nay-c425.html?ngaythang={date_str}'
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the gold price table
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    brand = cols[0].get_text(strip=True)
                    # Look for DOJI HN brand
                    if 'DOJI' in brand and 'HN' in brand:
                        try:
                            buy_price_text = cols[1].get_text(strip=True)
                            sell_price_text = cols[3].get_text(strip=True)
                            
                            # Remove dots (thousand separators) and convert
                            buy_price = buy_price_text.replace('.', '').replace(',', '')
                            sell_price = sell_price_text.replace('.', '').replace(',', '')
                            
                            # Convert to float (prices are in thousands VND)
                            buy_price = float(buy_price) * 1000
                            sell_price = float(sell_price) * 1000
                            
                            return {
                                'date': date_str,
                                'buy_price_vnd_per_tael': buy_price,
                                'sell_price_vnd_per_tael': sell_price,
                                'brand': brand
                            }
                        except (ValueError, IndexError) as e:
                            print(f"Parse error for {brand}: {e}")
                            continue
        
        return None
        
    except Exception as e:
        print(f"Error crawling {date_str}: {e}")
        return None

# Run the crawl (with progress bar and rate limiting)
gold_data_list = []

for date in tqdm(date_range):
    date_str = date.strftime('%Y-%m-%d')
    result = crawl_gold_price_24h(date_str)
    
    if result:
        gold_data_list.append(result)
    
    # Rate limiting: sleep to avoid overwhelming the server
    time.sleep(0.5)  # 0.5 seconds between requests
    
    # Save progress every 100 records
    if len(gold_data_list) % 100 == 0:
        print(f"\nProgress: {len(gold_data_list)} records collected...")

# Create domestic_gold DataFrame
if gold_data_list:
    domestic_gold = pd.DataFrame(gold_data_list)
    domestic_gold['date'] = pd.to_datetime(domestic_gold['date'])
    domestic_gold = domestic_gold.sort_values(by='date').reset_index(drop=True)
    
    # print(f"\nSuccessfully crawled {len(domestic_gold)} records!")
    # print(f"Date range: {domestic_gold['date'].min()} to {domestic_gold['date'].max()}")
    domestic_gold.tail(10)
else:
    print("No data collected. Please check the website structure or your internet connection.")
    
domestic_gold.to_sql('vn_gold_24h_dojihn_hist', engine, if_exists='append', index=False)
print(f"✅ Pushed {len(domestic_gold)} records")