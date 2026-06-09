"""Run migration 010 on KNOWLEDGE_MARKET_DB — adds price_usd column to knowledge_products."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load from project root .env (one level above be/)
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
# Fallback: also try be/.env for backwards compatibility
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "010_pricing_usd.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 010 applied successfully to KNOWLEDGE_MARKET_DB")
