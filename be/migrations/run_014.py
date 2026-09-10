"""Run migration 014 on KNOWLEDGE_MARKET_DB (widen credit_ledger.kind CHECK
to allow 'subscription_charge')."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "014_credit_ledger_subscription_kind.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    row = conn.execute(text("""
        SELECT conname, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'credit_ledger'::regclass AND contype = 'c'
    """)).first()
    print("credit_ledger CHECK constraint now:", row)

print("Migration 014 applied successfully to KNOWLEDGE_MARKET_DB")
