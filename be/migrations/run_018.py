"""Run migration 018 on GLOBAL_INDICATOR_DB (global_lbma_gold_forecast table)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("GLOBAL_INDICATOR_DB")
if not DB_URL:
    sys.exit("GLOBAL_INDICATOR_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "018_lbma_gold_forecast_survey.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    cols = conn.execute(text("""
        SELECT column_name, data_type FROM information_schema.columns
        WHERE table_name = 'global_lbma_gold_forecast' ORDER BY ordinal_position
    """)).fetchall()
    print("global_lbma_gold_forecast columns:")
    for c in cols:
        print(f"  {c[0]:<16} {c[1]}")
