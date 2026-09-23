"""Run migration 019 on USER_DB (api_call_log.user_id → nullable)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("USER_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "019_api_call_log_nullable_user.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    col = conn.execute(text("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'api_call_log'
          AND column_name = 'user_id'
    """)).first()
    print("api_call_log.user_id:", col)

    # The whole point of the migration: an anonymous row must now insert.
    # Probe inside a savepoint and roll it back — this table feeds the admin
    # report, so a migration must not leave a fake call in it.
    savepoint = conn.begin_nested()
    try:
        conn.execute(text("""
            INSERT INTO api_call_log (user_id, api_key_id, endpoint, status_code)
            VALUES (NULL, NULL, '/__migration_019_probe__', 401)
        """))
        print("anonymous insert: OK (rolled back, nothing stored)")
    finally:
        savepoint.rollback()

    total = conn.execute(text("SELECT COUNT(*) FROM api_call_log")).scalar()
    anon = conn.execute(text("SELECT COUNT(*) FROM api_call_log WHERE user_id IS NULL")).scalar()
    print(f"api_call_log rows: {total} total, {anon} anonymous "
          f"(anonymous stays 0 until the next real anonymous call — history "
          f"before this migration was never recorded and cannot be recovered)")

print("Migration 019 applied successfully to USER_DB")
