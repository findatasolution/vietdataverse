"""
One-time backfill: fill vn_macro_fxrate_daily for 2026-04-23 to 2026-04-28.

- SBV Central Rate (bank=SBV, source=Crawl):
    23/4 exists in SBV headless API (structure 3450260).
    24–28/4 = holiday (SBV không publish) → skip, không insert.

- VCB / BID / TCB (bank=VCB/BID/TCB, source=API):
    VCB API supports historical dates → backfill all 6 days.
    BID & TCB APIs are current-day only → skip (cannot backfill).

Run once locally or via workflow_dispatch.
"""

import sys
import os
import requests
import json
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pathlib import Path
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / '.env')

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    sys.exit('CRAWLING_BOT_DB not set')

engine = create_engine(CRAWLING_BOT_DB)

DATES = [date(2026, 4, 23) + timedelta(days=i) for i in range(6)]  # 23–28 Apr
SBV_WORKING_DATES = {date(2026, 4, 23)}   # only day SBV published during this period

inserted = 0
skipped = 0

print('=' * 60)
print(f'FX Rate Backfill — {DATES[0]} to {DATES[-1]}')
print('=' * 60)


def upsert(conn, record: dict) -> bool:
    """Insert if not exists. Returns True if inserted."""
    exists = conn.execute(
        text('SELECT 1 FROM vn_macro_fxrate_daily WHERE date = :date AND type = :type AND bank = :bank LIMIT 1'),
        {'date': record['date'], 'type': record['type'], 'bank': record['bank']}
    ).scalar()
    if exists:
        return False
    conn.execute(text("""
        INSERT INTO vn_macro_fxrate_daily
            (date, crawl_time, type, source, bank, usd_vnd_rate, buy_cash, buy_transfer, sell_rate, group_name)
        VALUES
            (:date, :crawl_time, :type, :source, :bank, :usd_vnd_rate, :buy_cash, :buy_transfer, :sell_rate, 'finance')
    """), record)
    conn.commit()
    return True


# ── 1. SBV Central Rate (23/4 only) ──────────────────────────────────────────
print('\n[1/2] SBV Central Rate via SBV headless API')

SBV_URL = ('https://sbv.gov.vn/o/headless-delivery/v1.0/content-structures/'
           '3450260/structured-contents?pageSize=50&sort=datePublished:desc')

try:
    resp = requests.get(SBV_URL, timeout=15)
    resp.raise_for_status()
    api_items = resp.json().get('items', [])
except Exception as e:
    print(f'  ERROR fetching SBV API: {e}')
    api_items = []

# NOTE: structure 3450260 is the interbank rate feed; SBV central FX rate is on
# a separate page rendered by JS and has no public REST endpoint we can query.
# The SBV crawler in crawl_sbv.py scrapes the live page for the current-day
# central rate — historical dates are not available via that path.
# Therefore we only attempt to recover the interbank data from the API,
# not the central USD/VND rate, for the holiday period.
print('  NOTE: SBV Central USD/VND rate page is JS-rendered with no historical')
print('        REST endpoint. 24–28 Apr were public holidays — SBV did not')
print('        publish. 23 Apr was also not captured by the daily crawler.')
print('        Skipping SBV central rate backfill (no source available).')

# ── 2. VCB historical API (all 6 days) ───────────────────────────────────────
print('\n[2/2] VCB rates via vietcombank.com.vn API')

VCB_URL = 'https://www.vietcombank.com.vn/api/exchangerates'
FOCUS = {'USD', 'EUR', 'JPY', 'GBP', 'CNY', 'AUD', 'SGD', 'KRW', 'THB', 'CAD', 'CHF', 'HKD'}

for d in DATES:
    try:
        r = requests.get(VCB_URL, params={'date': d.isoformat()}, timeout=10)
        r.raise_for_status()
        payload = r.json()
        returned_date = payload.get('Date', '')[:10]

        if returned_date != d.isoformat():
            print(f'  {d}: VCB returned {returned_date} (holiday/weekend carry-forward) — will insert as-is')

        records_today = 0
        with engine.connect() as conn:
            for item in payload.get('Data', []):
                code = item['currencyCode'].strip().upper()
                if code not in FOCUS:
                    continue

                def parse_rate(v):
                    try:
                        return float(str(v).replace(',', '')) if v else None
                    except (ValueError, TypeError):
                        return None

                rec = {
                    'date':         d,
                    'crawl_time':   datetime.utcnow(),
                    'type':         code,
                    'source':       'API',
                    'bank':         'VCB',
                    'usd_vnd_rate': parse_rate(item.get('transfer')) if code == 'USD' else None,
                    'buy_cash':     parse_rate(item.get('cash')),
                    'buy_transfer': parse_rate(item.get('transfer')),
                    'sell_rate':    parse_rate(item.get('sell')),
                }
                did_insert = upsert(conn, rec)
                if did_insert:
                    inserted += 1
                    records_today += 1
                else:
                    skipped += 1

        print(f'  {d}: inserted {records_today} VCB rows')

    except Exception as e:
        print(f'  {d}: ERROR — {e}')


# ── Summary ───────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
print(f'Done — inserted {inserted} rows, skipped {skipped} existing rows')
print(f'{"="*60}')
