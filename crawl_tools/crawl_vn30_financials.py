"""
VN30 Quarterly Financial Statements Crawler (Income, Balance Sheet, Cash Flow)
Source: vnstock3 (SSI/TCBS data)
Schedule: Quarterly — 15th of Jan, Apr, Jul, Oct (15:00 VN = 08:00 UTC)
Also supports backfill of last N quarters.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

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

BACKFILL_QUARTERS = 8  # Backfill last 8 quarters by default


def ensure_tables():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_income_stmt_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                revenue FLOAT,
                gross_profit FLOAT,
                ebit FLOAT,
                net_income FLOAT,
                eps FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                UNIQUE (ticker, year, quarter)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_balance_sheet_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                total_assets FLOAT,
                total_liabilities FLOAT,
                equity FLOAT,
                cash FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                UNIQUE (ticker, year, quarter)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_cashflow_quarterly (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                cfo FLOAT,
                cfi FLOAT,
                cff FLOAT,
                free_cashflow FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                UNIQUE (ticker, year, quarter)
            )
        """))
        conn.commit()
    print("Tables vn30_income_stmt_quarterly, vn30_balance_sheet_quarterly, vn30_cashflow_quarterly ready.")


def _safe_float(val):
    try:
        if val is None:
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def _pivot_kbs_wide(df) -> list:
    """Convert KBS wide-format (items as rows, quarters as cols) to list of dicts.
    Returns: [{'year': 2025, 'quarter': 4, 'item_id_1': val, ...}, ...]
    """
    import re
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


def _kbs_find(r: dict, *suffixes):
    """Find value by exact key or suffix match (handles 'n_3.net_revenue' → 'net_revenue')."""
    for suffix in suffixes:
        if suffix in r:
            return r[suffix]
        for k, v in r.items():
            if k == suffix or k.endswith('.' + suffix) or k.endswith('_' + suffix):
                return v
    return None


def _kbs_income_row(r: dict) -> dict:
    """Map KBS item_ids to income statement fields (handles banking + industrial)."""
    revenue = _kbs_find(r, 'net_revenue', 'revenue', 'net_interest_income', 'total_operating_income')
    gross   = _kbs_find(r, 'gross_profit', 'net_operating_income', 'net_fee_and_commission_income')
    ebit    = _kbs_find(r, 'operating_profit', 'ebit',
                        'operating_profit_before_provision_for_credit_losses',
                        'profit_before_provision', 'profit_before_tax')
    net_inc = _kbs_find(r, 'net_profit_after_tax', 'profit_after_tax', 'net_income',
                        'profit_after_tax_for_shareholders_of_parent_company',
                        'net_profit_atttributable_to_the_equity_holders_of_the_bank')
    eps_val = _kbs_find(r, 'earnings_per_share_vnd', 'earning_per_share_vnd', 'eps',
                        'diluted_earnings_per_share')
    return {
        'revenue':      _safe_float(revenue),
        'gross_profit': _safe_float(gross),
        'ebit':         _safe_float(ebit),
        'net_income':   _safe_float(net_inc),
        'eps':          _safe_float(eps_val),
    }


def _kbs_bs_row(r: dict) -> dict:
    total_assets = _kbs_find(r, 'total_assets')
    total_liab   = _kbs_find(r, 'total_liabilities', 'total_debt', 'liabilities')
    equity       = _kbs_find(r, 'owners_equity', 'equity', 'total_equity',
                             'shareholders_equity', 'owner_equity')
    cash         = _kbs_find(r, 'cash_and_cash_equivalents', 'cash_and_gold',
                             'cash', 'cash_and_short_term_investments')
    return {
        'total_assets':      _safe_float(total_assets),
        'total_liabilities': _safe_float(total_liab),
        'equity':            _safe_float(equity),
        'cash':              _safe_float(cash),
    }


def _kbs_cf_row(r: dict) -> dict:
    cfo = _kbs_find(r, 'net_cash_flows_from_operating_activities',
                    'cash_flows_from_operating_activities', 'cfo')
    cfi = _kbs_find(r, 'net_cash_flows_from_investing_activities',
                    'cash_flows_from_investing_activities', 'cfi')
    cff = _kbs_find(r, 'net_cash_flows_from_financing_activities',
                    'cash_flows_from_financing_activities', 'cff')
    cfo_f = _safe_float(cfo)
    cfi_f = _safe_float(cfi)
    return {
        'cfo': cfo_f, 'cfi': cfi_f,
        'cff': _safe_float(cff),
        'free_cashflow': (cfo_f + cfi_f) if (cfo_f is not None and cfi_f is not None) else None,
    }


def _upsert_income(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_income_stmt_quarterly
            (ticker, year, quarter, revenue, gross_profit, ebit, net_income, eps, crawl_time)
        VALUES (:ticker, :year, :quarter, :revenue, :gross_profit, :ebit, :net_income, :eps, :crawl_time)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            revenue=EXCLUDED.revenue, gross_profit=EXCLUDED.gross_profit,
            ebit=EXCLUDED.ebit, net_income=EXCLUDED.net_income,
            eps=EXCLUDED.eps, crawl_time=EXCLUDED.crawl_time
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})


def _upsert_bs(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_balance_sheet_quarterly
            (ticker, year, quarter, total_assets, total_liabilities, equity, cash, crawl_time)
        VALUES (:ticker, :year, :quarter, :total_assets, :total_liabilities, :equity, :cash, :crawl_time)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            total_assets=EXCLUDED.total_assets, total_liabilities=EXCLUDED.total_liabilities,
            equity=EXCLUDED.equity, cash=EXCLUDED.cash, crawl_time=EXCLUDED.crawl_time
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})


def _upsert_cf(conn, ticker, year, quarter, fields, crawl_time):
    conn.execute(text("""
        INSERT INTO vn30_cashflow_quarterly
            (ticker, year, quarter, cfo, cfi, cff, free_cashflow, crawl_time)
        VALUES (:ticker, :year, :quarter, :cfo, :cfi, :cff, :free_cashflow, :crawl_time)
        ON CONFLICT (ticker, year, quarter) DO UPDATE SET
            cfo=EXCLUDED.cfo, cfi=EXCLUDED.cfi, cff=EXCLUDED.cff,
            free_cashflow=EXCLUDED.free_cashflow, crawl_time=EXCLUDED.crawl_time
    """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})


def fetch_and_store_financials(ticker: str, crawl_time: datetime):
    """Fetch income statement, balance sheet, and cash flow for a ticker."""
    # --- Layer 1: vnstock 3.5+ (KBS — works from any IP) ---
    try:
        from vnstock import Vnstock as VnstockNew
        stock_kbs = VnstockNew().stock(symbol=ticker, source='KBS')

        try:
            inc_df = stock_kbs.finance.income_statement(period='quarter')
            if inc_df is not None and not inc_df.empty:
                rows = _pivot_kbs_wide(inc_df)
                with engine.connect() as conn:
                    for r in rows:
                        _upsert_income(conn, ticker, r['year'], r['quarter'],
                                       _kbs_income_row(r), crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Income (KBS): {len(rows)} quarters")
        except Exception as e:
            print(f"  [{ticker}] KBS income error: {e}")

        time.sleep(0.3)

        try:
            bs_df = stock_kbs.finance.balance_sheet(period='quarter')
            if bs_df is not None and not bs_df.empty:
                rows = _pivot_kbs_wide(bs_df)
                with engine.connect() as conn:
                    for r in rows:
                        _upsert_bs(conn, ticker, r['year'], r['quarter'],
                                   _kbs_bs_row(r), crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Balance sheet (KBS): {len(rows)} quarters")
        except Exception as e:
            print(f"  [{ticker}] KBS balance sheet error: {e}")

        time.sleep(0.3)

        try:
            cf_df = stock_kbs.finance.cash_flow(period='quarter')
            if cf_df is not None and not cf_df.empty:
                rows = _pivot_kbs_wide(cf_df)
                with engine.connect() as conn:
                    for r in rows:
                        _upsert_cf(conn, ticker, r['year'], r['quarter'],
                                   _kbs_cf_row(r), crawl_time)
                    conn.commit()
                print(f"  [{ticker}] Cash flow (KBS): {len(rows)} quarters")
        except Exception as e:
            print(f"  [{ticker}] KBS cash flow error: {e}")

        return  # KBS succeeded, skip VCI layer

    except ImportError:
        pass
    except Exception as e:
        print(f"  [{ticker}] KBS init error: {e}")

    # --- Layer 2: vnstock3 (VCI source) ---
    try:
        from vnstock3 import Vnstock
    except ImportError:
        raise RuntimeError(
            "vnstock/vnstock3 không khả dụng. "
            "Crawler này sẽ chạy tự động trên server khi deploy."
        )
    try:
        stock = Vnstock().stock(symbol=ticker, source='VCI')

        # --- Income Statement ---
        try:
            income_df = stock.finance.income_statement(period='quarter', lang='en')
            if income_df is not None and not income_df.empty:
                with engine.connect() as conn:
                    for _, row in income_df.iterrows():
                        year = int(row.get('year', 0)) if row.get('year') else None
                        quarter = int(row.get('quarter', 0)) if row.get('quarter') else None
                        if not year or not quarter:
                            continue
                        conn.execute(text("""
                            INSERT INTO vn30_income_stmt_quarterly
                                (ticker, year, quarter, revenue, gross_profit, ebit, net_income, eps, crawl_time)
                            VALUES
                                (:ticker, :year, :quarter, :revenue, :gross_profit, :ebit, :net_income, :eps, :crawl_time)
                            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                                revenue = EXCLUDED.revenue,
                                gross_profit = EXCLUDED.gross_profit,
                                ebit = EXCLUDED.ebit,
                                net_income = EXCLUDED.net_income,
                                eps = EXCLUDED.eps,
                                crawl_time = EXCLUDED.crawl_time
                        """), {
                            'ticker': ticker,
                            'year': year,
                            'quarter': quarter,
                            'revenue': _safe_float(row.get('revenue') or row.get('Net Revenue')),
                            'gross_profit': _safe_float(row.get('gross_profit') or row.get('Gross Profit')),
                            'ebit': _safe_float(row.get('ebit') or row.get('EBIT')),
                            'net_income': _safe_float(row.get('net_income') or row.get('Net Income')),
                            'eps': _safe_float(row.get('eps') or row.get('EPS')),
                            'crawl_time': crawl_time,
                        })
                    conn.commit()
                print(f"  [{ticker}] Income stmt: {len(income_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] Income stmt error: {e}")

        time.sleep(0.3)

        # --- Balance Sheet ---
        try:
            bs_df = stock.finance.balance_sheet(period='quarter', lang='en')
            if bs_df is not None and not bs_df.empty:
                with engine.connect() as conn:
                    for _, row in bs_df.iterrows():
                        year = int(row.get('year', 0)) if row.get('year') else None
                        quarter = int(row.get('quarter', 0)) if row.get('quarter') else None
                        if not year or not quarter:
                            continue
                        conn.execute(text("""
                            INSERT INTO vn30_balance_sheet_quarterly
                                (ticker, year, quarter, total_assets, total_liabilities, equity, cash, crawl_time)
                            VALUES
                                (:ticker, :year, :quarter, :total_assets, :total_liabilities, :equity, :cash, :crawl_time)
                            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                                total_assets = EXCLUDED.total_assets,
                                total_liabilities = EXCLUDED.total_liabilities,
                                equity = EXCLUDED.equity,
                                cash = EXCLUDED.cash,
                                crawl_time = EXCLUDED.crawl_time
                        """), {
                            'ticker': ticker,
                            'year': year,
                            'quarter': quarter,
                            'total_assets': _safe_float(row.get('total_assets') or row.get('Total Assets')),
                            'total_liabilities': _safe_float(row.get('total_liabilities') or row.get('Total Liabilities')),
                            'equity': _safe_float(row.get('equity') or row.get('Equity')),
                            'cash': _safe_float(row.get('cash') or row.get('Cash')),
                            'crawl_time': crawl_time,
                        })
                    conn.commit()
                print(f"  [{ticker}] Balance sheet: {len(bs_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] Balance sheet error: {e}")

        time.sleep(0.3)

        # --- Cash Flow ---
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
                        fcf = (cfo + cfi) if (cfo is not None and cfi is not None) else None
                        conn.execute(text("""
                            INSERT INTO vn30_cashflow_quarterly
                                (ticker, year, quarter, cfo, cfi, cff, free_cashflow, crawl_time)
                            VALUES
                                (:ticker, :year, :quarter, :cfo, :cfi, :cff, :free_cashflow, :crawl_time)
                            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                                cfo = EXCLUDED.cfo,
                                cfi = EXCLUDED.cfi,
                                cff = EXCLUDED.cff,
                                free_cashflow = EXCLUDED.free_cashflow,
                                crawl_time = EXCLUDED.crawl_time
                        """), {
                            'ticker': ticker,
                            'year': year,
                            'quarter': quarter,
                            'cfo': cfo,
                            'cfi': cfi,
                            'cff': cff,
                            'free_cashflow': fcf,
                            'crawl_time': crawl_time,
                        })
                    conn.commit()
                print(f"  [{ticker}] Cash flow: {len(cf_df)} quarters")
        except Exception as e:
            print(f"  [{ticker}] Cash flow error: {e}")

    except Exception as e:
        import traceback
        print(f"  [{ticker}] FATAL: {e}")
        print(f"  {traceback.format_exc()}")
        raise


def main():
    ensure_tables()
    crawl_time = datetime.now()
    success = 0
    errors = 0

    for ticker in VN30_TICKERS:
        print(f"\n  [{ticker}] Fetching financial statements...")
        try:
            fetch_and_store_financials(ticker, crawl_time)
            success += 1
            time.sleep(1.0)   # Polite delay between tickers
        except Exception:
            errors += 1

    print(f"\n{'='*60}")
    print(f"VN30 Financials Crawler done. Success: {success}, Errors: {errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
