#!/usr/bin/env python3
"""
Migration: Add & backfill mandatory fields (source, group_name) to all tables.

Steps per table:
  1. ADD COLUMN IF NOT EXISTS  — safe on new or old tables
  2. UPDATE ... SET            — backfill NULL rows with correct values
  3. ALTER COLUMN SET NOT NULL — enforce constraint

Run once per DB (CRAWLING_BOT_DB and CRAWLING_CORP_DB).

Usage:
  python crawl_tools/migrate_mandatory_fields.py
"""

import os, sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

CRAWLING_BOT_DB  = os.getenv('CRAWLING_BOT_DB')
CRAWLING_CORP_DB = os.getenv('CRAWLING_CORP_DB')

if not CRAWLING_BOT_DB:
    sys.exit("❌  CRAWLING_BOT_DB not set")

# ─────────────────────────────────────────────────────────────
# Migration spec: (table, source_value, group_value)
# source_value = None  →  column already existed with correct data (e.g. fxrate)
# ─────────────────────────────────────────────────────────────

BOT_TABLES = [
    # table                        source value                   group
    ("vn_macro_sbv_rate_daily",   "sbv.gov.vn",                  "finance"),
    ("vn_macro_termdepo_daily",   "acb.com.vn",                  "finance"),
    # fxrate: source col existed as 'Crawl'/'API' — only backfill group_name
    ("vn_macro_fxrate_daily",     None,                          "finance"),
    # gold: BTMC types get btmc source, rest get 24h.com.vn — handled with CASE
    ("vn_macro_gold_daily",       "__gold_case__",               "commodity"),
    ("vn_macro_silver_daily",     "phuquy.com.vn",               "commodity"),
    ("vn_gso_cpi_monthly",        "gso.gov.vn",                  "macro"),
    ("vn_gso_ppi_monthly",        "gso.gov.vn",                  "macro"),
    ("vn_gso_gdp_quarterly",      "gso.gov.vn",                  "macro"),
    ("vn_gso_trade_monthly",      "gso.gov.vn",                  "macro"),
    ("vn_gso_iip_monthly",        "gso.gov.vn",                  "macro"),
]

CORP_TABLES = [
    ("vn30_ohlcv_daily",              "vnstock3", "stock"),
    ("vn30_company_profile",          "vnstock3", "stock"),
    ("vn30_income_stmt_quarterly",    "vnstock3", "stock"),
    ("vn30_balance_sheet_quarterly",  "vnstock3", "stock"),
    ("vn30_cashflow_quarterly",       "vnstock3", "stock"),
    ("vn30_ratio_daily",              "vnstock3", "stock"),
]


def migrate_table(conn, table: str, source_val: str | None, group_val: str) -> dict:
    result = {"table": table, "source_added": False, "group_added": False,
              "source_updated": 0, "group_updated": 0, "errors": []}

    # ── 1. Add columns if missing ────────────────────────────
    try:
        conn.execute(text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS source TEXT"
        ))
    except Exception as e:
        result["errors"].append(f"ADD source: {e}")

    try:
        conn.execute(text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS group_name VARCHAR(20)"
        ))
    except Exception as e:
        result["errors"].append(f"ADD group_name: {e}")

    # ── 2. Backfill source (skip if None — column already meaningful) ─
    if source_val is not None and source_val != "__gold_case__":
        r = conn.execute(text(
            f"UPDATE {table} SET source = :src WHERE source IS NULL"
        ), {"src": source_val})
        result["source_updated"] = r.rowcount

    elif source_val == "__gold_case__":
        # Gold: BTMC-prefixed types come from btmc API; rest from 24h.com.vn
        r = conn.execute(text(f"""
            UPDATE {table}
            SET source = CASE
                WHEN type LIKE 'BTMC%' THEN 'api.btmc.vn'
                ELSE '24h.com.vn'
            END
            WHERE source IS NULL
        """))
        result["source_updated"] = r.rowcount

    # ── 3. Backfill group_name ────────────────────────────────
    r = conn.execute(text(
        f"UPDATE {table} SET group_name = :grp WHERE group_name IS NULL"
    ), {"grp": group_val})
    result["group_updated"] = r.rowcount

    # ── 4. Set NOT NULL (only after backfill) ────────────────
    # Check for remaining NULLs first
    null_check = conn.execute(text(
        f"SELECT COUNT(*) FROM {table} WHERE source IS NULL OR group_name IS NULL"
    )).scalar()

    if null_check == 0:
        try:
            conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN group_name SET NOT NULL"))
        except Exception as e:
            result["errors"].append(f"NOT NULL group_name: {e}")

        # Only set source NOT NULL if we managed source (not None case without existing data)
        if source_val is not None:
            try:
                conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN source SET NOT NULL"))
            except Exception as e:
                result["errors"].append(f"NOT NULL source: {e}")
    else:
        result["errors"].append(f"⚠️  {null_check} rows still NULL after backfill — NOT NULL skipped")

    return result


def run_migration(db_url: str, tables: list, db_label: str):
    engine = create_engine(db_url)
    print(f"\n{'='*60}")
    print(f"  Database: {db_label}")
    print(f"{'='*60}")

    with engine.begin() as conn:
        for table, source_val, group_val in tables:
            r = migrate_table(conn, table, source_val, group_val)
            status = "✅" if not r["errors"] else "⚠️ "
            print(f"\n{status} {table}")
            if source_val is not None:
                print(f"   source backfilled  : {r['source_updated']} rows → '{source_val}'")
            else:
                print(f"   source             : kept existing values")
            print(f"   group_name backfill: {r['group_updated']} rows → '{group_val}'")
            for err in r["errors"]:
                print(f"   ERROR: {err}")

    print(f"\n{'='*60}")
    print(f"  {db_label} migration complete.")
    print(f"{'='*60}\n")


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Mandatory Fields Migration — source, group_name         ║")
    print("╚══════════════════════════════════════════════════════════╝")

    run_migration(CRAWLING_BOT_DB, BOT_TABLES, "CRAWLING_BOT_DB")

    if CRAWLING_CORP_DB:
        run_migration(CRAWLING_CORP_DB, CORP_TABLES, "CRAWLING_CORP_DB")
    else:
        print("⏭️  CRAWLING_CORP_DB not set — skipping VN30 tables")

    print("✅  All done. Re-run stresstest_data_inventory.py to update Excel.")


if __name__ == "__main__":
    main()
