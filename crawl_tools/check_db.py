#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine, text

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

try:
    engine = create_engine(CRAWLING_BOT_DB)
    with engine.connect() as conn:
        # Check if tables exist
        tables = ['vn_silver_phuquy_hist', 'vn_gold_24h_hist']
        for table in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                print(f'{table}: {count} records')
                
                # Get recent dates
                result = conn.execute(text(f"SELECT DISTINCT date FROM {table} ORDER BY date DESC LIMIT 5"))
                dates = [row[0] for row in result]
                print(f'  Recent dates: {dates}')
                
                # Check table structure
                result = conn.execute(text(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}' ORDER BY ordinal_position"))
                print(f'  Columns:')
                for col_name, data_type in result:
                    print(f'    {col_name}: {data_type}')
                print()
            except Exception as e:
                print(f'{table}: Error - {e}')
                print()
                
except Exception as e:
    print(f'Error connecting to database: {e}')
