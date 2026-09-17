"""Run migration 017 (user_identities) on USER_DB."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("USER_DB env var not set")

sql = (Path(__file__).resolve().parent / "017_user_identities.sql").read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 017 applied: user_identities table + index.")
