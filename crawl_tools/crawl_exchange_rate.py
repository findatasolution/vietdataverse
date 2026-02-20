"""
Exchange Rate Crawler (Multi-source)
Schedule: Daily 10:00 AM VN

Sources:
1. VCB (Vietcombank) - Primary, supports historical dates
   API: https://www.vietcombank.com.vn/api/exchangerates?date=YYYY-MM-DD
   No auth required. Returns 20 currencies with cash/transfer/sell rates.

2. BID (BIDV) & TCB (Techcombank) - via VNAppMob API
   API: https://api.vnappmob.com/api/v2/exchange_rate/{bank}
   Requires bearer token (auto-requested, expires 15 days).
   Current-day only (date param ignored).

Stores into vn_sbv_centralrate table with source='API', bank=VCB/BID/TCB.
First run backfills VCB historical data (1 year).
Subsequent runs only insert today's data.

Prices are in VND per unit of foreign currency.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

import requests
import json
import time
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

current_date = datetime.now()
date_str = current_date.strftime('%Y-%m-%d')

print(f"\n{'='*60}")
print(f"Exchange Rate Crawler - {date_str} {current_date.strftime('%H:%M')}")
print(f"{'='*60}")

# Database connection
CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
engine = create_engine(CRAWLING_BOT_DB)

# VNAppMob API config
VNAPPMOB_BASE = 'https://api.vnappmob.com'
VNAPPMOB_KEY_URL = f'{VNAPPMOB_BASE}/api/request_api_key?scope=exchange_rate'

# VCB API config
VCB_API_URL = 'https://www.vietcombank.com.vn/api/exchangerates'

# Focus currencies (skip exotic/low-volume ones)
FOCUS_CURRENCIES = {'USD', 'EUR', 'JPY', 'GBP', 'CNY', 'AUD', 'SGD', 'KRW', 'THB', 'CAD', 'CHF', 'HKD', 'NZD', 'TWD', 'MYR'}

# Historical backfill: 1 year of daily data
BACKFILL_DAYS = 365


############## HELPER FUNCTIONS

def get_vnappmob_key():
    """Request a fresh API key from VNAppMob (valid 15 days)."""
    try:
        resp = requests.get(VNAPPMOB_KEY_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        key = data.get('results', '')
        if key:
            print(f"  Got VNAppMob API key")
            return key
        return None
    except Exception as e:
        print(f"  Failed to get VNAppMob key: {e}")
        return None


def normalize_currency(raw_currency):
    """Normalize currency codes: 'USD (50,100)' -> 'USD'."""
    return raw_currency.strip().split('(')[0].split(' ')[0].upper()


def insert_record(record):
    """Insert a single exchange rate record with dedup check. Returns True if inserted."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM vn_sbv_centralrate WHERE date = :date AND type = :type AND bank = :bank"),
            {'date': record['date'], 'type': record['type'], 'bank': record['bank']}
        )
        if result.scalar() > 0:
            return False

        conn.execute(
            text("""
                INSERT INTO vn_sbv_centralrate
                    (date, crawl_time, type, source, bank, usd_vnd_rate, buy_cash, buy_transfer, sell_rate)
                VALUES
                    (:date, :crawl_time, :type, :source, :bank, :usd_vnd_rate, :buy_cash, :buy_transfer, :sell_rate)
            """),
            record
        )
        conn.commit()
        return True


############## VCB CRAWLER (supports historical dates)

def fetch_vcb_rates(target_date):
    """Fetch VCB exchange rates for a specific date. Returns list of records."""
    date_param = target_date.strftime('%Y-%m-%d')
    try:
        resp = requests.get(VCB_API_URL, params={'date': date_param}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return []

    records = []
    api_date = data.get('Date', date_param)
    # Parse API date: "2026-02-17T00:00:00"
    try:
        actual_date = datetime.strptime(api_date[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        actual_date = date_param

    for item in data.get('Data', []):
        currency = item.get('currencyCode', '').strip().upper()
        if currency not in FOCUS_CURRENCIES:
            continue

        try:
            cash = float(item.get('cash', '0').replace(',', '')) if item.get('cash') else None
            transfer = float(item.get('transfer', '0').replace(',', '')) if item.get('transfer') else None
            sell = float(item.get('sell', '0').replace(',', '')) if item.get('sell') else None
        except (ValueError, TypeError):
            continue

        if not transfer and not sell:
            continue

        records.append({
            'date': actual_date,
            'crawl_time': current_date,
            'type': currency,
            'source': 'API',
            'bank': 'VCB',
            'buy_cash': cash,
            'buy_transfer': transfer,
            'sell_rate': sell,
            'usd_vnd_rate': transfer if currency == 'USD' else None,
        })

    return records


def crawl_vcb_historical():
    """Backfill VCB historical exchange rates (weekdays only, 1 year)."""
    print(f"\n--- VCB Historical Backfill ---")

    # Check how many VCB records already exist
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(DISTINCT date) FROM vn_sbv_centralrate WHERE bank = 'VCB'"))
        existing_days = result.scalar()

    if existing_days >= 200:
        print(f"  Already have {existing_days} days of VCB data, skipping backfill")
        return

    print(f"  Have {existing_days} days, backfilling up to {BACKFILL_DAYS} days...")
    total_inserted = 0
    total_skipped = 0
    errors = 0

    for days_ago in range(0, BACKFILL_DAYS):
        target = current_date - timedelta(days=days_ago)
        # Skip weekends (no trading)
        if target.weekday() >= 5:
            continue

        records = fetch_vcb_rates(target)
        if not records:
            errors += 1
            if errors > 10:
                print(f"  Too many consecutive errors, stopping backfill")
                break
            continue
        errors = 0  # reset error counter on success

        day_inserted = 0
        for record in records:
            if insert_record(record):
                day_inserted += 1
                total_inserted += 1
            else:
                total_skipped += 1

        if days_ago % 30 == 0 and days_ago > 0:
            print(f"  ... {days_ago} days back, {total_inserted} inserted so far")

        # Rate limit: ~0.3s between requests
        time.sleep(0.3)

    print(f"  VCB Backfill: {total_inserted} inserted, {total_skipped} skipped (duplicates)")


def crawl_vcb_today():
    """Crawl today's VCB exchange rates."""
    print(f"\n--- Crawling VCB Exchange Rates (today) ---")
    records = fetch_vcb_rates(current_date)
    if not records:
        print(f"  No data from VCB")
        return

    inserted = 0
    skipped = 0
    for record in records:
        if insert_record(record):
            inserted += 1
        else:
            skipped += 1

    print(f"  VCB: {inserted} inserted, {skipped} skipped ({len(records)} currencies)")


############## VNAPPMOB CRAWLER (BID, TCB - current day only)

def crawl_vnappmob():
    """Crawl BID and TCB rates from VNAppMob API."""
    print(f"\n--- Fetching VNAppMob API key ---")
    api_key = get_vnappmob_key()
    if not api_key:
        print("  Cannot get API key, skipping BID/TCB")
        return

    for bank_code in ['bid', 'tcb']:
        print(f"\n--- Crawling {bank_code.upper()} Exchange Rates ---")
        try:
            url = f'{VNAPPMOB_BASE}/api/v2/exchange_rate/{bank_code}'
            headers = {'Authorization': f'Bearer {api_key}'}
            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 403:
                print(f"  Key expired, refreshing...")
                api_key = get_vnappmob_key()
                if not api_key:
                    continue
                resp = requests.get(url, headers={'Authorization': f'Bearer {api_key}'}, timeout=15)

            resp.raise_for_status()
            results = resp.json().get('results', [])

            if not results:
                print(f"  No data from {bank_code.upper()}")
                continue

            # Parse and dedup by currency (keep highest buy_transfer)
            seen = {}
            for item in results:
                currency = normalize_currency(item.get('currency', ''))
                if currency not in FOCUS_CURRENCIES:
                    continue

                buy_cash = item.get('buy_cash', 0) or 0
                buy_transfer = item.get('buy_transfer', 0) or 0
                sell = item.get('sell', 0) or 0

                if currency in seen and (buy_transfer or 0) <= (seen[currency].get('buy_transfer') or 0):
                    continue

                seen[currency] = {
                    'date': date_str,
                    'crawl_time': current_date,
                    'type': currency,
                    'source': 'API',
                    'bank': bank_code.upper(),
                    'buy_cash': buy_cash if buy_cash > 0 else None,
                    'buy_transfer': buy_transfer if buy_transfer > 0 else None,
                    'sell_rate': sell if sell > 0 else None,
                    'usd_vnd_rate': buy_transfer if currency == 'USD' and buy_transfer > 0 else None,
                }

            inserted = 0
            skipped = 0
            for record in seen.values():
                if insert_record(record):
                    inserted += 1
                else:
                    skipped += 1

            print(f"  {bank_code.upper()}: {inserted} inserted, {skipped} skipped ({len(seen)} currencies)")

        except Exception as e:
            print(f"  Error crawling {bank_code.upper()}: {e}")


############## ENSURE TABLE EXISTS + MIGRATE SCHEMA
print(f"\n--- Ensuring table schema ---")
try:
    with engine.connect() as conn:
        # Create table if it doesn't exist yet
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_sbv_centralrate (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                crawl_time TIMESTAMP NOT NULL,
                type VARCHAR(20) NOT NULL DEFAULT 'USD',
                source VARCHAR(20) NOT NULL DEFAULT 'Crawl',
                bank VARCHAR(10) DEFAULT 'SBV',
                usd_vnd_rate FLOAT,
                buy_cash FLOAT,
                buy_transfer FLOAT,
                sell_rate FLOAT,
                document_no VARCHAR(50)
            )
        """))
        conn.commit()

        # Add missing columns if the table was created by an older schema
        for col, definition in [
            ('type',         "VARCHAR(20) NOT NULL DEFAULT 'USD'"),
            ('source',       "VARCHAR(20) NOT NULL DEFAULT 'Crawl'"),
            ('bank',         "VARCHAR(10) DEFAULT 'SBV'"),
            ('buy_transfer', 'FLOAT'),
            ('buy_cash',     'FLOAT'),
            ('sell_rate',    'FLOAT'),
            ('document_no',  'VARCHAR(50)'),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn_sbv_centralrate ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()

        # Add unique constraint if not present (ignore if already exists)
        try:
            conn.execute(text("""
                ALTER TABLE vn_sbv_centralrate
                ADD CONSTRAINT vn_sbv_centralrate_date_type_source_bank_key
                UNIQUE (date, type, source, bank)
            """))
            conn.commit()
        except Exception:
            conn.rollback()  # constraint already exists

    print(f"  Table vn_sbv_centralrate ready")
except Exception as e:
    print(f"  Table check error: {e}")


############## RUN CRAWLERS

# 1. VCB: historical backfill (first run) + today
crawl_vcb_historical()
crawl_vcb_today()

# 2. BID & TCB: today only
crawl_vnappmob()


print(f"\n{'='*60}")
print(f"Exchange Rate Crawler completed at {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*60}")
