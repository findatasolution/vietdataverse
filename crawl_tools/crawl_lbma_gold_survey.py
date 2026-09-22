"""Crawl LBMA's gold price forecast surveys (aggregate only) → GLOBAL_INDICATOR_DB.

Usage:
  python crawl_tools/crawl_lbma_gold_survey.py               # discover + crawl both report types
  python crawl_tools/crawl_lbma_gold_survey.py annual 2026    # one specific annual survey year
  python crawl_tools/crawl_lbma_gold_survey.py midyear        # just the mid-year snapshot

AGGREGATE ONLY — average/high/low/analyst-count, never the per-analyst "cards"
LBMA also publishes on the same pages. LBMA's own material states content "may
not be altered in any way, transmitted to, copied or distributed to any other
party" without written permission; the 16-28 individually-named analyst/firm
forecasts are LBMA's proprietary compiled data, materially different from the
raw public administrative bulletins (MOIT, GSO) this project already crawls.
Citing the aggregate with attribution is the smaller, defensible reuse. See
CLAUDE.md's "LBMA gold forecast survey" section before extending this to
store per-analyst rows.

Two report types, two different discovery problems:

  annual  — https://www.lbma.org.uk/forecast-survey-{year}/at-a-glance, a
            predictable per-year URL (verified 2022-2026, though 2022 used a
            different path — /publications/annual-precious-metals-forecast-
            survey-2022 — so a slug can drift; this crawler probes the current
            pattern and fails loud rather than silently matching nothing).
            Published mid-January, forecasting THAT SAME calendar year.
  midyear — a fixed, evergreen article URL that LBMA reuses and updates in
            place each July, rather than a new URL per year. "New" is
            therefore detected by the article's own published date (parsed
            from the page, e.g. "August 11, 2026") advancing past whatever is
            already stored for survey_type='midyear' — not by a URL appearing.

Both extractions are prose-regex against whitespace-collapsed text (the
figures sit in narrative sentences, not a table — same shape as the GSO
crawlers' layer1_structured). Every match requires the page to state its own
target year/date explicitly before being trusted — the same guard
reconcile_sjc.py uses, for the same reason: a page that doesn't confirm what
it is describing is not safe to believe.
"""
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}
ANNUAL_URL = "https://www.lbma.org.uk/forecast-survey-{year}/at-a-glance"
MIDYEAR_URL = "https://www.lbma.org.uk/articles/gold-price-lbma-snapshot-survey-of-professional-analysts"

MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December")


class SourceMismatch(Exception):
    """The page did not state what this crawler expected it to state."""


def _page_text(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=25)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" "))


def _money(s: str) -> float:
    return float(s.replace("$", "").replace(",", ""))


def parse_annual(text_: str, year: int, url: str) -> dict:
    """Pure extraction — no network — so it is unit-testable against canned
    text (crawl_tools/test_crawl_lbma_gold_survey.py) without depending on
    LBMA's page staying reachable or unchanged during a CI run.

    Guard: the extracted sentence must name `year` itself ("The gold price for
    {year} is predicted...") — the exact lesson from the 196 fake gold rows:
    a URL naming a year proves nothing if the page doesn't say so too.
    """
    m = re.search(
        rf"gold price for {year} is predicted to see gains averaging at \$([\d,\.]+).*?"
        rf"from \$([\d,\.]+) to \$([\d,\.]+)\)",
        text_,
    )
    if not m:
        raise SourceMismatch(f"{url}: page did not state a {year} gold forecast in the expected form")

    avg, low, high = _money(m.group(1)), _money(m.group(2)), _money(m.group(3))

    m2 = re.search(r"[Oo]f the (\d+) analysts forecasting in the gold category", text_)
    if not m2:
        raise SourceMismatch(f"{url}: could not find the analyst count")
    n_analysts = int(m2.group(1))

    m3 = re.search(r"as at (\d{1,2}) (" + "|".join(MONTH_NAMES) + r")", text_)
    if m3:
        month = MONTH_NAMES.index(m3.group(2)) + 1
        published = date(year, month, int(m3.group(1)))
    else:
        published = date(year, 1, 20)  # LBMA's usual publish window; best-effort fallback

    return {
        "survey_type": "annual", "survey_year": year, "published_date": published,
        "n_analysts": n_analysts, "avg_price": avg, "high_price": high, "low_price": low,
        "source_url": url,
    }


def parse_midyear(text_: str, url: str) -> dict:
    """Pure extraction — no network. survey_year comes from the article's own
    publish date stamp, since the forecast sentence itself only ever says
    "year-end" without naming a year."""
    m_date = re.search(
        r"(" + "|".join(MONTH_NAMES) + r") (\d{1,2}), (\d{4})\s*Gold Price: LBMA Snapshot Survey",
        text_,
    )
    if not m_date:
        raise SourceMismatch(f"{url}: could not find the article's publish date")
    month = MONTH_NAMES.index(m_date.group(1)) + 1
    published = date(int(m_date.group(3)), month, int(m_date.group(2)))

    m = re.search(
        r"Gold is forecast to price at around \$([\d,\.]+) at year-end according to the "
        r"average of a survey of (\d+) professional analysts conducted[^.]*\. "
        r"The highest year-end number from the survey was \$([\d,\.]+), the lowest \$([\d,\.]+)",
        text_,
    )
    if not m:
        raise SourceMismatch(f"{url}: page did not state the snapshot survey in the expected form")

    return {
        "survey_type": "midyear", "survey_year": published.year, "published_date": published,
        "n_analysts": int(m.group(2)), "avg_price": _money(m.group(1)),
        "high_price": _money(m.group(3)), "low_price": _money(m.group(4)),
        "source_url": url,
    }


def fetch_annual_survey(year: int) -> Optional[dict]:
    """One row for the annual survey targeting `year`, or None if not published yet."""
    url = ANNUAL_URL.format(year=year)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException:
        return None
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    text_ = re.sub(r"\s+", " ", BeautifulSoup(resp.content, "html.parser").get_text(" "))
    return parse_annual(text_, year, url)


def fetch_midyear_snapshot() -> Optional[dict]:
    """The current mid-year snapshot, from LBMA's fixed evergreen article URL."""
    try:
        text_ = _page_text(MIDYEAR_URL)
    except requests.RequestException:
        return None
    return parse_midyear(text_, MIDYEAR_URL)


def store(row: dict) -> bool:
    """Upsert one row. Returns True if this was new or changed vs. what's stored."""
    db_url = os.getenv("GLOBAL_INDICATOR_DB")
    if not db_url:
        sys.exit("GLOBAL_INDICATOR_DB not set")
    engine = create_engine(db_url)
    with engine.begin() as conn:
        existing = conn.execute(text("""
            SELECT published_date, avg_price FROM global_lbma_gold_forecast
            WHERE survey_type = :t AND survey_year = :y
        """), {"t": row["survey_type"], "y": row["survey_year"]}).fetchone()

        is_new = existing is None or existing[0] != row["published_date"] or float(existing[1]) != row["avg_price"]

        conn.execute(text("""
            INSERT INTO global_lbma_gold_forecast
                (survey_type, survey_year, published_date, n_analysts,
                 avg_price, high_price, low_price, source_url, crawl_time, source, group_name)
            VALUES (:survey_type, :survey_year, :published_date, :n_analysts,
                    :avg_price, :high_price, :low_price, :source_url, :crawl_time, :source, 'commodity')
            ON CONFLICT (survey_type, survey_year) DO UPDATE SET
                published_date = EXCLUDED.published_date,
                n_analysts     = EXCLUDED.n_analysts,
                avg_price      = EXCLUDED.avg_price,
                high_price     = EXCLUDED.high_price,
                low_price      = EXCLUDED.low_price,
                crawl_time     = EXCLUDED.crawl_time
        """), {**row, "crawl_time": datetime.now(), "source": "lbma.org.uk"})
    return is_new


def discover_and_crawl() -> int:
    """Probe the current year's annual survey (and next year's, for the window
    right after a new one is likely published) plus the mid-year snapshot.
    Prints what it found; returns the process exit code."""
    today = date.today()
    found_any = False
    errors = []

    for year in (today.year, today.year + 1):
        try:
            row = fetch_annual_survey(year)
        except SourceMismatch as e:
            print(f"  MISMATCH: {e}")
            errors.append(str(e))
            continue
        if row is None:
            print(f"  annual {year}: not published yet")
            continue
        is_new = store(row)
        found_any = True
        print(f"  annual {year}: avg ${row['avg_price']:,.0f} "
              f"(${row['low_price']:,.0f}-${row['high_price']:,.0f}), "
              f"{row['n_analysts']} analysts, published {row['published_date']}"
              f"{' [NEW]' if is_new else ''}")

    try:
        row = fetch_midyear_snapshot()
    except SourceMismatch as e:
        print(f"  MISMATCH: {e}")
        errors.append(str(e))
        row = None
    if row is None:
        print("  midyear: could not fetch")
    else:
        is_new = store(row)
        found_any = True
        print(f"  midyear {row['survey_year']}: avg ${row['avg_price']:,.0f} "
              f"(${row['low_price']:,.0f}-${row['high_price']:,.0f}), "
              f"{row['n_analysts']} analysts, published {row['published_date']}"
              f"{' [NEW]' if is_new else ''}")

    if errors:
        return 1
    if not found_any:
        print("  nothing found at all — check the page structure by hand")
        return 1
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return discover_and_crawl()

    if args[0] == "annual":
        year = int(args[1]) if len(args) > 1 else date.today().year
        row = fetch_annual_survey(year)
        if row is None:
            print(f"annual {year}: not published yet")
            return 1
        store(row)
        print(row)
        return 0

    if args[0] == "midyear":
        row = fetch_midyear_snapshot()
        if row is None:
            print("midyear: could not fetch")
            return 1
        store(row)
        print(row)
        return 0

    sys.exit(f"usage: {sys.argv[0]} [annual YEAR | midyear]")


if __name__ == "__main__":
    sys.exit(main())
