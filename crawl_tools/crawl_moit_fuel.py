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

# Primary discovery: MOIT's own site search. Category listings drop bulletins and
# slug templates keep changing (2026-07 moved category, 2026-09 dropped the year),
# so anything that depends on knowing the URL in advance breaks silently. Search
# is server-rendered, needs no API key, and returns the bulletins whatever they
# are named or filed under.
MOIT_SEARCH_URL = (
    "https://moit.gov.vn/?page=search&keyword="
    "%C4%91i%E1%BB%81u%20h%C3%A0nh%20gi%C3%A1%20x%C4%83ng%20d%E1%BA%A7u"  # "điều hành giá xăng dầu"
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
                    (period, fuel, retail_price, world_avg_price,
                     crawl_time, source, group_name)
                VALUES
                    (:period, :fuel, :retail, :world, :ct, :src, 'commodity')
                ON CONFLICT (fuel, period) DO UPDATE SET
                    retail_price = EXCLUDED.retail_price,
                    world_avg_price = EXCLUDED.world_avg_price,
                    crawl_time = EXCLUDED.crawl_time
            """), {
                "period": period, "fuel": r.fuel, "retail": r.retail_price,
                "world": r.world_avg_price, "ct": now, "src": source_url,
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
    """Year-bearing slugs only; kept for crawl_tools/backfill_moit_archive.py."""
    m = re.search(r"ngay-(\d{1,2})-(\d{1,2})-(\d{4})", url)
    if not m:
        sys.exit(f"cannot derive cycle date from url: {url}")
    d, mo, y = (int(x) for x in m.groups())
    return date(y, mo, d)


def _published_date(html: str) -> date | None:
    m = re.search(r'article:published_time"[^>]*?content="(\d{4})-(\d{2})-(\d{2})', html)
    return date(*(int(x) for x in m.groups())) if m else None


# MOIT has used several slug templates and categories for the same bulletin;
# 2026-09 dropped the year altogether ("...-ngay-10-9.html" under /thong-bao/),
# which the crawler could not see while CI stayed green.
_BULLETIN_PREFIXES = ("tin-tuc", "tin-tuc/thong-bao", "tin-tuc/thi-truong-trong-nuoc")
_BULLETIN_SLUGS = (
    "mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{d}-{m}-{y}.html",
    "mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{d}-{m}.html",
    "thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{d}-{m}-{y}.html",
)


def _bulletin_urls(d: date) -> list[str]:
    return [f"https://moit.gov.vn/{prefix}/{slug.format(d=d.day, m=d.month, y=d.year)}"
            for prefix in _BULLETIN_PREFIXES for slug in _BULLETIN_SLUGS]


def _published_on(html: str, d: date) -> bool:
    """A bulletin goes up on its cycle day (occasionally the next). A year-less
    slug keeps resolving to last year's article, so the page itself must agree."""
    published = _published_date(html)
    return published is not None and 0 <= (published - d).days <= 1


def _slug_day_month(url: str) -> tuple[int, int] | None:
    m = re.search(r"ngay-(\d{1,2})-(\d{1,2})(?:-\d{4})?(?:-[^/]*)?\.html$", url)
    return (int(m.group(1)), int(m.group(2))) if m else None


# How many days ahead of the last known cycle to direct-probe. Cadence has moved
# between ~7 and ~14 days in 2026 (see PROBE_WINDOW_DAYS note below); this window
# covers a return to weekly all the way through a slip to 3 weeks.
PROBE_WINDOW_DAYS = 21

# Hard alert threshold, independent of whether a new cycle was found this run.
# Cadence went back to weekly on 2026-09-03, so 25 days was far too slack: the
# 2026-09-03 -> 09-17 miss sat at 21 days of silence and would never have paged.
# 17 days = two missed weekly cycles plus slack, still above the ~14-day cadence
# of Aug 2026 in case it returns.
STALE_AFTER_DAYS = 17


def discover_new(latest_known: date | None, today: date | None = None,
                 fetch=fetch, indexes=MOIT_NEWS_INDEXES) -> list[tuple[date, str]]:
    """Every MOIT fuel-price-cycle bulletin newer than `latest_known`, oldest first.

    Two independent strategies, because category listings have proven unreliable —
    confirmed 2026-09-08: the 2026-08-27 cycle exists at its predictable URL but is
    not linked from EITHER known category page.

    1. Category scan (cheap, catches a same-page re-listing).
    2. Direct date probe (robust, catches unlisted pages): try every known slug
       template for every calendar day in the window after `latest_known`.

    A page only counts if its own publish date matches the cycle day, which is
    also where a year-less slug gets its year. Returns [] if nothing newer was
    found — NOT necessarily an error; see STALE_AFTER_DAYS in main().
    """
    today = today or date.today()
    found: dict[date, str] = {}

    for index_url in (MOIT_SEARCH_URL,) + tuple(indexes):
        # moit.gov.vn drops connections from foreign datacenter IPs (the same
        # reason prod moved to a VN box). One unreachable source must fall
        # through to the next, not kill discovery — staleness is what pages.
        try:
            html, _ = fetch(index_url)
        except Exception as exc:
            print(f"discovery source unreachable ({index_url}): {exc}")
            continue
        for m in re.finditer(r'href="([^"]*dieu-hanh-(?:gia-)?xang-dau-ngay[^"]+\.html)"', html):
            href = m.group(1)
            url = href if href.startswith("http") else "https://moit.gov.vn" + href
            # Search also returns the /van-ban-phap-luat/ mirror of each cycle —
            # a different document type that moit_parser.py is not written for.
            if "/tin-tuc/" not in url:
                continue
            day_month, published = _slug_day_month(url), None
            page, status = fetch(url)
            if status == 200:
                published = _published_date(page)
            if not day_month or not published:
                continue
            for year in (published.year, published.year - 1):
                try:
                    d = date(year, day_month[1], day_month[0])
                except ValueError:
                    continue
                if _published_on(page, d):
                    found.setdefault(d, url)
                    break

    if latest_known is not None:
        for offset in range(1, PROBE_WINDOW_DAYS + 1):
            d = latest_known + timedelta(days=offset)
            if d > today:
                break
            if d in found:
                continue
            for url in _bulletin_urls(d):
                try:
                    page, status = fetch(url)
                except Exception:
                    continue  # same reason as the discovery sources above
                if status == 200 and _published_on(page, d):
                    found[d] = url
                    break

    return sorted((d, u) for d, u in found.items() if latest_known is None or d > latest_known)


def _latest_known_period(engine) -> date | None:
    with engine.connect() as conn:
        return conn.execute(text("SELECT max(period) FROM fuel_price_cycle")).scalar()


def main() -> None:
    engine = _engine()
    if len(sys.argv) >= 3:
        crawl_one(sys.argv[1], date.fromisoformat(sys.argv[2]), engine)
        return

    latest_known = _latest_known_period(engine)
    new_cycles = discover_new(latest_known)

    if not new_cycles:
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
                "in MOIT_NEWS_INDEXES, or changed the slug again (_BULLETIN_SLUGS) — "
                "check https://moit.gov.vn manually."
            )
        print(
            f"no newer fuel price cycle found yet (latest known: {latest_known}, "
            f"gap {gap_days}d, checked categories + date-probe up to "
            f"+{PROBE_WINDOW_DAYS}d) — within the normal cadence, nothing to do"
        )
        return

    # All of them, oldest first: taking only the newest used to drop any
    # cycle missed in between.
    for period, url in new_cycles:
        crawl_one(url, period, engine)


if __name__ == "__main__":
    main()
