"""One-shot backfill helper: fill fuel_price_cycle gaps using a real-date
oracle instead of calendar guessing.

METHODOLOGY (per user decision 2026-09-16 — combine option 2 + option 3,
ranked below option 1 which does not exist for this source; see
docs/superpowers/plans/2026-09-15-fuel-forecast-data-quality-roadmap.md):

  1. Date discovery (option 2, free dataset): Kaggle dataset
     "suthcong/fuel-prices-in-vietnam" (Petrolimex_oilprice.csv), downloaded
     anonymously via `kagglehub` (no API key). It has Petrolimex's own
     Zone 1/2 retail prices per real cycle date, 2022-12-01 -> 2026-04-16.
     We use it ONLY to know *which dates had a real MOIT cycle* — its
     retail_price does NOT go into fuel_price_cycle directly (see below).
  2. Value fetch (still MOIT, the official source): for each Kaggle-real
     date not already in fuel_price_cycle, we still fetch and parse the
     actual MOIT bulletin (be/fuel/moit_parser.py, same regex pipeline as
     the live crawler) to get world_avg_price (MOPS) AND the official
     retail ceiling price. Kaggle has no MOPS column, so MOIT stays the
     source of record for every number that lands in the DB; `source`
     column on each inserted row is the literal MOIT URL, same as every
     other row in this table.
  3. Validation: Kaggle's retail_price is used as an INDEPENDENT
     cross-check against what we just parsed from MOIT (not a replacement)
     -- large disagreement (>2%, well above the ~0.04% zone1-vs-ceiling
     noise seen on known-good rows) flags a probable mis-parse or wrong-date
     match for manual review, rather than trusting the regex silently.

Why "option 3" (deep research / search) still matters here: MOIT's slug
format changed across eras (5+ patterns found this session), so even with a
*confirmed real date* from Kaggle, the bulletin isn't always at a guessable
URL. Where the pattern list below misses, a human WebSearch pass can often
still find it (see session notes) -- this script only tries the pattern
list; it reports remaining misses instead of guessing further.

Run:  python crawl_tools/backfill_moit_fuel_kaggle_assisted.py
"""
import csv
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
from be.fuel.moit_parser import parse_moit  # noqa: E402

load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
DB_URL = os.environ["FUEL_FORECAST_DB"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}

KAGGLE_CSV = Path.home() / ".cache/kagglehub/datasets/suthcong/fuel-prices-in-vietnam/versions/50/Petrolimex_oilprice.csv"

CATEGORIES = [
    "tin-tuc",
    "tin-tuc/thi-truong-trong-nuoc",
    "tin-tuc/thong-bao",
    "tin-tuc/doanh-nghiep/doanh-nghiep-trong-nuoc",
    "tin-tuc/thi-truong-nuoc-ngoai",
]
SLUGS = [
    "mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{d}-{m}-{y}.html",
    "mot-so-thong-tin-dieu-hanh-gia-xang-dau-tai-ky-dieu-hanh-ngay-{d}-{m}-{y}.html",
    "thong-tin-dieu-hanh-xang-dau-ngay-{d:02d}-{m}-{y}.html",
    "thong-tin-dieu-hanh-gia-xang-dau-ngay-{d:02d}-{m}-{y}.html",
]


def load_kaggle_real_dates() -> dict[date, dict[str, float]]:
    """Returns {date: {'E5RON92': zone1_price, 'DO005S': zone1_price}} for
    real (non-blank) Kaggle rows."""
    out = {}
    with open(KAGGLE_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            e5 = row["Xăng E5 RON 92-II zone1_price"].strip()
            do = row["DO 0,05S-II zone1_price"].strip()
            if e5 or do:
                d = date.fromisoformat(row["Date"])
                out[d] = {
                    "E5RON92": float(e5) if e5 else None,
                    "DO005S": float(do) if do else None,
                }
    return out


def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=False)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    if "Xin lỗi! Liên kết không tồn tại" in r.text or "Không tìm thấy" in r.text:
        return None
    return r.text


def try_date(d: date):
    for cat in CATEGORIES:
        for slug in SLUGS:
            url = f"https://moit.gov.vn/{cat}/{slug.format(d=d.day, m=d.month, y=d.year)}"
            html = fetch(url)
            time.sleep(0.15)
            if html:
                rows = parse_moit(html, d)
                if rows:
                    return rows, url
    return None, None


def existing_periods() -> set[date]:
    proc = subprocess.run(
        ["psql", DB_URL, "-t", "-A", "-c", "SELECT DISTINCT period FROM fuel_price_cycle ORDER BY period"],
        capture_output=True, text=True,
    )
    return {date.fromisoformat(line.strip()) for line in proc.stdout.splitlines() if line.strip()}


def insert_rows(period: date, rows, source_url: str) -> tuple[bool, str]:
    now = datetime.now(timezone.utc).isoformat()
    values = []
    for r in rows:
        values.append(
            f"('{period.isoformat()}','{r.fuel}',{r.retail_price},{r.world_avg_price},"
            f"'{now}',$${source_url}$$,'commodity')"
        )
    sql = (
        "INSERT INTO fuel_price_cycle (period, fuel, retail_price, world_avg_price, crawl_time, source, group_name) "
        "VALUES " + ",".join(values) + " ON CONFLICT (fuel, period) DO NOTHING;"
    )
    proc = subprocess.run(["psql", DB_URL, "-v", "ON_ERROR_STOP=1", "-c", sql], capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr


def main():
    known = existing_periods()
    kaggle = load_kaggle_real_dates()
    candidates = sorted(d for d in kaggle if d not in known)
    print(f"existing periods: {len(known)} | Kaggle real dates: {len(kaggle)} | new candidates: {len(candidates)}")

    found, moit_missing, validation_flags = [], [], []

    for d in candidates:
        rows, url = try_date(d)
        if not rows:
            moit_missing.append(d)
            print(f"{d} -> MOIT not found (Kaggle confirms cycle is real; needs manual WebSearch pass)")
            continue

        # Cross-validate against Kaggle's independent retail_price per fuel
        for r in rows:
            kag = kaggle[d].get(r.fuel)
            if kag:
                pct = abs(r.retail_price - kag) / kag
                if pct > 0.02:  # >2% is well above the ~0.04% zone1-vs-ceiling noise seen on known-good rows
                    validation_flags.append((d, r.fuel, r.retail_price, kag, pct))

        ok, err = insert_rows(d, rows, url)
        print(f"{d} -> HIT fuels={[r.fuel for r in rows]} insert_ok={ok} url={url}")
        if not ok:
            print("   insert error:", err[:300])
        found.append(d)

    print(f"\nDONE. found={len(found)} moit_missing={len(moit_missing)} validation_flags={len(validation_flags)}")
    if validation_flags:
        print("\nVALIDATION FLAGS (MOIT-parsed vs Kaggle-retail differ >2% — review before trusting):")
        for d, fuel, parsed, kag, pct in validation_flags:
            print(f"  {d} {fuel}: MOIT={parsed} Kaggle={kag} ({pct*100:.1f}% diff)")
    if moit_missing:
        print(f"\n{len(moit_missing)} Kaggle-confirmed real dates had no matching MOIT bulletin under the known "
              f"URL patterns — candidates for a manual WebSearch pass (option 3), not auto-inserted (no "
              f"world_avg_price available without MOIT):")
        for d in moit_missing:
            print(f"  {d}")


if __name__ == "__main__":
    main()
