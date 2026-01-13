"""
Initialize global_macro table in Neon PostgreSQL
Run this once to create the table before running crawl_bot.py
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from sqlalchemy import create_engine, text

conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

# Create table
create_table_query = text("""
CREATE TABLE IF NOT EXISTS global_macro (
    date DATE PRIMARY KEY,
    crawl_time TIMESTAMP NOT NULL,
    gold_price NUMERIC(10, 2),
    silver_price NUMERIC(10, 2),
    nasdaq_price NUMERIC(10, 2)
)
""")

try:
    with engine.connect() as conn:
        conn.execute(create_table_query)
        conn.commit()
        print("✅ Table 'global_macro' created successfully!")
        print("\nTable schema:")
        print("  - date: DATE (PRIMARY KEY)")
        print("  - crawl_time: TIMESTAMP")
        print("  - gold_price: NUMERIC(10,2) - Gold futures price in $/oz")
        print("  - silver_price: NUMERIC(10,2) - Silver futures price in $/oz")
        print("  - nasdaq_price: NUMERIC(10,2) - NASDAQ Composite index")

except Exception as e:
    print(f"❌ Error creating table: {e}")