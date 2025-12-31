"""Add sample data to test CSV download"""
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta

conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

# Generate last 30 days of sample data
end_date = datetime.now()
dates = [(end_date - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30)]

# Sample Gold data
gold_data = pd.DataFrame({
    'date': pd.to_datetime(dates),
    'buy_price': [83500000 + (i * 10000) for i in range(30)],
    'sell_price': [84000000 + (i * 10000) for i in range(30)]
})

# Sample Silver data
silver_data = pd.DataFrame({
    'date': pd.to_datetime(dates),
    'buy_price': [750000 + (i * 1000) for i in range(30)],
    'sell_price': [780000 + (i * 1000) for i in range(30)]
})

# Sample SBV Interbank data
sbv_data = pd.DataFrame({
    'date': pd.to_datetime(dates),
    'crawl_time': [datetime.now() for _ in range(30)],
    'ls_quadem': [4.5 + (i * 0.01) for i in range(30)],
    'doanhso_quadem': [5000 + (i * 100) for i in range(30)],
    'ls_1w': [4.6 + (i * 0.01) for i in range(30)],
    'doanhso_1w': [6000 + (i * 100) for i in range(30)],
    'ls_2w': [4.65 + (i * 0.01) for i in range(30)],
    'doanhso_2w': [5500 + (i * 100) for i in range(30)],
    'ls_1m': [4.7 + (i * 0.01) for i in range(30)],
    'doanhso_1m': [7000 + (i * 100) for i in range(30)],
    'ls_3m': [4.8 + (i * 0.01) for i in range(30)],
    'doanhso_3m': [8000 + (i * 100) for i in range(30)],
    'ls_6m': [4.9 + (i * 0.01) for i in range(30)],
    'doanhso_6m': [9000 + (i * 100) for i in range(30)],
    'ls_9m': [5.0 + (i * 0.01) for i in range(30)],
    'doanhso_9m': [10000 + (i * 100) for i in range(30)]
})

# Insert data
try:
    gold_data.to_sql('vn_gold_24h_dojihn_hist', engine, if_exists='append', index=False)
    print(f"Added {len(gold_data)} gold records")
except Exception as e:
    print(f"Gold error: {e}")

try:
    silver_data.to_sql('vn_silver_phuquy_hist', engine, if_exists='append', index=False)
    print(f"Added {len(silver_data)} silver records")
except Exception as e:
    print(f"Silver error: {e}")

try:
    sbv_data.to_sql('vn_sbv_interbankrate', engine, if_exists='append', index=False)
    print(f"Added {len(sbv_data)} SBV interbank records")
except Exception as e:
    print(f"SBV error: {e}")

print("Sample data added successfully!")
