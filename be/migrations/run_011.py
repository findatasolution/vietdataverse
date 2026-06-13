"""Run migration 011 (user analytics & API metering) on USER_DB."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("USER_DB env var not set")

sql_path = Path(__file__).resolve().parent / "011_user_analytics.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 011 applied successfully.")
print("  - users.last_login_at / login_count added")
print("  - login_events table created")
print("  - api_usage_monthly / api_call_log formalized + indexed")
