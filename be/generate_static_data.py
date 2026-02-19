"""
Static Data Generator for Chart CDN
Generates pre-computed JSON files for all charts.
These files are served via GitHub Pages for instant loading.

Run after each crawler completes to update the static data.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Output directory for static JSON files
STATIC_DIR = Path(__file__).parent.parent / 'data'
STATIC_DIR.mkdir(exist_ok=True)

# Database connections
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
ARGUS_FINTEL_DB = os.getenv('ARGUS_FINTEL_DB')
GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')

if not CRAWLING_BOT_DB:
    print("ERROR: CRAWLING_BOT_DB not set")
    exit(1)

engine_crawl = create_engine(CRAWLING_BOT_DB)
engine_argus = create_engine(ARGUS_FINTEL_DB) if ARGUS_FINTEL_DB else None
engine_global = create_engine(GLOBAL_INDICATOR_DB) if GLOBAL_INDICATOR_DB else None

# Time periods
PERIODS = {
    '7d': 7,
    '1m': 30,
    '1y': 365,
    'all': 3650  # ~10 years
}


def get_date_filter(period):
    """Get date filter string for SQL query."""
    days = PERIODS.get(period, 30)
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


def save_json(filename, data):
    """Save data to JSON file with metadata."""
    output = {
        'generated_at': datetime.now().isoformat(),
        'data': data
    }
    filepath = STATIC_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))
    print(f"  Saved: {filepath.name} ({filepath.stat().st_size:,} bytes)")


# ============================================================
# GOLD DATA
# ============================================================
def generate_gold_data():
    """Generate static JSON for gold prices."""
    print("\n--- Generating Gold Data ---")

    # Get available gold types
    with engine_crawl.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT type FROM vn_gold_24h_hist
            WHERE type IS NOT NULL
            ORDER BY type
        """))
        gold_types = [row[0] for row in result.fetchall()]

    print(f"  Gold types: {gold_types}")

    # Generate for each type and period
    for gold_type in gold_types[:5]:  # Top 5 types
        for period in ['7d', '1m', '1y']:
            date_filter = get_date_filter(period)

            with engine_crawl.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT date, buy_price, sell_price
                    FROM (
                        SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
                        FROM vn_gold_24h_hist
                        WHERE date >= '{date_filter}'
                        AND type = :gold_type
                        ORDER BY date, crawl_time DESC
                    ) subquery
                    ORDER BY date ASC
                """), {'gold_type': gold_type})
                rows = result.fetchall()

            data = {
                'type': gold_type,
                'period': period,
                'count': len(rows),
                'dates': [row[0].strftime('%Y-%m-%d') for row in rows],
                'buy_prices': [float(row[1]) if row[1] else 0 for row in rows],
                'sell_prices': [float(row[2]) if row[2] else 0 for row in rows]
            }

            # Sanitize filename
            safe_type = gold_type.replace(' ', '_').replace('/', '_')
            save_json(f'gold_{safe_type}_{period}.json', data)

    # Generate gold types list
    save_json('gold_types.json', {'types': gold_types})


# ============================================================
# SILVER DATA
# ============================================================
def generate_silver_data():
    """Generate static JSON for silver prices."""
    print("\n--- Generating Silver Data ---")

    for period in ['7d', '1m', '1y']:
        date_filter = get_date_filter(period)

        with engine_crawl.connect() as conn:
            result = conn.execute(text(f"""
                SELECT date, buy_price, sell_price
                FROM (
                    SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
                    FROM vn_silver_phuquy_hist
                    WHERE date >= '{date_filter}'
                    ORDER BY date, crawl_time DESC
                ) subquery
                ORDER BY date ASC
            """))
            rows = result.fetchall()

        data = {
            'period': period,
            'count': len(rows),
            'dates': [row[0].strftime('%Y-%m-%d') for row in rows],
            'buy_prices': [float(row[1]) if row[1] else 0 for row in rows],
            'sell_prices': [float(row[2]) if row[2] else 0 for row in rows]
        }

        save_json(f'silver_{period}.json', data)


# ============================================================
# SBV INTERBANK DATA
# ============================================================
def generate_sbv_data():
    """Generate static JSON for SBV interbank rates."""
    print("\n--- Generating SBV Interbank Data ---")

    for period in ['7d', '1m', '1y']:
        date_filter = get_date_filter(period)

        with engine_crawl.connect() as conn:
            result = conn.execute(text(f"""
                SELECT date, ls_quadem, ls_1m, ls_3m, rediscount_rate, refinancing_rate
                FROM (
                    SELECT DISTINCT ON (date) date, ls_quadem, ls_1m, ls_3m,
                           rediscount_rate, refinancing_rate, crawl_time
                    FROM vn_sbv_interbankrate
                    WHERE date >= '{date_filter}'
                    ORDER BY date, crawl_time DESC
                ) subquery
                ORDER BY date ASC
            """))
            rows = result.fetchall()

        data = {
            'period': period,
            'count': len(rows),
            'dates': [row[0].strftime('%Y-%m-%d') for row in rows],
            'overnight': [float(row[1]) if row[1] else 0 for row in rows],
            'month_1': [float(row[2]) if row[2] else 0 for row in rows],
            'month_3': [float(row[3]) if row[3] else 0 for row in rows],
            'rediscount': [float(row[4]) if row[4] else 0 for row in rows],
            'refinancing': [float(row[5]) if row[5] else 0 for row in rows]
        }

        save_json(f'sbv_{period}.json', data)


# ============================================================
# TERM DEPOSIT DATA
# ============================================================
def generate_termdepo_data():
    """Generate static JSON for bank term deposit rates."""
    print("\n--- Generating Term Deposit Data ---")

    # Get available banks
    with engine_crawl.connect() as conn:
        result = conn.execute(text("""
            SELECT DISTINCT bank_code FROM vn_bank_termdepo
            WHERE bank_code IS NOT NULL
            ORDER BY bank_code
        """))
        banks = [row[0] for row in result.fetchall()]

    print(f"  Banks: {banks}")

    for bank in banks:
        for period in ['7d', '1m', '1y']:
            date_filter = get_date_filter(period)

            with engine_crawl.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT date, term_1m, term_3m, term_6m, term_12m, term_24m
                    FROM (
                        SELECT DISTINCT ON (date) date, term_1m, term_3m, term_6m, term_12m, term_24m, crawl_time
                        FROM vn_bank_termdepo
                        WHERE date >= '{date_filter}'
                        AND bank_code = :bank
                        ORDER BY date, crawl_time DESC
                    ) subquery
                    ORDER BY date ASC
                """), {'bank': bank})
                rows = result.fetchall()

            data = {
                'bank': bank,
                'period': period,
                'count': len(rows),
                'dates': [row[0].strftime('%Y-%m-%d') for row in rows],
                'term_1m': [float(row[1]) if row[1] else 0 for row in rows],
                'term_3m': [float(row[2]) if row[2] else 0 for row in rows],
                'term_6m': [float(row[3]) if row[3] else 0 for row in rows],
                'term_12m': [float(row[4]) if row[4] else 0 for row in rows],
                'term_24m': [float(row[5]) if row[5] else 0 for row in rows]
            }

            save_json(f'termdepo_{bank}_{period}.json', data)

    # Generate banks list
    save_json('termdepo_banks.json', {'banks': banks})


# ============================================================
# MANIFEST FILE
# ============================================================
# MARKET PULSE DATA
# ============================================================
def generate_market_pulse_data():
    """Generate static JSON for market pulse news."""
    print("\n--- Generating Market Pulse Data ---")

    if not engine_argus:
        print("  ARGUS_FINTEL_DB not set, skipping market pulse")
        return

    try:
        with engine_argus.connect() as conn:
            result = conn.execute(text("""
                SELECT id, title, brief_content, source_name, source_date, url, label, mri, generated_at, lang
                FROM mri_analysis
                WHERE generated_at > NOW() - INTERVAL '7 days'
                ORDER BY generated_at DESC
                LIMIT 50
            """))
            rows = result.fetchall()

        data = []
        for row in rows:
            data.append({
                'id': row[0],
                'title': row[1],
                'brief_content': row[2],
                'source_name': row[3],
                'source_date': row[4],
                'url': row[5],
                'label': row[6],
                'mri': row[7],
                'generated_at': row[8].isoformat() if row[8] else None,
                'lang': row[9]
            })

        save_json('market_pulse.json', {'data': data, 'count': len(data)})
        print(f"  Saved {len(data)} articles")

    except Exception as e:
        print(f"  Error generating market pulse: {e}")


# ============================================================
# EXCHANGE RATE DATA (VCB, BID, TCB — from vn_sbv_centralrate)
# ============================================================
def generate_fxrate_data():
    """Generate static JSON for exchange rates (USD/VND from VCB by default)."""
    print("\n--- Generating Exchange Rate Data ---")

    # Generate for key bank/currency combos
    combos = [
        ('VCB', 'USD'),
        ('VCB', 'EUR'),
        ('VCB', 'JPY'),
    ]

    for bank, currency in combos:
        for period in ['7d', '1m', '1y']:
            date_filter = get_date_filter(period)

            with engine_crawl.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT date, usd_vnd_rate, buy_cash, sell_rate
                    FROM (
                        SELECT DISTINCT ON (date) date, usd_vnd_rate, buy_cash, sell_rate, crawl_time
                        FROM vn_sbv_centralrate
                        WHERE date >= '{date_filter}'
                        AND type = '{currency}'
                        AND bank = '{bank}'
                        AND usd_vnd_rate IS NOT NULL
                        ORDER BY date, crawl_time DESC
                    ) subquery
                    ORDER BY date ASC
                """))
                rows = result.fetchall()

            data = {
                'bank': bank,
                'currency': currency,
                'period': period,
                'count': len(rows),
                'dates': [row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]) for row in rows],
                'usd_vnd_rate': [float(row[1]) if row[1] else 0 for row in rows],
                'buy_cash': [float(row[2]) if row[2] else None for row in rows],
                'sell_rate': [float(row[3]) if row[3] else None for row in rows],
            }

            save_json(f'fxrate_{bank}_{currency}_{period}.json', data)
            print(f"  fxrate_{bank}_{currency}_{period}.json: {len(rows)} rows")


# ============================================================
# GLOBAL MACRO DATA
# ============================================================
def generate_global_data():
    """Generate static JSON for global macro indicators (Gold futures, Silver, NASDAQ)."""
    print("\n--- Generating Global Macro Data ---")

    if not engine_global:
        print("  GLOBAL_INDICATOR_DB not set, skipping global macro")
        return

    try:
        for period in ['7d', '1m', '1y']:
            date_filter = get_date_filter(period)

            with engine_global.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT date, gold_price, silver_price, nasdaq_price
                    FROM (
                        SELECT DISTINCT ON (date) date, gold_price, silver_price, nasdaq_price, crawl_time
                        FROM global_macro
                        WHERE date >= '{date_filter}'
                        ORDER BY date, crawl_time DESC
                    ) subquery
                    ORDER BY date ASC
                """))
                rows = result.fetchall()

            data = {
                'period': period,
                'count': len(rows),
                'dates': [row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]) for row in rows],
                'gold_prices': [float(row[1]) if row[1] else 0 for row in rows],
                'silver_prices': [float(row[2]) if row[2] else 0 for row in rows],
                'nasdaq_prices': [float(row[3]) if row[3] else 0 for row in rows]
            }

            save_json(f'global_{period}.json', data)
            print(f"  global_{period}.json: {len(rows)} rows")

    except Exception as e:
        print(f"  Error generating global macro data: {e}")


# ============================================================
# MANIFEST FILE
# ============================================================
def generate_manifest():
    """Generate manifest file listing all available static data."""
    print("\n--- Generating Manifest ---")

    files = list(STATIC_DIR.glob('*.json'))
    manifest = {
        'generated_at': datetime.now().isoformat(),
        'files': [f.name for f in files if f.name != 'manifest.json'],
        'count': len(files) - 1  # Exclude manifest itself
    }

    save_json('manifest.json', manifest)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("Static Data Generator")
    print(f"Output: {STATIC_DIR}")
    print("=" * 60)

    try:
        generate_gold_data()
        generate_silver_data()
        generate_sbv_data()
        generate_fxrate_data()
        generate_termdepo_data()
        generate_global_data()
        generate_market_pulse_data()
        generate_manifest()

        print("\n" + "=" * 60)
        print(f"Static data generation completed!")
        print(f"Files saved to: {STATIC_DIR}")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
