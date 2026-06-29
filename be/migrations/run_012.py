"""Run migration 012 on GLOBAL_INDICATOR_DB (add source/group_name to global_macro)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load from project root .env (two levels above this file: be/migrations/ -> repo root)
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

DB_URL = os.getenv("GLOBAL_INDICATOR_DB")
if not DB_URL:
    sys.exit("GLOBAL_INDICATOR_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "012_global_macro_source_groupname.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    cols = [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='global_macro' AND table_schema='public' ORDER BY ordinal_position"))]

print("Migration 012 applied to GLOBAL_INDICATOR_DB")
print("global_macro columns:", ", ".join(cols))
