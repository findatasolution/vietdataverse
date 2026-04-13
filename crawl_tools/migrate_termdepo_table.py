"""
One-time migration: copy missing rows from vn_bank_termdepo → vn_macro_termdepo_daily.

Both tables share the same schema (bank_code, date, term_* columns).
This script copies every row in vn_bank_termdepo that does not yet exist
in vn_macro_termdepo_daily (dedup key: bank_code + date).

Run:
    cd /path/to/nguyenphamdieuhien
    python crawl_tools/migrate_termdepo_table.py [--dry-run] [--from-date 2026-03-01]
"""

import os
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "vietdataverse" / "be" / ".env")
DB_URL = os.getenv("CRAWLING_BOT_DB")
if not DB_URL:
    sys.exit("ERROR: CRAWLING_BOT_DB env var not set")

engine = create_engine(DB_URL, pool_pre_ping=True)

parser = argparse.ArgumentParser(description="Migrate vn_bank_termdepo → vn_macro_termdepo_daily")
parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing")
parser.add_argument("--from-date", default=None,
                    help="Only migrate rows on or after this date (YYYY-MM-DD). "
                         "Defaults to first date missing in vn_macro_termdepo_daily.")
args = parser.parse_args()

TERM_COLS = [
    "term_1m", "term_2m", "term_3m", "term_6m",
    "term_9m", "term_12m", "term_13m", "term_18m", "term_24m", "term_36m",
]

with engine.connect() as conn:
    # ── 1. Check both tables exist ──────────────────────────────────────────
    for tbl in ("vn_bank_termdepo", "vn_macro_termdepo_daily"):
        exists = conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t)"
        ), {"t": tbl}).scalar()
        if not exists:
            sys.exit(f"ERROR: table '{tbl}' not found in the database")

    # ── 2. Check actual columns in both tables ─────────────────────────────
    def get_cols(table):
        rows = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t ORDER BY ordinal_position"
        ), {"t": table}).fetchall()
        return [r[0] for r in rows]

    src_cols = get_cols("vn_bank_termdepo")
    dst_cols = get_cols("vn_macro_termdepo_daily")
    print(f"\nvn_bank_termdepo     columns: {src_cols}")
    print(f"vn_macro_termdepo_daily columns: {dst_cols}")

    # Common transferable columns (exclude id — will be regenerated)
    common = [c for c in src_cols if c in dst_cols and c != "id"]
    print(f"\nColumns to copy: {common}")

    # ── 3. Determine date range ────────────────────────────────────────────
    if args.from_date:
        from_date = args.from_date
    else:
        # Auto-detect: day after the latest date in vn_macro_termdepo_daily
        last_date = conn.execute(
            text("SELECT MAX(date) FROM vn_macro_termdepo_daily")
        ).scalar()
        if last_date is None:
            from_date = "2000-01-01"
        else:
            # Go back 7 days for safety (in case some days were missed before bug)
            from datetime import timedelta
            from_date = (last_date - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"\nAuto from_date: {from_date}  (last in dst: {last_date})")

    # ── 4. Find rows in source NOT in destination ──────────────────────────
    missing_rows = conn.execute(text(f"""
        SELECT src.*
        FROM vn_bank_termdepo src
        WHERE src.date >= :from_date
          AND NOT EXISTS (
              SELECT 1 FROM vn_macro_termdepo_daily dst
              WHERE dst.bank_code = src.bank_code
                AND dst.date      = src.date
          )
        ORDER BY src.date, src.bank_code
    """), {"from_date": from_date}).fetchall()

    col_names_from_query = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'vn_bank_termdepo' ORDER BY ordinal_position"
    )).fetchall()
    src_col_order = [r[0] for r in col_names_from_query]

    print(f"\nRows missing in vn_macro_termdepo_daily (from {from_date}): {len(missing_rows)}")

    if not missing_rows:
        print("Nothing to migrate. Tables are already in sync.")
        sys.exit(0)

    # Show preview
    print("\nPreview (first 10 rows):")
    print(f"  {'bank_code':<10} {'date':<12} {'term_1m':<10} {'term_3m':<10} "
          f"{'term_6m':<10} {'term_12m':<10}")
    print("  " + "-" * 60)
    for row in missing_rows[:10]:
        d = dict(zip(src_col_order, row))
        print(f"  {str(d.get('bank_code','')):<10} {str(d.get('date','')):<12} "
              f"{str(d.get('term_1m','')):<10} {str(d.get('term_3m','')):<10} "
              f"{str(d.get('term_6m','')):<10} {str(d.get('term_12m','')):<10}")

    if args.dry_run:
        print(f"\n[DRY RUN] Would insert {len(missing_rows)} rows. Run without --dry-run to apply.")
        sys.exit(0)

    # ── 5. Insert missing rows ─────────────────────────────────────────────
    # Get next id starting point
    max_id = conn.execute(
        text("SELECT COALESCE(MAX(id), 0) FROM vn_macro_termdepo_daily")
    ).scalar()

    inserted = 0
    skipped  = 0

    for row in missing_rows:
        record = dict(zip(src_col_order, row))

        # Build insert dict — only columns that exist in destination
        insert_data = {c: record[c] for c in common if c in record}
        insert_data["crawl_time"] = insert_data.get("crawl_time") or datetime.now()

        # Assign new id
        max_id += 1
        insert_data["id"] = max_id

        try:
            col_list  = ", ".join(insert_data.keys())
            val_list  = ", ".join(f":{k}" for k in insert_data.keys())
            conn.execute(
                text(f"INSERT INTO vn_macro_termdepo_daily ({col_list}) VALUES ({val_list})"),
                insert_data
            )
            inserted += 1
        except Exception as e:
            print(f"  SKIP {record.get('bank_code')} {record.get('date')}: {e}")
            skipped += 1

    conn.commit()

print(f"\n{'='*50}")
print(f"Migration complete.")
print(f"  Inserted : {inserted}")
print(f"  Skipped  : {skipped}")
print(f"  Total    : {len(missing_rows)}")
print(f"\nNext step: verify chart shows updated data, then commit & push")
print(f"  crawler fix (bank_code) + new workflow pointing to vn_macro_termdepo_daily.")
