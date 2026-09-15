"""One-shot: drop base_price/bog_contrib/bog_use/taxes from fuel_price_cycle.

These columns were never actually parsed — moit_parser.py always set
base_price = retail_price (a duplicate, not a real "giá cơ sở") and
bog_contrib/bog_use/taxes always stayed at their defaults (0 / '{}'). Verified
2026-09-15 against all 74 live rows before writing this: 0 rows differ from
that pattern. Backup: be/migrations/fuel_price_cycle_unused_cols_backup_20260915.csv.

The model only ever consumed world_avg_price and retail_price (see
be/fuel/calibration.py CyclePoint) — these columns were designed-ahead-of-need
for a formula breakdown (Nghị định 80 components) that was never built out.

Run:  python be/migrations/fix_fuel_price_cycle_drop_unused_cols.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")


def main():
    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set")
    engine = create_engine(db_url)
    with engine.connect() as conn:
        mismatched = conn.execute(text("""
            SELECT count(*) FROM fuel_price_cycle
            WHERE base_price != retail_price OR bog_contrib != 0
               OR bog_use != 0 OR taxes != '{}'::jsonb
        """)).scalar()
        if mismatched:
            sys.exit(
                f"{mismatched} row(s) have non-default values in the columns "
                f"being dropped — re-check the backup before proceeding, this "
                f"script refuses to drop data that isn't provably unused."
            )
        conn.execute(text("""
            ALTER TABLE fuel_price_cycle
                DROP COLUMN base_price,
                DROP COLUMN bog_contrib,
                DROP COLUMN bog_use,
                DROP COLUMN taxes
        """))
        conn.commit()
        cols = conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'fuel_price_cycle' ORDER BY ordinal_position
        """)).fetchall()
        print("fuel_price_cycle columns now:", [r[0] for r in cols])


if __name__ == "__main__":
    main()
