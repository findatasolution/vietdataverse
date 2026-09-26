"""Run migration 021 on KNOWLEDGE_MARKET_DB (credit_holds)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql = (Path(__file__).resolve().parent / "021_credit_holds.sql").read_text(encoding="utf-8")
engine = create_engine(DB_URL)

with engine.begin() as conn:
    conn.execute(text(sql))
    cols = [r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'credit_holds' ORDER BY ordinal_position"""))]
    print("credit_holds columns:", cols)

    # The point of the migration: a second active hold on the same ref must be
    # impossible. Probe inside a savepoint so nothing is stored.
    savepoint = conn.begin_nested()
    ok = False
    try:
        for _ in range(2):
            conn.execute(text("""
                INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
                VALUES (-999, 1, 'probe', 'probe', -999, 'active', NOW())"""))
    except Exception as exc:
        ok = True
        print(f"double active hold: rejected ({type(exc).__name__}) — as intended")
    finally:
        savepoint.rollback()
    if not ok:
        sys.exit("double active hold: ACCEPTED — unique index missing")

    # A released hold must not block a new one, or a user could never retry.
    savepoint = conn.begin_nested()
    try:
        conn.execute(text("""
            INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at, released_at)
            VALUES (-998, 1, 'probe', 'probe', -998, 'released', NOW(), NOW())"""))
        conn.execute(text("""
            INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
            VALUES (-998, 1, 'probe', 'probe', -998, 'active', NOW())"""))
        print("released then active on same ref: accepted — as intended")
    finally:
        savepoint.rollback()
