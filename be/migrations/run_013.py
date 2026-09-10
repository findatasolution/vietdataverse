"""Run migration 013 on KNOWLEDGE_MARKET_DB (platform subscriptions)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "013_platform_subscriptions.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    for table in ("platform_products", "platform_subscriptions", "platform_subscription_events"):
        cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:t AND table_schema='public' ORDER BY ordinal_position"
        ), {"t": table})]
        print(f"{table}: {cols}")
    seeded = conn.execute(text("SELECT code, price_credits, list_price_credits FROM platform_products")).fetchall()
    print("platform_products rows:", seeded)

print("Migration 013 applied successfully to KNOWLEDGE_MARKET_DB")
