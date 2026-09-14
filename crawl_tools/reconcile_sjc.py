"""Retrospective reconciliation of stored SJC prices against an independent archive.

WHY THIS EXISTS
    Every other check in this project runs *before* a write, on freshly parsed
    values. That cannot see two whole classes of failure, and both have already
    happened here:

      - A write that never happens. The 75-day freeze bug discarded correct
        values at the persistence step; validation passed on data that was then
        thrown away.
      - A write that bypasses the crawler. 196 placeholder rows were backfilled
        through 24h.com.vn's `?ngaythang=` lookup, which returns fixed junk for
        past dates. gold_validation.py never saw them because they never went
        through it.

    Nothing reconciled a *stored* value against reality afterwards, so both sat
    undetected — the freeze for 75 days, the fake rows for years.

THE SOURCE
    webgia.com/gia-vang/sjc/DD-MM-YYYY.html archives SJC's own published
    adjustments per day, with the time of each one. It is a genuine third source:
    unrelated to 24h.com.vn and giavang.org, and unlike either of them it serves
    *historical* dates. That is the whole point — you cannot reconcile the past
    against a source that only knows today.

    It is NOT promoted to a crawl source. It is the auditor, and an auditor that
    also writes the books is not an auditor.

TWO DIFFERENT QUESTIONS, TWO DIFFERENT SEVERITIES
    fabricated  Was the stored price *ever* a real SJC quote that day? If it
                matches none of the day's adjustments, the number is not a price
                — this is the 196-fake-rows shape. ERROR.
    stale       Is it the day's *last* quote? If it matches an earlier
                adjustment but not the closing one, the number is real but the
                row froze mid-day — this is the 75-day-freeze shape. WARNING.

NEVER AUTO-CORRECTS
    A third source disagreeing is evidence to look at, not truth to overwrite
    with. Silently rewriting stored history from whichever source spoke last is
    how the table got into this state to begin with.
"""
import os
import re
import statistics
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text

ARCHIVE_URL = "https://webgia.com/gia-vang/sjc/{d:%d-%m-%Y}.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}

# Prices are quoted in thousands on the archive page, to the nearest 100k VND.
# 0.2% of ~143M is ~286k, comfortably above rounding and far below any real
# disagreement, which would be in the millions.
TOLERANCE = 0.002

DEFAULT_DAYS = 30
REQUEST_DELAY = 1.0  # be a polite guest on someone else's archive


class ArchiveUnavailable(Exception):
    """The archive could not be read for this date — not a data finding."""


def _to_vnd(txt: str) -> float:
    """'141.400 (-600)' -> 141400000.0. Strips the change-since-last annotation."""
    head = txt.split("(")[0]
    digits = re.sub(r"[^\d]", "", head)
    if not digits:
        raise ArchiveUnavailable(f"no number in {txt!r}")
    return float(digits) * 1000


def fetch_archive_day(d: date, session=None) -> list:
    """Every SJC adjustment published on `d`, as [(time, buy, sell), ...].

    An empty list is a real answer, not a failure: on a day SJC published no
    change the page renders normally and simply omits the adjustments table.

    The page is required to state, in its own <h1>, the date it is describing,
    and that date must be the one asked for. This guard is the entire lesson of
    the 196 fake rows: 24h.com.vn's historical lookup happily served placeholder
    numbers under a URL that named a past date, and nothing checked that the
    page agreed. A page that does not say which day it shows is not usable as an
    audit source, and an audit source that can be silently wrong is worse than
    none.
    """
    get = (session or requests).get
    try:
        resp = get(ARCHIVE_URL.format(d=d), headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise ArchiveUnavailable(f"{type(e).__name__}: {e}") from e

    soup = BeautifulSoup(resp.content, "html.parser")

    heading = soup.find("h1")
    stamp = re.search(r"(\d{2})/(\d{2})/(\d{4})", heading.get_text(" ", strip=True)) if heading else None
    if not stamp:
        raise ArchiveUnavailable("page heading does not state a date")
    shown = date(int(stamp.group(3)), int(stamp.group(2)), int(stamp.group(1)))
    if shown != d:
        raise ArchiveUnavailable(f"asked for {d}, page shows {shown}")

    # The adjustments table is identified by its own header, not by position:
    # it is absent entirely on a no-change day, and when absent the first table
    # on the page is the unrelated world-gold one.
    table = None
    for candidate in soup.find_all("table"):
        header = candidate.find("tr")
        if header and "Thời gian" in header.get_text(" ", strip=True):
            table = candidate
            break
    if table is None:
        return []

    adjustments = []
    for row in table.find_all("tr"):
        cells = [c.get_text(strip=True) for c in row.find_all("td")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        try:
            adjustments.append((cells[1], _to_vnd(cells[2]), _to_vnd(cells[3])))
        except ArchiveUnavailable:
            continue
    return adjustments


def _matches(stored_buy, stored_sell, buy, sell) -> bool:
    return (abs(stored_buy - buy) / buy <= TOLERANCE
            and abs(stored_sell - sell) / sell <= TOLERANCE)


def classify(stored_buy, stored_sell, adjustments, prev_close=None):
    """-> (verdict, detail). verdict in {'ok', 'stale', 'carry_forward',
    'unconfirmed', 'fabricated', 'no_data'}.

    Only 'fabricated' is an ERROR, and only when the archive positively lists
    what SJC published that day and our value is none of them. Everything softer
    is a WARNING on purpose — a tool that overstates its confidence gets ignored,
    which is precisely how the last DQ agent ended up unread.

    `prev_close` is the previous trading day's final quote, and it is what keeps
    this from crying wolf. SJC sometimes publishes its first change of the day
    after our last crawl (18:35 happens), and on those days the price actually
    in effect for nearly the whole day IS the previous close. Storing it is
    correct behaviour, not a fabricated number — but it matches nothing in that
    day's own list, so without this check it would be reported as the worst
    finding the tool has. Real data showed exactly that on 2026-07-14 and
    2026-08-07.
    """
    if not adjustments:
        # SJC published nothing that day, so the price in effect is the previous
        # close and that is what we should be storing. Skipping these days was a
        # real blind spot: 2026-07-15 stored a figure SJC never quoted and went
        # unreported purely because the day itself had no adjustment to compare
        # against.
        if prev_close is None:
            return "no_data", "archive lists no adjustment, and no previous close to compare"
        if _matches(stored_buy, stored_sell, *prev_close):
            return "ok", ""
        # Deliberately weaker than "fabricated". An empty day is the absence of
        # evidence, not evidence of absence: it is consistent with SJC holding
        # its price AND with the archive simply missing an entry. When our own
        # value moves plausibly day to day, the archive is as likely to be the
        # incomplete one. Worth a human look, not an accusation.
        return "unconfirmed", (
            f"stored {stored_buy/1e6:.1f}/{stored_sell/1e6:.1f}, but the archive lists no "
            f"change that day and the previous close was "
            f"{prev_close[0]/1e6:.1f}/{prev_close[1]/1e6:.1f} — either our row is wrong or "
            f"the archive is missing an entry; check by hand before acting"
        )

    _, close_buy, close_sell = adjustments[-1]
    if _matches(stored_buy, stored_sell, close_buy, close_sell):
        return "ok", ""

    for when, buy, sell in adjustments:
        if _matches(stored_buy, stored_sell, buy, sell):
            return "stale", (
                f"stored {stored_buy/1e6:.1f}/{stored_sell/1e6:.1f} is the {when} quote; "
                f"the day closed at {close_buy/1e6:.1f}/{close_sell/1e6:.1f} "
                f"({len(adjustments)} adjustments that day)"
            )

    if prev_close and _matches(stored_buy, stored_sell, *prev_close):
        first_time = adjustments[0][0]
        return "carry_forward", (
            f"stored {stored_buy/1e6:.1f}/{stored_sell/1e6:.1f} is the previous day's close; "
            f"SJC's first change that day was at {first_time}, and the day closed at "
            f"{close_buy/1e6:.1f}/{close_sell/1e6:.1f}"
        )

    quotes = ", ".join(f"{t} {b/1e6:.1f}/{s/1e6:.1f}" for t, b, s in adjustments)
    return "fabricated", (
        f"stored {stored_buy/1e6:.1f}/{stored_sell/1e6:.1f} matches no quote "
        f"published that day, nor the previous close — SJC published: {quotes}"
    )


def published_rows(engine, days: int) -> list:
    """The rows the site actually serves, newest first.

    DISTINCT ON + the same CASE ordering as be/generate_static_data.py and
    be/routers/market_data.py: auditing a row nobody publishes would miss the
    point. Change those two and this together.
    """
    sql = text("""
        SELECT DISTINCT ON (date) date, buy_price, sell_price, source, crawl_time
        FROM vn_macro_gold_daily
        WHERE type = 'SJC' AND date >= :since AND date < CURRENT_DATE
        ORDER BY date,
                 CASE source WHEN '24h.com.vn' THEN 1 WHEN 'giavang.org' THEN 2 ELSE 3 END,
                 crawl_time DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"since": date.today() - timedelta(days=days)}).fetchall()
    return sorted(rows, key=lambda r: r[0], reverse=True)


def reconcile(engine, days: int = DEFAULT_DAYS, log=print) -> list:
    """Compare each published day against the archive. Returns findings."""
    findings = []
    session = requests.Session()
    cache: dict = {}

    def archive(d):
        """Memoised: consecutive days share lookups, and prev-close resolution
        would otherwise double the request count against someone else's site."""
        if d not in cache:
            cache[d] = fetch_archive_day(d, session=session)
            time.sleep(REQUEST_DELAY)
        return cache[d]

    def previous_close(d):
        """Last quote before `d`, walking back over no-change days and weekends."""
        for back in range(1, 6):
            try:
                adjustments = archive(d - timedelta(days=back))
            except ArchiveUnavailable:
                return None
            if adjustments:
                return adjustments[-1][1], adjustments[-1][2]
        return None

    rows = published_rows(engine, days)
    log(f"  reconciling {len(rows)} published days against webgia.com")

    unavailable = 0
    severity = {"fabricated": "ERROR", "stale": "WARNING",
                "carry_forward": "WARNING", "unconfirmed": "WARNING"}
    for d, buy, sell, source, _ct in rows:
        try:
            adjustments = archive(d)
        except ArchiveUnavailable as e:
            unavailable += 1
            log(f"    {d}  archive unavailable ({e})")
            continue

        verdict, detail = classify(float(buy), float(sell), adjustments,
                                   prev_close=previous_close(d))
        if verdict in severity:
            findings.append({"date": str(d), "source": source, "verdict": verdict,
                             "detail": detail, "severity": severity[verdict]})
            log(f"    {d}  {verdict.upper()}: {detail}")

    # A source that cannot be read cannot audit anything. Say so loudly rather
    # than letting "0 findings" be read as "0 problems".
    if unavailable:
        log(f"  NOTE: {unavailable}/{len(rows)} days could not be checked")
        if unavailable == len(rows) and rows:
            findings.append({
                "date": "—", "source": "webgia.com", "verdict": "auditor_down",
                "severity": "ERROR",
                "detail": "archive unreachable for every day — reconciliation did not run",
            })
    return findings


def structural_audit(engine, log=print) -> list:
    """Whole-history checks that need no network.

    These are the year-aware checks the pre-insert rules cannot express. The
    fixed 20M-500M range has no notion of time: 81M is unremarkable in general
    and impossible in 2015, and that is exactly how the fake rows passed.
    """
    findings = []
    with engine.connect() as conn:
        # 1. Rows that never went through a crawler. Every one of the 196 fake
        #    rows carried crawl_time 00:00:00 — a synthesised timestamp is the
        #    fingerprint of a backfill, and a backfill skips every guard.
        n, lo, hi = conn.execute(text("""
            SELECT COUNT(*), MIN(date), MAX(date) FROM vn_macro_gold_daily
            WHERE type = 'SJC' AND crawl_time::time = '00:00:00'
        """)).fetchone()
        if n:
            log(f"  {n} rows with a synthesised crawl_time ({lo} -> {hi})")

        # 2. Year-aware outliers: each row against the median of its own
        #    +/-45-day neighbourhood, so the threshold moves with the era
        #    instead of being a fixed band across 11 years of price history.
        #
        #    The median is computed here rather than in SQL: Postgres does not
        #    allow PERCENTILE_CONT as a window function (it is an ordered-set
        #    aggregate), and the series is under a thousand rows.
        series = conn.execute(text("""
            SELECT DISTINCT ON (date) date, buy_price
            FROM vn_macro_gold_daily WHERE type = 'SJC'
            ORDER BY date, crawl_time DESC
        """)).fetchall()
        dated = [(d, float(b)) for d, b in series]
        for d, buy in dated:
            window = [b for dd, b in dated if abs((dd - d).days) <= 45]
            # A lone row in its own 90-day window has nothing to be an outlier
            # against — the 2015/2016 rows are 5 and 11 points in empty years.
            if len(window) < 5:
                continue
            med = statistics.median(window)
            if med and abs(buy - med) / med > 0.35:
                findings.append({
                    "date": str(d), "source": "—", "verdict": "outlier", "severity": "ERROR",
                    "detail": f"{buy/1e6:.1f}M is {abs(buy-med)/med*100:.0f}% off the "
                              f"{med/1e6:.1f}M median of its own 90-day window "
                              f"({len(window)} rows)",
                })

        # 3. A price frozen for weeks. SJC was administratively pinned for long
        #    stretches of 2024, so this is a WARNING to eyeball, not an error.
        runs = conn.execute(text("""
            WITH s AS (SELECT DISTINCT ON (date) date, buy_price
                       FROM vn_macro_gold_daily WHERE type = 'SJC'
                       ORDER BY date, crawl_time DESC),
            g AS (SELECT date, buy_price,
                         ROW_NUMBER() OVER (ORDER BY date)
                       - ROW_NUMBER() OVER (PARTITION BY buy_price ORDER BY date) AS grp
                  FROM s)
            SELECT buy_price, COUNT(*) n, MIN(date), MAX(date)
            FROM g GROUP BY buy_price, grp HAVING COUNT(*) >= 20 ORDER BY n DESC
        """)).fetchall()
        for buy, n, lo2, hi2 in runs:
            findings.append({
                "date": f"{lo2} -> {hi2}", "source": "—", "verdict": "frozen",
                "severity": "WARNING",
                "detail": f"{float(buy)/1e6:.1f}M unchanged for {n} consecutive days",
            })

    for f in findings:
        log(f"    {f['date']}  {f['verdict'].upper()}: {f['detail']}")
    return findings


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")
    url = os.getenv("CRAWLING_BOT_DB")
    if not url:
        sys.exit("CRAWLING_BOT_DB not set")
    engine = create_engine(url)

    days = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DAYS
    print(f"SJC reconciliation — {datetime.now():%Y-%m-%d %H:%M}, last {days} published days\n")

    print("Structural audit (no network):")
    findings = structural_audit(engine)
    print("\nArchive reconciliation:")
    findings += reconcile(engine, days=days)

    errors = [f for f in findings if f["severity"] == "ERROR"]
    warns = [f for f in findings if f["severity"] == "WARNING"]
    print(f"\nResult: {len(errors)} ERROR / {len(warns)} WARNING")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
