"""Initialize database tables for Viet Dataverse"""
from sqlalchemy import create_engine, text

conn_str = 'postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
engine = create_engine(conn_str)

# Create tables with proper schema
tables = [
    """
    CREATE TABLE IF NOT EXISTS vn_gold_24h_dojihn_hist (
        date DATE PRIMARY KEY,
        buy_price FLOAT,
        sell_price FLOAT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vn_silver_phuquy_hist (
        date DATE PRIMARY KEY,
        buy_price FLOAT,
        sell_price FLOAT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vn_sbv_interbankrate (
        date DATE PRIMARY KEY,
        crawl_time TIMESTAMP,
        ls_quadem FLOAT,
        doanhso_quadem FLOAT,
        ls_1w FLOAT,
        doanhso_1w FLOAT,
        ls_2w FLOAT,
        doanhso_2w FLOAT,
        ls_1m FLOAT,
        doanhso_1m FLOAT,
        ls_3m FLOAT,
        doanhso_3m FLOAT,
        ls_6m FLOAT,
        doanhso_6m FLOAT,
        ls_9m FLOAT,
        doanhso_9m FLOAT
    )
    """
]

with engine.connect() as conn:
    for table_sql in tables:
        try:
            conn.execute(text(table_sql))
            conn.commit()
            print(f"Created table successfully")
        except Exception as e:
            print(f"Error: {e}")

print("Database initialization complete!")
