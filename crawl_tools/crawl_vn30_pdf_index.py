"""
VN30 Financial PDF Index Crawler
Source: static2.vietstock.vn (annual + quarterly BCTC PDFs)
DB: CRAWLING_CORP_PDF_DB (separate from financial data DB)

Table: vn30_pdf_index
  ticker, year, quarter (NULL=annual), report_type, pdf_url, exchange, source, status, ...

Usage:
  python crawl_vn30_pdf_index.py            # discover new URLs (default)
  python crawl_vn30_pdf_index.py --recheck  # re-probe known-missing years
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

current_date = datetime.now()
print(f"\n{'='*60}")
print(f"VN30 PDF Index Crawler — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_CORP_PDF_DB = os.getenv('CRAWLING_CORP_PDF_DB')
if not CRAWLING_CORP_PDF_DB:
    raise ValueError("CRAWLING_CORP_PDF_DB environment variable not set")
engine = create_engine(CRAWLING_CORP_PDF_DB)

VN30_TICKERS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR',
    'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'NVL', 'PDR', 'PLX',
    'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VPB'
]

# vietstock stores all VN30 reports under HOSE path regardless of actual exchange listing
VIETSTOCK_BASE = 'https://static2.vietstock.vn/data/HOSE'
VIETSTOCK_SOURCE = 'vietstock'

# Annual filename patterns to try (consolidated audited annual report)
ANNUAL_FILENAME_PATTERNS = [
    '{ticker}_Baocaotaichinh_{year}_Kiemtoan_Hopnhat.pdf',
    '{ticker}_BCTC_{year}_Kiemtoan_Hopnhat.pdf',
    '{ticker}_BaocaotaichinhHopnhat_{year}_Kiemtoan.pdf',
    '{ticker}_Baocaotaichinh_{year}_KiemToan_HopNhat.pdf',
]

# Quarterly filename patterns to try
QUARTERLY_FILENAME_PATTERNS = [
    '{ticker}_Baocaotaichinh_{year}_Q{q}_Hopnhat.pdf',
    '{ticker}_BCTC_Q{q}_{year}_Hopnhat.pdf',
    '{ticker}_Baocaotaichinh_Q{q}_{year}_Hopnhat.pdf',
    '{ticker}_BCTC_{year}_Q{q}_Hopnhat.pdf',
    '{ticker}_BaocaotaichinhQ{q}_{year}_Hopnhat.pdf',
]

QUARTERLY_PATH_VARIANTS = [
    'BCTC/VN/QUY{q}',
    'BCTC/VN/QUYQ{q}',
    'BCTC/VN/QUY {q}',
]

SCAN_YEARS = list(range(2010, current_date.year + 1))
SCAN_QUARTERS = [1, 2, 3, 4]


# ── DB setup ──────────────────────────────────────────────────────────────────

def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_pdf_index (
                id           SERIAL PRIMARY KEY,
                ticker       VARCHAR(10)  NOT NULL,
                year         INTEGER      NOT NULL,
                quarter      INTEGER,                  -- NULL = annual report
                report_type  VARCHAR(20)  NOT NULL DEFAULT 'ALL',
                              -- 'ALL' = full annual/quarterly BCTC
                              -- 'IS' = income statement only
                              -- 'BS' = balance sheet only
                              -- 'CF' = cash flow only
                pdf_url      TEXT         NOT NULL,
                exchange     VARCHAR(10),              -- 'HOSE', 'HNX', etc.
                source       VARCHAR(50)  DEFAULT 'vietstock',
                status       VARCHAR(20)  DEFAULT 'indexed',
                              -- 'indexed'  = URL confirmed, not yet parsed
                              -- 'parsed'   = financial data extracted
                              -- 'error'    = parse failed
                              -- 'manual'   = manually added
                parse_error  TEXT,
                added_time   TIMESTAMP    NOT NULL DEFAULT NOW(),
                parsed_time  TIMESTAMP,
                UNIQUE (ticker, year, quarter, report_type, source)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vn30_pdf_ticker_year
            ON vn30_pdf_index (ticker, year, quarter)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vn30_pdf_status
            ON vn30_pdf_index (status)
        """))
        conn.commit()
    print("Table vn30_pdf_index ready.")


def upsert_pdf(conn, ticker, year, quarter, report_type, pdf_url, exchange, source):
    conn.execute(text("""
        INSERT INTO vn30_pdf_index
            (ticker, year, quarter, report_type, pdf_url, exchange, source, status, added_time)
        VALUES
            (:ticker, :year, :quarter, :report_type, :pdf_url, :exchange, :source, 'indexed', NOW())
        ON CONFLICT (ticker, year, quarter, report_type, source) DO UPDATE SET
            pdf_url    = EXCLUDED.pdf_url,
            exchange   = EXCLUDED.exchange,
            status     = CASE WHEN vn30_pdf_index.status = 'manual' THEN 'manual'
                              ELSE 'indexed' END,
            added_time = NOW()
    """), {
        'ticker': ticker, 'year': year, 'quarter': quarter,
        'report_type': report_type, 'pdf_url': pdf_url,
        'exchange': exchange, 'source': source,
    })


# ── HTTP probe ────────────────────────────────────────────────────────────────

import requests as _requests

_sess = _requests.Session()
_sess.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})


def probe_url(url: str) -> bool:
    """HEAD request — returns True if URL exists (HTTP 200)."""
    try:
        r = _sess.head(url, timeout=8, allow_redirects=True)
        return r.status_code == 200
    except Exception:
        return False


# ── Discovery logic ───────────────────────────────────────────────────────────

def discover_annual(ticker: str, years=None) -> list[dict]:
    """Try all known annual filename patterns for each year. Returns list of found records."""
    found = []
    scan_years = years or SCAN_YEARS
    for yr in scan_years:
        for pattern in ANNUAL_FILENAME_PATTERNS:
            filename = pattern.format(ticker=ticker, year=yr)
            url = f'{VIETSTOCK_BASE}/{yr}/BCTC/VN/NAM/{filename}'
            if probe_url(url):
                found.append({
                    'ticker': ticker, 'year': yr, 'quarter': None,
                    'report_type': 'ALL', 'pdf_url': url,
                    'exchange': 'HOSE', 'source': VIETSTOCK_SOURCE,
                })
                break   # first working pattern is enough
        time.sleep(0.3)
    return found


def discover_quarterly(ticker: str, years=None) -> list[dict]:
    """Try all known quarterly filename + path patterns. Returns list of found records."""
    found = []
    scan_years = years or SCAN_YEARS
    for yr in scan_years:
        for q in SCAN_QUARTERS:
            hit = False
            for path_tmpl in QUARTERLY_PATH_VARIANTS:
                if hit:
                    break
                path = path_tmpl.format(q=q)
                for fn_tmpl in QUARTERLY_FILENAME_PATTERNS:
                    filename = fn_tmpl.format(ticker=ticker, year=yr, q=q)
                    url = f'{VIETSTOCK_BASE}/{yr}/{path}/{filename}'
                    if probe_url(url):
                        found.append({
                            'ticker': ticker, 'year': yr, 'quarter': q,
                            'report_type': 'ALL', 'pdf_url': url,
                            'exchange': 'HOSE', 'source': VIETSTOCK_SOURCE,
                        })
                        hit = True
                        break
            time.sleep(0.3)
    return found


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--recheck', action='store_true', help='Re-probe all years (not just gaps)')
    parser.add_argument('--quarterly', action='store_true', help='Also probe quarterly reports')
    parser.add_argument('--ticker', help='Run for single ticker only')
    args = parser.parse_args()

    ensure_table()

    # Load already-indexed (ticker, year, quarter) to skip
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT ticker, year, quarter FROM vn30_pdf_index WHERE source = 'vietstock'"
        )).fetchall()
    already_indexed = set((r[0], r[1], r[2]) for r in rows)
    print(f"Already indexed: {len(already_indexed)} entries")

    tickers = [args.ticker] if args.ticker else VN30_TICKERS
    total_new = 0
    crawl_time = datetime.now()

    for ticker in tickers:
        print(f"\n  [{ticker}] Scanning annual reports...")
        ticker_new = 0

        # Determine which years to scan
        if args.recheck:
            scan_years = SCAN_YEARS
        else:
            indexed_years = {yr for (t, yr, q) in already_indexed if t == ticker and q is None}
            scan_years = [yr for yr in SCAN_YEARS if yr not in indexed_years]

        if not scan_years:
            print(f"  [{ticker}] All years already indexed — skipping")
        else:
            records = discover_annual(ticker, scan_years)
            if records:
                with engine.connect() as conn:
                    for rec in records:
                        upsert_pdf(conn, **rec)
                    conn.commit()
                ticker_new += len(records)
                years_found = sorted(r['year'] for r in records)
                print(f"  [{ticker}] Annual: {len(records)} PDFs found — years {years_found}")
            else:
                print(f"  [{ticker}] Annual: no PDFs found for years {scan_years}")

        if args.quarterly:
            print(f"  [{ticker}] Scanning quarterly reports...")
            if args.recheck:
                scan_years_q = SCAN_YEARS
            else:
                indexed_quarters = {(yr, q) for (t, yr, q) in already_indexed
                                    if t == ticker and q is not None}
                scan_years_q = [yr for yr in SCAN_YEARS
                                if not all((yr, q) in indexed_quarters for q in SCAN_QUARTERS)]

            if scan_years_q:
                q_records = discover_quarterly(ticker, scan_years_q)
                if q_records:
                    with engine.connect() as conn:
                        for rec in q_records:
                            upsert_pdf(conn, **rec)
                        conn.commit()
                    ticker_new += len(q_records)
                    print(f"  [{ticker}] Quarterly: {len(q_records)} PDFs found")
                else:
                    print(f"  [{ticker}] Quarterly: none found")

        total_new += ticker_new
        time.sleep(0.5)

    # Final summary
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT COUNT(*), MIN(year), MAX(year), COUNT(DISTINCT ticker) FROM vn30_pdf_index"
        )).fetchone()
        print(f"\n{'='*60}")
        print(f"PDF Index done. New this run: {total_new}")
        print(f"Total in DB: {r[0]} PDFs, years {r[1]}-{r[2]}, {r[3]} tickers")
        print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")


if __name__ == '__main__':
    main()
