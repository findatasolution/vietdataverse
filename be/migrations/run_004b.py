"""Run migration 004b on USER_DB — extends payment_orders for credit topup."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load from project root .env (one level above be/)
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
# Fallback: also try be/.env for backwards compatibility
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("USER_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "004b_payment_orders_topup.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 004b applied successfully to USER_DB")
