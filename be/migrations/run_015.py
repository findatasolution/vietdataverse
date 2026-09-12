"""Run migration 015 on KNOWLEDGE_MARKET_DB (cancel_at_period_end flag)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "015_cancel_at_period_end.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    col = conn.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'platform_subscriptions'
          AND table_schema = 'public'
          AND column_name = 'cancel_at_period_end'
    """)).first()
    print("platform_subscriptions.cancel_at_period_end:", col)
    cols = [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='platform_subscriptions' AND table_schema='public' "
        "ORDER BY ordinal_position"
    ))]
    print("platform_subscriptions:", cols)
    # Existing rows must all read false — the default backfilled them, so no
    # live subscription silently acquired a pending cancellation.
    counts = conn.execute(text("""
        SELECT cancel_at_period_end, count(*) FROM platform_subscriptions
        GROUP BY cancel_at_period_end ORDER BY 1
    """)).fetchall()
    print("rows by cancel_at_period_end:", counts)

print("Migration 015 applied successfully to KNOWLEDGE_MARKET_DB")
