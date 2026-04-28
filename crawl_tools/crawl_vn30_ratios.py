"""
VN30 Daily Financial Ratios Crawler (P/E, P/B, ROE, ROA, etc.)
Source: vnstock3 (SSI/TCBS data)
Schedule: Daily 17:30 VN (10:30 AM UTC) — after HSX close
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
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"VN30 Financial Ratios Crawler — {date_str} {current_date.strftime('%H:%M')}")
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


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn30_ratio_daily (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL,
                date DATE NOT NULL,
                pe FLOAT,
                pb FLOAT,
                ps FLOAT,
                roe FLOAT,
                roa FLOAT,
                eps FLOAT,
                dividend_yield FLOAT,
                market_cap_billion FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'vnstock3',
                group_name VARCHAR(20) NOT NULL DEFAULT 'stock',
                UNIQUE (ticker, date)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_vn30_ratios_ticker_date
            ON vn30_ratio_daily (ticker, date)
        """))
        for col, definition in [
            ('source',     "TEXT NOT NULL DEFAULT 'vnstock3'"),
            ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'stock'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn30_ratio_daily ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.commit()
    print("Table vn30_ratio_daily ready.")


def _safe_float(val):
    try:
        if val is None:
            return None
        return float(val)
    except (ValueError, TypeError):
        return None


def _kbs_find(lookup: dict, *suffixes):
    """Find value by exact key or suffix match (handles 'r_1.p_e' → 'p_e')."""
    for suffix in suffixes:
        if suffix in lookup:
            return lookup[suffix]
        for k, v in lookup.items():
            if k.endswith('.' + suffix) or k.endswith('_' + suffix):
                return v
    return None


def _parse_kbs_ratio(df) -> dict:
    """Parse wide-format KBS ratio DataFrame (item_id as lookup key)."""
    # Use col index 2 = most recent period; fallback to last non-null column
    lookup = dict(zip(df['item_id'], df.iloc[:, 2]))
    return {
        'pe':             _safe_float(_kbs_find(lookup, 'p_e', 'pe', 'price_to_earnings')),
        'pb':             _safe_float(_kbs_find(lookup, 'p_b', 'pb', 'price_to_book')),
        'ps':             None,
        'roe':            _safe_float(_kbs_find(lookup, 'roe_trailling', 'roe_trailing', 'roe')),
        'roa':            _safe_float(_kbs_find(lookup, 'roa_trailling', 'roa_trailing', 'roa')),
        'eps':            _safe_float(_kbs_find(lookup, 'trailing_eps', 'eps', 'basic_eps', 'diluted_eps')),
        'dividend_yield': _safe_float(_kbs_find(lookup, 'dividend_yield', 'div_yield')),
        'market_cap_billion': None,
    }


def fetch_ratios_vnstock(ticker: str) -> dict:
    """Fetch latest financial ratios. Tries vnstock (KBS) → vnstock3 (VCI)."""
    # --- Layer 1: vnstock 3.5+ (KBS — works from any IP) ---
    try:
        from vnstock import Vnstock
        stock = Vnstock().stock(symbol=ticker, source='KBS')
        ratio_df = stock.finance.ratio(period='quarter')
        if ratio_df is not None and not ratio_df.empty:
            return _parse_kbs_ratio(ratio_df)
    except ImportError:
        pass
    except Exception as e:
        print(f"  [{ticker}] vnstock KBS ratio error: {e}")

    # --- Layer 2: vnstock3 (VCI source) ---
    try:
        from vnstock3 import Vnstock as Vnstock3
    except ImportError:
        print(f"  [{ticker}] vnstock/vnstock3 không khả dụng — skip")
        return {}
    try:
        stock = Vnstock3().stock(symbol=ticker, source='VCI')

        try:
            ratio_df = stock.finance.ratio(period='quarter', lang='en')
            if ratio_df is not None and not ratio_df.empty:
                row = ratio_df.iloc[-1]
                return {
                    'pe': _safe_float(row.get('pe') or row.get('P/E')),
                    'pb': _safe_float(row.get('pb') or row.get('P/B')),
                    'ps': _safe_float(row.get('ps') or row.get('P/S')),
                    'roe': _safe_float(row.get('roe') or row.get('ROE')),
                    'roa': _safe_float(row.get('roa') or row.get('ROA')),
                    'eps': _safe_float(row.get('eps') or row.get('EPS')),
                    'dividend_yield': _safe_float(row.get('dividend_yield')),
                    'market_cap_billion': None,
                }
        except Exception as e:
            print(f"  [{ticker}] VCI ratio() error: {e}")

        try:
            overview = stock.company.overview()
            if overview is not None and not overview.empty:
                row = overview.iloc[0]
                return {
                    'pe': _safe_float(row.get('pe')),
                    'pb': _safe_float(row.get('pb')),
                    'ps': _safe_float(row.get('ps')),
                    'roe': _safe_float(row.get('roe')),
                    'roa': _safe_float(row.get('roa')),
                    'eps': _safe_float(row.get('eps')),
                    'dividend_yield': _safe_float(row.get('dividendYield')),
                    'market_cap_billion': _safe_float(row.get('marketCap', 0)) / 1e9 if row.get('marketCap') else None,
                }
        except Exception as e:
            print(f"  [{ticker}] VCI overview() error: {e}")

    except Exception as e:
        print(f"  [{ticker}] vnstock3 error: {e}")
    return {}


def upsert_ratios(ticker: str, ratios: dict, trade_date: str, crawl_time: datetime):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn30_ratio_daily
                (ticker, date, pe, pb, ps, roe, roa, eps, dividend_yield, market_cap_billion, crawl_time, source, group_name)
            VALUES
                (:ticker, :date, :pe, :pb, :ps, :roe, :roa, :eps, :dividend_yield, :market_cap_billion, :crawl_time, :source, :group_name)
            ON CONFLICT (ticker, date) DO UPDATE SET
                pe = EXCLUDED.pe,
                pb = EXCLUDED.pb,
                ps = EXCLUDED.ps,
                roe = EXCLUDED.roe,
                roa = EXCLUDED.roa,
                eps = EXCLUDED.eps,
                dividend_yield = EXCLUDED.dividend_yield,
                market_cap_billion = EXCLUDED.market_cap_billion,
                crawl_time = EXCLUDED.crawl_time,
                source = EXCLUDED.source,
                group_name = EXCLUDED.group_name
        """), {
            'ticker': ticker,
            'date': trade_date,
            **ratios,
            'crawl_time': crawl_time,
            'source': 'vnstock3',
            'group_name': 'stock',
        })
        conn.commit()


def main():
    ensure_table()
    crawl_time = datetime.now()
    success = 0
    errors = 0

    for ticker in VN30_TICKERS:
        print(f"\n  [{ticker}] Fetching ratios...")
        try:
            ratios = fetch_ratios_vnstock(ticker)
            if ratios:
                upsert_ratios(ticker, ratios, date_str, crawl_time)
                print(f"  [{ticker}] OK — P/E: {ratios.get('pe')}, P/B: {ratios.get('pb')}, ROE: {ratios.get('roe')}")
                success += 1
            else:
                print(f"  [{ticker}] No ratio data returned")
            time.sleep(0.5)
        except Exception as e:
            import traceback
            print(f"  [{ticker}] ERROR: {e}")
            print(f"  {traceback.format_exc()}")
            errors += 1

    print(f"\n{'='*60}")
    print(f"VN30 Ratios Crawler done. Success: {success}, Errors: {errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
