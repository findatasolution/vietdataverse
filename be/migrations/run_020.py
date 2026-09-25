"""Run migration 020 on USER_DB (users.email must never be blank)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("USER_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "020_users_email_not_blank.sql"
engine = create_engine(DB_URL)

with engine.begin() as conn:
    before = conn.execute(text("SELECT count(*) FROM users WHERE btrim(email) = ''")).scalar()
    print(f"blank-email rows before: {before}")
    conn.execute(text(sql_path.read_text(encoding="utf-8")))
    after = conn.execute(text("SELECT count(*) FROM users WHERE btrim(email) = ''")).scalar()
    print(f"blank-email rows after:  {after}")

    constraint = conn.execute(text("""
        SELECT pg_get_constraintdef(oid) FROM pg_constraint
        WHERE conrelid = 'users'::regclass AND conname = 'users_email_not_blank'
    """)).scalar()
    print("constraint:", constraint)

    # The point of the migration: a blank email must now be rejected by the DB
    # itself. Probe inside a savepoint and roll back so no fake user is stored.
    savepoint = conn.begin_nested()
    try:
        conn.execute(text(
            "INSERT INTO users (email, auth0_id, user_level) "
            "VALUES ('', '__migration_020_probe__', 'free')"
        ))
        print("blank insert: STILL ACCEPTED — constraint did not take effect")
        sys.exit(1)
    except Exception as exc:
        print(f"blank insert: rejected ({type(exc).__name__}) — as intended")
    finally:
        savepoint.rollback()
