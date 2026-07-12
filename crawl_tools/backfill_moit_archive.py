"""Backfill MOIT fuel price announcements by discovering all historical URLs.

Usage:
  python crawl_tools/backfill_moit_archive.py

Discovers announcement URLs from MOIT news listing pages, derives periods,
checks DB to skip already-complete periods, then crawls new ones.
"""
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import crawl_moit_fuel as m

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

MOIT_NEWS_BASE = "https://moit.gov.vn/tin-tuc/thi-truong-trong-nuoc"
MOIT_SEARCH = "https://moit.gov.vn/tim-kiem.html?keyword=dieu%20hanh%20gia%20xang%20dau"
UA = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}

ANNOUNCE_PATTERN = re.compile(r'dieu-hanh-gia-xang-dau-ngay-[\d-]+\.html')


def fetch_with_retry(url: str, max_retries: int = 2) -> tuple[str, int]:
    """Fetch URL with simple retry logic."""
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=UA, timeout=30)
            return resp.text, resp.status_code
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
    return "", 500


def discover_urls_from_page(html: str, base_url: str) -> set[str]:
    """Extract announcement hrefs matching pattern, make absolute."""
    urls = set()
    for match in re.finditer(r'href="([^"]*dieu-hanh-gia-xang-dau-ngay-[\d-]+\.html)"', html):
        href = match.group(1)
        abs_url = urljoin(base_url, href)
        urls.add(abs_url)
    return urls


def discover_pagination_pattern(html: str) -> list[str]:
    """Infer pagination link patterns from HTML. Returns list of page URLs."""
    # Try common pagination patterns: ?page=N, ?p=N, ?trang=N, etc.
    # Look for links like "2", "3", etc. in nav/pagination elements

    pages = []

    # Try to find pagination container (usually in nav or div with class *page* or *paginat*)
    # Pattern 1: href="...?page=2"
    for match in re.finditer(r'href="([^"]*\?[^"]*(?:page|p|trang)=(\d+)[^"]*)"', html):
        page_url = match.group(1)
        page_num = int(match.group(2))
        if page_url.startswith("/"):
            page_url = "https://moit.gov.vn" + page_url
        if page_url not in pages:
            pages.append((page_num, page_url))

    # If found, return a reasonable range (pages sorted by number)
    if pages:
        pages.sort(key=lambda x: x[0])
        return [url for num, url in pages]

    # Fallback: return simple ?page=2..N guesses
    return []


def discover_urls_from_listing(base_url: str, max_pages: int = 40) -> set[str]:
    """Crawl MOIT listing pages, extract announcement links, handle pagination."""
    all_urls = set()
    page_num = 1
    seen_pages = set()
    no_new_count = 0

    while page_num <= max_pages and no_new_count < 2:  # Stop after 2 blank pages
        print(f"  Fetching {base_url} (page {page_num})...")

        # Build page URL
        if "?" in base_url:
            page_url = f"{base_url}&page={page_num}"
        else:
            page_url = f"{base_url}?page={page_num}"

        try:
            html, status = fetch_with_retry(page_url)
            if status != 200:
                print(f"    Status {status}, stopping pagination")
                break

            time.sleep(1.5)  # Politeness

            page_urls = discover_urls_from_page(html, base_url)
            new_count = len(page_urls - all_urls)

            if new_count == 0:
                no_new_count += 1
                print(f"    Page {page_num}: 0 new URLs, blank count = {no_new_count}")
            else:
                no_new_count = 0
                all_urls.update(page_urls)
                print(f"    Page {page_num}: +{new_count} URLs (total {len(all_urls)})")

            page_num += 1

        except Exception as e:
            print(f"    Error fetching page {page_num}: {str(e)[:60]}")
            break

    return all_urls


def is_period_complete(engine, period: date) -> bool:
    """Check if period already has 3+ fuel entries in DB."""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT count(*) FROM fuel_price_cycle WHERE period = :p"),
                {"p": period}
            ).scalar()
            return result is not None and result >= 3
    except Exception as e:
        print(f"    DB check error for {period}: {str(e)[:60]}")
        return False


def try_smart_historical_dates(engine) -> set[str]:
    """Generate URLs for likely announcement dates (mainly Thursdays) going back in time."""
    found_urls = set()
    tested = 0

    # Get the earliest known period to start searching before it
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT min(period) FROM fuel_price_cycle")
            ).scalar()
            earliest = result if result else date(2026, 1, 1)
    except:
        earliest = date(2026, 1, 1)

    print(f"\n[Stage 3] Smart historical search: testing Wed/Thu/Fri dates before {earliest}...")

    # Generate dates for Wed, Thu, Fri going back ~2.5 years
    current = earliest - timedelta(days=7)
    end = date(2023, 9, 1)  # Extend back to mid-2023
    test_dates = []

    while current > end:
        dow = current.weekday()  # 0=Mon, 3=Thu, 4=Fri, 2=Wed
        if dow in [2, 3, 4]:  # Wed, Thu, Fri
            test_dates.append(current)
        current -= timedelta(days=1)

    print(f"  Generated {len(test_dates)} candidate dates")

    # Test URLs for these dates (test all generated dates since they're pre-filtered)
    # Sort by reverse (most recent first) to test recent dates and fill gaps
    for test_date in sorted(test_dates, reverse=True)[:500]:  # Test most recent first, up to 500
        day = test_date.day
        month = test_date.month
        year = test_date.year

        # Try the most common pattern first
        url = f"https://moit.gov.vn/tin-tuc/mot-so-thong-tin-ve-viec-dieu-hanh-gia-xang-dau-ngay-{day:02d}-{month}-{year}.html"

        try:
            resp = requests.get(url, headers=UA, timeout=5)
            if resp.status_code == 200 and "Page not found" not in resp.text and ("Giá" in resp.text or "giá" in resp.text):
                found_urls.add(url)
                print(f"  ✓ Found: {test_date} - {url}")
            tested += 1

            if tested % 20 == 0:
                print(f"    Tested {tested}...")
        except:
            tested += 1
            continue

    print(f"  Tested {tested} URLs, found {len(found_urls)} new ones")
    return found_urls


def main():
    engine = m._engine()

    print("=" * 70)
    print("MOIT Fuel Price Backfill: Discovering historical announcement URLs")
    print("=" * 70)

    # Stage 1: Discover from news listing
    print(f"\n[Stage 1] Crawling news listing: {MOIT_NEWS_BASE}")
    urls = discover_urls_from_listing(MOIT_NEWS_BASE, max_pages=40)
    print(f"  Total discovered from news: {len(urls)}")

    # Stage 2: If fewer than 20, try search listing
    if len(urls) < 20:
        print(f"\n[Stage 2] Only {len(urls)} URLs found; trying search listing...")
        search_urls = discover_urls_from_listing(MOIT_SEARCH, max_pages=20)
        urls.update(search_urls)
        print(f"  Total after search: {len(urls)}")

    # Stage 2b: Try smart historical date testing (Thu/Wed/Fri backward)
    historical_urls = try_smart_historical_dates(engine)
    urls.update(historical_urls)

    if not urls:
        print("\nNo announcement URLs discovered. Exiting.")
        sys.exit(0)

    # Stage 4: Dedupe and sort by period (oldest first for better UX)
    print(f"\n[Stage 4] Deduplicating and sorting {len(urls)} URLs...")
    url_list = sorted(list(urls))

    # Try to extract periods and sort chronologically
    periods_urls = []
    for url in url_list:
        try:
            period = m._period_from_url(url)
            periods_urls.append((period, url))
        except SystemExit:
            print(f"  SKIP {url.split('/')[-1][:40]} -> cannot parse period")
            continue

    periods_urls.sort(key=lambda x: x[0])  # oldest first
    print(f"  {len(periods_urls)} URLs with valid periods (sorted)")

    # Stage 5: Crawl new periods
    print(f"\n[Stage 5] Crawling new periods (skipping if already 3+ fuels)...")
    crawled_ok = 0
    crawled_skip = 0
    crawled_fail = 0

    for i, (period, url) in enumerate(periods_urls, 1):
        if is_period_complete(engine, period):
            print(f"  [{i}/{len(periods_urls)}] SKIP {url.split('/')[-1][:50]} -> period {period} already complete")
            crawled_skip += 1
            continue

        try:
            print(f"  [{i}/{len(periods_urls)}] Crawling {url.split('/')[-1][:50]} (period {period})...")
            m.crawl_one(url, period, engine)
            crawled_ok += 1
            time.sleep(1.5)  # Politeness between crawls
        except SystemExit as e:
            print(f"    FAIL {url.split('/')[-1][:50]} -> {str(e)[:60]}")
            crawled_fail += 1
        except Exception as e:
            print(f"    FAIL {url.split('/')[-1][:50]} -> {str(e)[:60]}")
            crawled_fail += 1

    # Stage 6: Final summary
    print("\n" + "=" * 70)
    print("BACKFILL SUMMARY")
    print("=" * 70)
    print(f"URLs discovered:    {len(url_list)}")
    print(f"URLs with periods:  {len(periods_urls)}")
    print(f"Crawled OK:         {crawled_ok}")
    print(f"Skipped (complete): {crawled_skip}")
    print(f"Failed:             {crawled_fail}")

    # Final DB query
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT count(DISTINCT period), min(period), max(period)
                    FROM fuel_price_cycle
                """)
            ).fetchone()
            if row and row[0] is not None:
                distinct_periods, min_period, max_period = row
                print(f"DB stats:           {distinct_periods} distinct periods, {min_period} to {max_period}")
            else:
                print(f"DB stats:           No data in DB")
    except Exception as e:
        print(f"DB stats:           Error: {str(e)[:60]}")

    print("=" * 70)


if __name__ == "__main__":
    main()
