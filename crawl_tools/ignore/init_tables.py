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
        date DATE NOT NULL,
        crawl_time TIMESTAMP NOT NULL,
        buy_price FLOAT,
        sell_price FLOAT,
        PRIMARY KEY (date, crawl_time)
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
    """,
    """
    CREATE TABLE IF NOT EXISTS vn_bank_termdepo (
        id SERIAL PRIMARY KEY,
        bank_code VARCHAR(20) NOT NULL,
        date DATE NOT NULL,
        crawl_time TIMESTAMP NOT NULL,
        term_1m FLOAT,
        term_2m FLOAT,
        term_3m FLOAT,
        term_6m FLOAT,
        term_9m FLOAT,
        term_12m FLOAT,
        term_13m FLOAT,
        term_18m FLOAT,
        term_24m FLOAT,
        term_36m FLOAT,
        UNIQUE(bank_code, date)
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

# Migration 1: Add term_noterm column for VCB (no-term deposit rate)
migration_sql_1 = """
ALTER TABLE vn_bank_termdepo ADD COLUMN IF NOT EXISTS term_noterm FLOAT;
"""

with engine.connect() as conn:
    try:
        conn.execute(text(migration_sql_1))
        conn.commit()
        print("✅ Migration 1: Added term_noterm column for VCB")
    except Exception as e:
        print(f"Migration 1 note: {e}")

# Migration 2: Fix vn_silver_phuquy_hist to support multiple crawls per day
migration_sql_2 = """
-- Check if crawl_time column exists
DO $$
BEGIN
    -- Add crawl_time if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'vn_silver_phuquy_hist' AND column_name = 'crawl_time'
    ) THEN
        -- Add crawl_time column with default value
        ALTER TABLE vn_silver_phuquy_hist ADD COLUMN crawl_time TIMESTAMP;

        -- Update existing rows to set crawl_time = date at 08:30:00
        UPDATE vn_silver_phuquy_hist
        SET crawl_time = date + INTERVAL '8 hours 30 minutes'
        WHERE crawl_time IS NULL;

        -- Make crawl_time NOT NULL
        ALTER TABLE vn_silver_phuquy_hist ALTER COLUMN crawl_time SET NOT NULL;

        -- Drop old primary key and create new one
        ALTER TABLE vn_silver_phuquy_hist DROP CONSTRAINT vn_silver_phuquy_hist_pkey;
        ALTER TABLE vn_silver_phuquy_hist ADD PRIMARY KEY (date, crawl_time);

        RAISE NOTICE 'Migration 2: Silver table updated to support multiple crawls per day';
    END IF;
END $$;
"""

with engine.connect() as conn:
    try:
        conn.execute(text(migration_sql_2))
        conn.commit()
        print("✅ Migration 2: Fixed silver table schema")
    except Exception as e:
        print(f"Migration 2 note: {e}")

print("Database initialization complete!")
