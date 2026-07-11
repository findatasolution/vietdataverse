"""Crawl MOIT fuel price-management announcements → Bronze (R2) → Silver (FUEL_FORECAST_DB).

Usage:
  python crawl_tools/crawl_moit_fuel.py <url> <YYYY-MM-DD>   # one specific cycle (backfill)
  python crawl_tools/crawl_moit_fuel.py                      # discover + crawl the latest cycle

Pattern (CLAUDE.md): land raw first, validate before insert, ON CONFLICT UPSERT,
explicit commit, sys.exit(1) on invalid data.
"""
import os
import re
import sys
from datetime import datetime, timezone, date
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fuel_raw_store as raw_store
from be.fuel.moit_parser import parse_moit, CycleRow

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

MOIT_NEWS_INDEX = "https://moit.gov.vn/tin-tuc/thi-truong-trong-nuoc"
UA = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}


def _engine():
    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set")
    return create_engine(db_url)


def fetch(url: str) -> tuple[str, int]:
    resp = requests.get(url, headers=UA, timeout=30)
    return resp.text, resp.status_code


def validate(rows: list[CycleRow]) -> bool:
    if not rows:
        return False
    for r in rows:
        # Wide bounds: refined-product world price can spike (diesel hit ~205 USD/bbl
        # in the 2026-03 cycle) and retail follows it — reject only implausible garbage.
        if not (30.0 <= r.world_avg_price <= 400.0):
            return False
        if not (10000 <= r.retail_price <= 60000):
            return False
    return True


def store(engine, period: date, rows: list[CycleRow], source_url: str) -> None:
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO fuel_price_cycle
                    (period, fuel, retail_price, base_price, world_avg_price,
                     bog_contrib, bog_use, taxes, crawl_time, source, group_name)
                VALUES
                    (:period, :fuel, :retail, :base, :world,
                     :bogc, :bogu, '{}'::jsonb, :ct, :src, 'commodity')
                ON CONFLICT (fuel, period) DO UPDATE SET
                    retail_price = EXCLUDED.retail_price,
                    base_price = EXCLUDED.base_price,
                    world_avg_price = EXCLUDED.world_avg_price,
                    crawl_time = EXCLUDED.crawl_time
            """), {
                "period": period, "fuel": r.fuel, "retail": r.retail_price,
                "base": r.base_price, "world": r.world_avg_price,
                "bogc": r.bog_contrib, "bogu": r.bog_use, "ct": now, "src": source_url,
            })
        conn.commit()


def crawl_one(url: str, period: date, engine) -> int:
    html, status = fetch(url)
    raw_store.land_raw(html.encode("utf-8"), "moit_fuel", url, "html", "text/html", status)
    rows = parse_moit(html, period)
    if not validate(rows):
        sys.exit(f"validation failed for {url}: {[(r.fuel, r.world_avg_price, r.retail_price) for r in rows]}")
    store(engine, period, rows, url)
    print(f"stored {len(rows)} rows for cycle {period} from {url}")
    return len(rows)


def _period_from_url(url: str) -> date:
    m = re.search(r"ngay-(\d{1,2})-(\d{1,2})-(\d{4})", url)
    if not m:
        sys.exit(f"cannot derive cycle date from url: {url}")
    d, mo, y = (int(x) for x in m.groups())
    return date(y, mo, d)


def discover_latest() -> str:
    html, _ = fetch(MOIT_NEWS_INDEX)
    m = re.search(r'href="([^"]*dieu-hanh-gia-xang-dau-ngay[^"]+\.html)"', html)
    if not m:
        sys.exit("could not find a latest fuel announcement link on the MOIT index")
    href = m.group(1)
    return href if href.startswith("http") else "https://moit.gov.vn" + href


def main() -> None:
    engine = _engine()
    if len(sys.argv) >= 3:
        crawl_one(sys.argv[1], date.fromisoformat(sys.argv[2]), engine)
    else:
        url = discover_latest()
        crawl_one(url, _period_from_url(url), engine)


if __name__ == "__main__":
    main()
