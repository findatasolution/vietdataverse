"""
VN30 Quarterly Financial Statements Crawler (Income, Balance Sheet, Cash Flow)
Source: vnstock (KBS) — works from VN IP (Mac/local)
Schedule: Quarterly — 15th of Jan, Apr, Jul, Oct (08:00 local)

UNIT CONVENTION (stored in DB):
  - Monetary columns (revenue, assets, cfo, etc.): tỷ VND (billion VND)
  - EPS: VND per share (not converted)
  - KBS raw data is in nghìn đồng → divide by 1e6 to get tỷ VND
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import re
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

current_date = datetime.now()
print(f"\n{'='*60}")
print(f"VN30 Financials Crawler — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_CORP_DB = os.getenv('CRAWLING_CORP_DB')
if not CRAWLING_CORP_DB:
    raise ValueError("CRAWLING_CORP_DB environment variable not set")
engine = create_engine(CRAWLING_CORP_DB)

VN30_TICKERS = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR',
    'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'NVL', 'PDR', 'PLX',
    'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB',
    'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VPB'
]

# KBS returns data in nghìn đồng (thousand VND). Divide by this to get tỷ VND.
KBS_TO_TY = 1_000_000   # nghìn đồng ÷ 1e6 = tỷ VND

# Set FINANCIALS_MAX_PAGES=15 for full 15-year historical backfill (≈ 60 quarters).
# Default=1 fetches only the most recent year (4 quarters) — used for regular quarterly runs.
FINANCIALS_MAX_PAGES = int(os.getenv('FINANCIALS_MAX_PAGES', '1'))

# KBS report type → Content section key mapping
_KBS_CONTENT_KEYS = {
    'KQKD': 'Kết quả kinh doanh',
    'CDKT': 'Cân đối kế toán',
    'LCTT': None,   # varies by company (direct vs indirect method) — resolved at runtime
}


def ensure_tables():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_income_stmt_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                revenue FLOAT,        -- tỷ VND
                gross_profit FLOAT,   -- tỷ VND
                ebit FLOAT,           -- tỷ VND
                net_income FLOAT,     -- tỷ VND
                eps FLOAT,            -- VND per share
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (ticker, year, quarter)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_balance_sheet_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                total_assets FLOAT,       -- tỷ VND
                total_liabilities FLOAT,  -- tỷ VND
                equity FLOAT,             -- tỷ VND
                cash FLOAT,               -- tỷ VND
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (ticker, year, quarter)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_cashflow_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                cfo FLOAT,           -- tỷ VND (operating)
                cfi FLOAT,           -- tỷ VND (investing)
                cff FLOAT,           -- tỷ VND (financing)
                free_cashflow FLOAT, -- tỷ VND (cfo + cfi)
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (ticker, year, quarter)
            )
        """))
        # Migrate existing tables
        for tbl in ('vn30_income_stmt_quarterly', 'vn30_balance_sheet_quarterly', 'vn30_cashflow_quarterly'):
            for col, definition in [
                ('source',     "TEXT NOT NULL DEFAULT 'vnstock3'"),
                ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'stock'"),
            ]:
                try:
                    conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {definition}"))
                    conn.commit()
                except Exception:
                    conn.rollback()
        conn.commit()
    print("Tables ready (unit: tỷ VND for monetary cols, VND/share for EPS).")


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_float(val):
    try:
        if val is None:
            return None
        f = float(val)
        return None if (f != f) else f   # catch NaN
    except (ValueError, TypeError):
        return None


def _to_ty(val):
    """Convert KBS nghìn đồng → tỷ VND. Returns None if val is None/NaN."""
    f = _safe_float(val)
    return None if f is None else f / KBS_TO_TY


def _pivot_kbs_wide(df) -> list:
    """Convert KBS wide-format DataFrame (items as rows, quarters as cols)
    to list of row-dicts keyed by item_id.
    """
    quarter_cols = [c for c in df.columns if re.match(r'\d{4}-Q\d', str(c))]
    records = []
    for col in quarter_cols:
        m = re.match(r'(\d{4})-Q(\d)', col)
        if not m:
            continue
        year, qtr = int(m.group(1)), int(m.group(2))
        row_dict = {'year': year, 'quarter': qtr}
        for _, r in df.iterrows():
            row_dict[r['item_id']] = r[col]
        records.append(row_dict)
    return records


def _is_valid(v) -> bool:
    """Return True if v is a non-None, non-NaN value."""
    if v is None:
        return False
    try:
        f = float(v)
        return f == f   # NaN != NaN
    except (TypeError, ValueError):
        return False


def _kbs_find(r: dict, *suffixes):
    """Find first non-NaN value by exact key or suffix match.
    Handles prefixed item_ids like 'n_3.net_revenue' → matches 'net_revenue'.
    Skips NaN/None section-header rows so real leaf rows are found instead.
    """
    for suffix in suffixes:
        # 1. Exact key match (skip NaN)
        if suffix in r and _is_valid(r[suffix]):
            return r[suffix]
        # 2. Suffix match on dot/underscore-prefixed keys
        for k, v in r.items():
            if (k.endswith('.' + suffix) or k.endswith('_' + suffix)) and _is_valid(v):
                return v
    return None


def _kbs_income_row(r: dict) -> dict:
    """Map KBS item_ids → income stmt fields. Handles banking + industrial."""
    revenue = _kbs_find(r, 'net_revenue', 'revenue',
                        'net_interest_income', 'total_operating_income')
    gross   = _kbs_find(r, 'gross_profit', 'net_operating_income',
                        'net_fee_and_commission_income')
    ebit    = _kbs_find(r, 'operating_profit', 'ebit',
                        'operating_profit_before_provision_for_credit_losses',
                        'profit_before_provision', 'profit_before_tax')
    net_inc = _kbs_find(r, 'net_profit_after_tax', 'profit_after_tax', 'net_income',
                        'profit_after_tax_for_shareholders_of_parent_company',
                        'net_profit_atttributable_to_the_equity_holders_of_the_bank')
    eps_val = _kbs_find(r, 'earnings_per_share_vnd', 'earning_per_share_vnd', 'eps',
                        'diluted_earnings_per_share')
    return {
        'revenue':      _to_ty(revenue),
        'gross_profit': _to_ty(gross),
        'ebit':         _to_ty(ebit),
        'net_income':   _to_ty(net_inc),
        'eps':          _safe_float(eps_val),   # VND/share — no unit conversion
    }


def _kbs_bs_row(r: dict) -> dict:
    total_assets = _kbs_find(r, 'total_assets')
    total_liab   = _kbs_find(r, 'total_liabilities', 'total_debt', 'liabilities')
    equity       = _kbs_find(r,
                             'capital_and_reserves',        # banks (ACB, VCB, BID, ...)
                             'owners_equity', 'equity', 'total_equity',
                             'shareholders_equity', 'owner_equity')
    cash         = _kbs_find(r,
                             'cash_gold_and_silver_precious_stones',  # banks
                             'cash_and_cash_equivalents', 'cash_and_gold',
                             'cash', 'cash_and_short_term_investments')
    return {
        'total_assets':      _to_ty(total_assets),
        'total_liabilities': _to_ty(total_liab),
        'equity':            _to_ty(equity),
        'cash':              _to_ty(cash),
    }


def _kbs_cf_row(r: dict) -> dict:
    cfo = _kbs_find(r, 'net_cash_flows_from_operating_activities',
                    'cash_flows_from_operating_activities', 'cfo')
    cfi = _kbs_find(r, 'net_cash_flows_from_investing_activities',
                    'cash_flows_from_investing_activities', 'cfi')
    cff = _kbs_find(r, 'net_cash_flows_from_financing_activities',
                    'cash_flows_from_financing_activities', 'cff')
    cfo_ty = _to_ty(cfo)
    cfi_ty = _to_ty(cfi)
    return {
        'cfo': cfo_ty,
        'cfi': cfi_ty,
        'cff': _to_ty(cff),
        'free_cashflow': (cfo_ty + cfi_ty) if (cfo_ty is not None and cfi_ty is not None) else None,
    }


# ── upserts ──────────────────────────────────────────────────────────────────

def _upsert_income(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_income_stmt_quarterly
            (ticker, year, quarter, revenue, gross_profit, ebit, net_income, eps, crawl_time, source, group_name)
        VALUES (:ticker, :year, :quarter, :revenue, :gross_profit, :ebit, :net_income, :eps, :crawl_time, :source, :group_name)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            revenue=EXCLUDED.revenue, gross_profit=EXCLUDED.gross_profit,
            ebit=EXCLUDED.ebit, net_income=EXCLUDED.net_income,
            eps=EXCLUDED.eps, crawl_time=EXCLUDED.crawl_time,
            source=EXCLUDED.source, group_name=EXCLUDED.group_name
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time,
           'source': 'vnstock3', 'group_name': 'stock'})


def _upsert_bs(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_balance_sheet_quarterly
            (ticker, year, quarter, total_assets, total_liabilities, equity, cash, crawl_time, source, group_name)
        VALUES (:ticker, :year, :quarter, :total_assets, :total_liabilities, :equity, :cash, :crawl_time, :source, :group_name)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            total_assets=EXCLUDED.total_assets, total_liabilities=EXCLUDED.total_liabilities,
            equity=EXCLUDED.equity, cash=EXCLUDED.cash, crawl_time=EXCLUDED.crawl_time,
            source=EXCLUDED.source, group_name=EXCLUDED.group_name
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time,
           'source': 'vnstock3', 'group_name': 'stock'})


def _upsert_cf(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_cashflow_quarterly
            (ticker, year, quarter, cfo, cfi, cff, free_cashflow, crawl_time, source, group_name)
        VALUES (:ticker, :year, :quarter, :cfo, :cfi, :cff, :free_cashflow, :crawl_time, :source, :group_name)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            cfo=EXCLUDED.cfo, cfi=EXCLUDED.cfi, cff=EXCLUDED.cff,
            free_cashflow=EXCLUDED.free_cashflow, crawl_time=EXCLUDED.crawl_time,
            source=EXCLUDED.source, group_name=EXCLUDED.group_name
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time,
           'source': 'vnstock3', 'group_name': 'stock'})


# ── rate-limit-aware fetch ───────────────────────────────────────────────────

def _kbs_call_with_retry(fn, label: str, max_retries=3):
    """Call fn(); on rate-limit (including SystemExit) sleep 40s and retry."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except BaseException as e:
            msg = str(e).lower()
            is_rate_limit = ('rate limit' in msg or 'giới hạn' in msg
                             or '429' in msg or isinstance(e, SystemExit))
            if is_rate_limit and attempt < max_retries:
                wait = 40 + attempt * 20   # 40s, 60s, 80s
                print(f"  {label} rate limit — waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
                continue
            if isinstance(e, SystemExit):
                raise RuntimeError(f"KBS rate limit exhausted for {label}") from e
            raise


# ── multi-page fetch ──────────────────────────────────────────────────────────

def _kbs_fetch_all_pages(ds, report_type: str, max_pages: int):
    """Fetch up to max_pages quarterly pages from KBS and return combined DataFrame.

    Each page covers 1 year (4 quarters). page=1 → most recent year.
    Returns None if no data. Stops early if a page returns empty results.
    """
    import pandas as pd

    all_dfs = []
    for page in range(1, max_pages + 1):
        try:
            def _fn(p=page):
                resp = ds._fetch_financial_data(report_type=report_type, period_type=2, page=p)
                if not resp or 'Content' not in resp or not resp['Content']:
                    return None
                report_key = list(resp['Content'].keys())[0]
                return ds._parse_financial_response(resp, report_key)

            df = _kbs_call_with_retry(_fn, f'{report_type} p{page}')
            if df is None or df.empty:
                break   # no more data

            all_dfs.append(df)
            if page < max_pages:
                time.sleep(4)   # ~15 req/min — safely under KBS 20 req/min limit
        except Exception as e:
            print(f"    page {page} error: {e}")
            break

    if not all_dfs:
        return None
    if len(all_dfs) == 1:
        return all_dfs[0]

    # Merge all pages: same item_id rows, different quarter columns
    base = all_dfs[0]
    for df in all_dfs[1:]:
        new_q_cols = [c for c in df.columns if re.match(r'\d{4}-Q\d', str(c))]
        if new_q_cols:
            base = base.merge(df[['item_id'] + new_q_cols], on='item_id', how='left')
    return base


# ── main fetch ───────────────────────────────────────────────────────────────

def fetch_and_store_financials(ticker: str, crawl_time: datetime):
    """Fetch income stmt, balance sheet, cash flow for ticker via KBS → VCI fallback."""

    # --- Layer 1: vnstock 3.5+ (KBS — works from VN IP) ---
    try:
        from vnstock import Vnstock as VnstockNew
        stock_kbs = VnstockNew().stock(symbol=ticker, source='KBS')
        ds = stock_kbs.finance.data_source   # KBS Finance — exposes _fetch_financial_data(page=N)

        pages_label = f'{FINANCIALS_MAX_PAGES}p'

        # Income statement
        try:
            inc_df = _kbs_fetch_all_pages(ds, 'KQKD', FINANCIALS_MAX_PAGES)
            if inc_df is not None and not inc_df.empty:
                rows = _pivot_kbs_wide(inc_df)
                with engine.connect() as conn:
                    for r in rows:
                        _upsert_income(conn, ticker, r['year'], r['quarter'],
                                       _kbs_income_row(r), crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Income (KBS/{pages_label}): {len(rows)} quarters")
        except Exception as e:
            print(f"  [{ticker}] KBS income error: {e}")

        time.sleep(5)

        # Balance sheet
        try:
            bs_df = _kbs_fetch_all_pages(ds, 'CDKT', FINANCIALS_MAX_PAGES)
            if bs_df is not None and not bs_df.empty:
                rows = _pivot_kbs_wide(bs_df)
                with engine.connect() as conn:
                    for r in rows:
                        _upsert_bs(conn, ticker, r['year'], r['quarter'],
                                   _kbs_bs_row(r), crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Balance sheet (KBS/{pages_label}): {len(rows)} quarters")
        except Exception as e:
            print(f"  [{ticker}] KBS balance sheet error: {e}")

        time.sleep(5)

        # Cash flow
        try:
            cf_df = _kbs_fetch_all_pages(ds, 'LCTT', FINANCIALS_MAX_PAGES)
            if cf_df is not None and not cf_df.empty:
                rows = _pivot_kbs_wide(cf_df)
                non_null = 0
                with engine.connect() as conn:
                    for r in rows:
                        fields = _kbs_cf_row(r)
                        if any(v is not None for v in fields.values()):
                            _upsert_cf(conn, ticker, r['year'], r['quarter'],
                                       fields, crawl_time)
                            non_null += 1
                    conn.commit()
                print(f"  [{ticker}] Cash flow (KBS/{pages_label}): {len(rows)} quarters ({non_null} non-null)")
        except Exception as e:
            print(f"  [{ticker}] KBS cash flow error: {e}")

        return  # KBS succeeded — skip VCI

    except ImportError:
        pass
    except Exception as e:
        print(f"  [{ticker}] KBS init error: {e}")

    # --- Layer 2: vnstock3 VCI (fallback, VN IP only) ---
    try:
        from vnstock3 import Vnstock
    except ImportError:
        raise RuntimeError("vnstock/vnstock3 not available")

    try:
        stock = Vnstock().stock(symbol=ticker, source='VCI')

        # VCI returns values in tỷ VND directly — no unit conversion needed
        try:
            income_df = stock.finance.income_statement(period='quarter', lang='en')
            if income_df is not None and not income_df.empty:
                with engine.connect() as conn:
                    for _, row in income_df.iterrows():
                        year = int(row.get('year', 0)) if row.get('year') else None
                        quarter = int(row.get('quarter', 0)) if row.get('quarter') else None
                        if not year or not quarter:
                            continue
                        _upsert_income(conn, ticker, year, quarter, {
                            'revenue':      _safe_float(row.get('revenue') or row.get('Net Revenue')),
                            'gross_profit': _safe_float(row.get('gross_profit') or row.get('Gross Profit')),
                            'ebit':         _safe_float(row.get('ebit') or row.get('EBIT')),
                            'net_income':   _safe_float(row.get('net_income') or row.get('Net Income')),
                            'eps':          _safe_float(row.get('eps') or row.get('EPS')),
                        }, crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Income stmt (VCI): {len(income_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] VCI income error: {e}")

        time.sleep(2)

        try:
            bs_df = stock.finance.balance_sheet(period='quarter', lang='en')
            if bs_df is not None and not bs_df.empty:
                with engine.connect() as conn:
                    for _, row in bs_df.iterrows():
                        year = int(row.get('year', 0)) if row.get('year') else None
                        quarter = int(row.get('quarter', 0)) if row.get('quarter') else None
                        if not year or not quarter:
                            continue
                        _upsert_bs(conn, ticker, year, quarter, {
                            'total_assets':      _safe_float(row.get('total_assets') or row.get('Total Assets')),
                            'total_liabilities': _safe_float(row.get('total_liabilities') or row.get('Total Liabilities')),
                            'equity':            _safe_float(row.get('equity') or row.get('Equity')),
                            'cash':              _safe_float(row.get('cash') or row.get('Cash')),
                        }, crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Balance sheet (VCI): {len(bs_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] VCI balance sheet error: {e}")

        time.sleep(2)

        try:
            cf_df = stock.finance.cash_flow(period='quarter', lang='en')
            if cf_df is not None and not cf_df.empty:
                with engine.connect() as conn:
                    for _, row in cf_df.iterrows():
                        year = int(row.get('year', 0)) if row.get('year') else None
                        quarter = int(row.get('quarter', 0)) if row.get('quarter') else None
                        if not year or not quarter:
                            continue
                        cfo = _safe_float(row.get('cfo') or row.get('Operating Cash Flow'))
                        cfi = _safe_float(row.get('cfi') or row.get('Investing Cash Flow'))
                        cff = _safe_float(row.get('cff') or row.get('Financing Cash Flow'))
                        _upsert_cf(conn, ticker, year, quarter, {
                            'cfo': cfo, 'cfi': cfi, 'cff': cff,
                            'free_cashflow': (cfo + cfi) if (cfo is not None and cfi is not None) else None,
                        }, crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Cash flow (VCI): {len(cf_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] VCI cash flow error: {e}")

    except Exception as e:
        import traceback
        print(f"  [{ticker}] FATAL: {e}\n  {traceback.format_exc()}")
        raise


def main():
    ensure_tables()
    crawl_time = datetime.now()
    success = 0
    errors = 0

    print(f"Mode: {'BACKFILL' if FINANCIALS_MAX_PAGES > 1 else 'incremental'} "
          f"({FINANCIALS_MAX_PAGES} page(s) per statement ≈ {FINANCIALS_MAX_PAGES * 4} quarters max)")

    for ticker in VN30_TICKERS:
        print(f"\n  [{ticker}] Fetching financial statements...")
        try:
            fetch_and_store_financials(ticker, crawl_time)
            success += 1
            time.sleep(5)  # inter-ticker pause — stay under 12 req/min
        except Exception:
            errors += 1

    print(f"\n{'='*60}")
    print(f"VN30 Financials Crawler done. Success: {success}, Errors: {errors}")
    print(f"Unit: tỷ VND (monetary), VND/share (EPS)")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
