"""
Historical backfill for vn_macro_termdepo_daily using Wayback Machine CDX API.

Strategy:
  1. For each bank, query CDX API for archived snapshots (1 per month)
  2. Fetch archived page via Selenium (handles JS-rendered Wayback pages)
  3. Parse with structured parser (parse_acb_structured)
  4. Insert into DB (skip dates already present)

Bank: ACB

Run:
    cd crawl_tools
    python enrich_termdepo_history.py [--bank ACB] [--from 2018] [--to 2024] [--dry-run]
"""

import sys, os, re, time, argparse
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))

from pathlib import Path
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Re-use helpers from main crawler
from crawl_tools.crawl_bank_termdepo import (
    validate_rates, extract_rate_from_text, extract_month_from_text,
    month_to_column, normalize_text, save_bank_data, parse_acb_structured,
)

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / "be" / ".env")
DB_URL = os.getenv("CRAWLING_BOT_DB")
if not DB_URL:
    sys.exit("CRAWLING_BOT_DB not set")
engine = create_engine(DB_URL, pool_pre_ping=True)

# ── CLI ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--bank",    default=None, help="Single bank code (default: all)")
parser.add_argument("--from",    dest="year_from", type=int, default=2018)
parser.add_argument("--to",      dest="year_to",   type=int, default=2024)
parser.add_argument("--dry-run", action="store_true", help="Parse but do not write to DB")
args = parser.parse_args()

DRY_RUN = args.dry_run

# ── Bank config ───────────────────────────────────────────────────────────────
BANKS = {
    "ACB": {"name": "ACB", "url": "https://acb.com.vn/lai-suat-tien-gui", "parser": parse_acb_structured},
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "vi-VN,vi;q=0.9",
}

# ── Wayback CDX API ───────────────────────────────────────────────────────────
CDX_API = "https://web.archive.org/cdx/search/cdx"

def get_snapshots(url: str, year_from: int, year_to: int) -> list:
    """Return list of {timestamp, url} — one per month."""
    # Try the exact URL and its domain prefix variants
    base_domain = re.sub(r'https?://(www\.)?', '', url).split('/')[0]
    path = '/' + '/'.join(re.sub(r'https?://(www\.)?', '', url).split('/')[1:])

    params = {
        "url":       url,
        "output":    "json",
        "from":      f"{year_from}0101",
        "to":        f"{year_to}1231",
        "fl":        "timestamp,original,statuscode",
        "collapse":  "timestamp:6",
        "filter":    "statuscode:200",
        "limit":     200,
        "matchType": "prefix",
    }
    try:
        r = requests.get(CDX_API, params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
        if len(data) <= 1:
            return []
        return [{"timestamp": row[0], "url": row[1]} for row in data[1:]]
    except Exception as e:
        print(f"    CDX error: {e}")
        return []

def fetch_wayback(timestamp: str, original_url: str) -> str:
    """Fetch Wayback Machine archived page via HTTP."""
    wb_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(wb_url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    Fetch error: {e}")
        return None

# ── DB helpers ────────────────────────────────────────────────────────────────
def existing_dates(bank_code: str) -> set:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT date_trunc('month', date)::date FROM vn_macro_termdepo_daily WHERE bank_code = :b"
        ), {"b": bank_code}).fetchall()
    return {r[0] for r in rows}

def insert_row(bank_code: str, snap_date: date, rates: dict):
    cols = ["bank_code", "date", "crawl_time"] + list(rates.keys())
    vals = {"bank_code": bank_code, "date": snap_date,
            "crawl_time": datetime.utcnow(), **rates}
    col_str  = ", ".join(cols)
    ph_str   = ", ".join(f":{c}" for c in cols)
    with engine.begin() as conn:
        conn.execute(text(
            f"INSERT INTO vn_macro_termdepo_daily ({col_str}) VALUES ({ph_str}) ON CONFLICT DO NOTHING"
        ), vals)

# ── Main ──────────────────────────────────────────────────────────────────────
def process_bank(bank_code: str, cfg: dict):
    print(f"\n{'─'*60}")
    print(f"Bank: {bank_code} ({cfg['name']})  [{args.year_from}–{args.year_to}]")

    already = existing_dates(bank_code)
    print(f"  Existing months in DB: {len(already)}")

    snapshots = get_snapshots(cfg["url"], args.year_from, args.year_to)
    snapshots.sort(key=lambda x: x["timestamp"])
    print(f"  Wayback snapshots found: {len(snapshots)}")

    if not snapshots:
        print("  No snapshots — skipping")
        return 0

    inserted = skipped = failed = 0

    for snap in snapshots:
        ts        = snap["timestamp"]
        snap_date = date(int(ts[:4]), int(ts[4:6]), 1)

        if snap_date in already:
            skipped += 1
            continue

        print(f"  {ts} → {snap_date} ...", end=" ", flush=True)

        html = fetch_wayback(ts, snap["url"])
        if not html:
            print("FETCH FAIL")
            failed += 1
            time.sleep(3)
            continue

        soup = BeautifulSoup(html, "html.parser")
        data = cfg["parser"](soup)

        if not validate_rates(data):
            print(f"PARSE FAIL ({list(data.keys())})")
            failed += 1
            time.sleep(2)
            continue

        terms = [f"{k}:{v}%" for k, v in sorted(data.items()) if k.startswith("term_")]
        print(f"OK  {', '.join(terms)}")

        if not DRY_RUN:
            insert_row(bank_code, snap_date, data)
            already.add(snap_date)

        inserted += 1
        time.sleep(4)  # polite Wayback delay

    print(f"  Done: +{inserted} inserted, {skipped} skipped, {failed} failed")
    return inserted


if __name__ == "__main__":
    if args.bank and args.bank not in BANKS:
        sys.exit(f"Unknown bank: {args.bank}. Available: {list(BANKS.keys())}")

    target = {args.bank: BANKS[args.bank]} if args.bank else BANKS

    print(f"\n{'='*60}")
    print(f"Term Deposit History Enrichment  [{args.year_from}–{args.year_to}]")
    print(f"Banks: {list(target.keys())}")
    if DRY_RUN:
        print("MODE: DRY RUN")
    print(f"{'='*60}")

    total = sum(process_bank(code, cfg) for code, cfg in target.items())

    print(f"\n{'='*60}")
    print(f"Total inserted: {total} rows")
