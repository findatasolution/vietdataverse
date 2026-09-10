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
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fuel_raw_store as raw_store
from be.fuel.moit_parser import parse_moit, CycleRow

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# MOIT re-files these bulletins under different news categories without notice —
# confirmed 2026-09-08: every "điều hành giá xăng dầu" post since 2026-07-09 stopped
# appearing under thi-truong-trong-nuoc and started appearing under
# phat-trien-nang-luong instead (the article URL itself is unchanged; only which
# category page links it changed). Scan every known category and take the newest
# match across all of them so a future re-filing doesn't silently freeze the crawl.
MOIT_NEWS_INDEXES = (
    "https://moit.gov.vn/tin-tuc/thi-truong-trong-nuoc",
    "https://moit.gov.vn/tin-tuc/phat-trien-nang-luong",
)
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


def _bulletin_url(d: date) -> str:
    return (
        "https://moit.gov.vn/tin-tuc/"
        f"mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{d.day}-{d.month}-{d.year}.html"
    )


def _page_exists(url: str) -> bool:
    html, status = fetch(url)
    return status == 200 and "Xin lỗi! Liên kết không tồn tại" not in html


# How many days ahead of the last known cycle to direct-probe. Cadence has moved
# between ~7 and ~14 days in 2026 (see PROBE_WINDOW_DAYS note below); this window
# covers a return to weekly all the way through a slip to 3 weeks.
PROBE_WINDOW_DAYS = 21

# Hard alert threshold, independent of whether a new cycle was found this run.
# Confirmed real-world gaps: weekly (~7d) pre-2026-07, ~14d from 2026-08-13 onward.
# 25 days gives headroom over both without masking a genuine multi-week freeze —
# this exact bug (2026-07-09 -> 2026-08-27, a 49-day freeze) is what this threshold
# exists to catch, since discover_latest() alone can silently find nothing new
# under a legitimate biweekly cadence and that must NOT be treated as failure.
STALE_AFTER_DAYS = 25


def discover_latest(latest_known: date | None) -> str | None:
    """Find the newest MOIT fuel-price-cycle bulletin newer than `latest_known`.

    Two independent strategies, because category listings have proven unreliable —
    confirmed 2026-09-08: the 2026-08-27 cycle exists at its predictable URL but is
    not linked from EITHER known category page (thi-truong-trong-nuoc, where the
    bulletins used to be listed until 2026-07-09, nor phat-trien-nang-luong, where
    they moved to afterwards — that page links 2026-08-13 but not 2026-08-27).

    1. Category scan (cheap, catches a same-page re-listing).
    2. Direct date probe (robust, catches unlisted pages): the article URL itself
       follows a fixed, predictable pattern regardless of which category links it,
       so probe every calendar day in the window after `latest_known` directly.

    Returns None if nothing newer than `latest_known` was found by either strategy —
    NOT necessarily an error; see STALE_AFTER_DAYS in main() for the actual alert.
    """
    candidates: list[str] = []

    for index_url in MOIT_NEWS_INDEXES:
        html, _ = fetch(index_url)
        for m in re.finditer(r'href="([^"]*dieu-hanh-gia-xang-dau-ngay[^"]+\.html)"', html):
            href = m.group(1)
            candidates.append(href if href.startswith("http") else "https://moit.gov.vn" + href)

    if latest_known is not None:
        for offset in range(1, PROBE_WINDOW_DAYS + 1):
            d = latest_known + timedelta(days=offset)
            if d > date.today():
                break
            url = _bulletin_url(d)
            if _page_exists(url):
                candidates.append(url)

    newer = [u for u in candidates if latest_known is None or _period_from_url(u) > latest_known]
    if not newer:
        return None
    return max(newer, key=_period_from_url)


def _latest_known_period(engine) -> date | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT max(period) FROM fuel_price_cycle")).scalar()


def main() -> None:
    engine = _engine()
    if len(sys.argv) >= 3:
        crawl_one(sys.argv[1], date.fromisoformat(sys.argv[2]), engine)
        return

    latest_known = _latest_known_period(engine)
    url = discover_latest(latest_known)

    if url is None:
        gap_days = (date.today() - latest_known).days if latest_known else None
        if gap_days is not None and gap_days > STALE_AFTER_DAYS:
            # This is the failure mode that let the crawl freeze silently for 2
            # months (2026-07-09 -> 2026-08-27) while CI stayed green: a no-op
            # exiting 0 every week. Past STALE_AFTER_DAYS, no-op is no longer a
            # plausible normal gap — fail loud so the workflow goes red.
            sys.exit(
                f"fuel_price_cycle hasn't advanced in {gap_days} days (latest: "
                f"{latest_known}), past the {STALE_AFTER_DAYS}-day staleness "
                "threshold. MOIT likely re-filed the bulletin under a category not "
                "in MOIT_NEWS_INDEXES, or changed the URL pattern in _bulletin_url — "
                "check https://moit.gov.vn manually."
            )
        print(
            f"no newer fuel price cycle found yet (latest known: {latest_known}, "
            f"gap {gap_days}d, checked categories + date-probe up to "
            f"+{PROBE_WINDOW_DAYS}d) — within the normal cadence, nothing to do"
        )
        return

    crawl_one(url, _period_from_url(url), engine)


if __name__ == "__main__":
    main()
