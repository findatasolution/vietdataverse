"""Run migration 006 on KNOWLEDGE_MARKET_DB."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB env var not set")

sql_path = Path(__file__).resolve().parent / "006_align_seller_zero_admin.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 006 applied successfully.")
print("  - seller_profiles.linkedin_url → nullable")
print("  - seller_profiles.apply_status CHECK → now includes 'auto_approved'")
