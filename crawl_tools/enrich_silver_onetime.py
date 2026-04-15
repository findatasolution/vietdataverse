"""
ONE-TIME SCRIPT: Backfill historical silver prices from exchange-rates.org
Source: https://www.exchange-rates.org/vn/kim-loai-quy/bac/viet-nam/{year}
Unit: VND per lượng (giá spot quốc tế quy đổi VND)

Flag: source = 'exchange-rates.org'  ← dùng để xóa toàn bộ nếu cần:
  DELETE FROM vn_macro_silver_daily WHERE source = 'exchange-rates.org';

Chạy 1 lần rồi xóa file này.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

SOURCE = 'exchange-rates.org'
BASE_URL = 'https://www.exchange-rates.org/vn/kim-loai-quy/bac/viet-nam/{year}'
START_YEAR = 2010
END_YEAR = datetime.now().year

_http = requests.Session()
_http.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})

engine = create_engine(os.getenv('CRAWLING_BOT_DB'))

# Vietnamese month names → month number
_MONTH_MAP = {
    'tháng 1': 1, 'thg 1': 1,
    'tháng 2': 2, 'thg 2': 2,
    'tháng 3': 3, 'thg 3': 3,
    'tháng 4': 4, 'thg 4': 4,
    'tháng 5': 5, 'thg 5': 5,
    'tháng 6': 6, 'thg 6': 6,
    'tháng 7': 7, 'thg 7': 7,
    'tháng 8': 8, 'thg 8': 8,
    'tháng 9': 9, 'thg 9': 9,
    'tháng 10': 10, 'thg 10': 10,
    'tháng 11': 11, 'thg 11': 11,
    'tháng 12': 12, 'thg 12': 12,
}


def _parse_price(text: str) -> float | None:
    """Parse '500.343₫' or '1.234.567₫' → float VND."""
    text = text.replace('₫', '').replace('\xa0', '').strip()
    # Remove thousands separators (dots before 3-digit groups)
    text = re.sub(r'\.(?=\d{3}(?:\.|$))', '', text)
    text = text.replace(',', '.')
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text)
    except ValueError:
        return None


def crawl_year(year: int) -> list[dict]:
    """Fetch one year page and return list of {date, price}."""
    url = BASE_URL.format(year=year)
    try:
        r = _http.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  [{year}] Fetch error: {e}")
        return []

    soup = BeautifulSoup(r.content, 'html.parser')
    table = soup.find('table')
    if not table:
        print(f"  [{year}] No table found")
        return []

    rows = table.find_all('tr')
    records = []
    current_month = None

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if not cells:
            continue

        text0 = cells[0].get_text(strip=True).lower()

        # Detect month header row (e.g. "Tháng 1 2020")
        for m_key, m_num in _MONTH_MAP.items():
            if m_key in text0:
                current_month = m_num
                break

        if current_month is None or len(cells) < 2:
            continue

        # Day row: "1 thg 1" or "15 thg 3"
        # Extract day number from first cell
        day_match = re.match(r'^(\d{1,2})\s', text0)
        if not day_match:
            continue
        day = int(day_match.group(1))

        price = _parse_price(cells[1].get_text(strip=True))
        if price is None or price <= 0:
            continue

        try:
            d = date(year, current_month, day)
            records.append({'date': d, 'price': price})
        except ValueError:
            continue

    return records


def main():
    print(f"\n{'='*60}")
    print(f"Silver Backfill — exchange-rates.org — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Source flag: '{SOURCE}'  (DELETE WHERE source='{SOURCE}' to remove all)")
    print(f"Years: {START_YEAR} → {END_YEAR}")
    print(f"{'='*60}")

    # Get existing dates (all sources) to avoid duplicates on same date
    with engine.connect() as conn:
        existing = {r[0] for r in conn.execute(
            text("SELECT DISTINCT date FROM vn_macro_silver_daily")
        ).fetchall()}
    print(f"Existing dates in DB: {len(existing)}")

    total_inserted = 0
    total_skipped = 0
    crawl_time = datetime.now()

    for year in range(START_YEAR, END_YEAR + 1):
        records = crawl_year(year)
        if not records:
            print(f"  [{year}] 0 records")
            time.sleep(1)
            continue

        new_records = [r for r in records if r['date'] not in existing]
        skipped = len(records) - len(new_records)

        if new_records:
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO vn_macro_silver_daily
                        (date, crawl_time, buy_price, sell_price, source)
                    SELECT r.date, :crawl_time, r.price, r.price, :source
                    FROM (VALUES {values}) AS r(date, price)
                """.format(values=', '.join(
                    f"('{r['date']}'::date, {r['price']})"
                    for r in new_records
                ))), {'crawl_time': crawl_time, 'source': SOURCE})
                conn.commit()

            # Update existing set for subsequent years (avoid cross-year dupes)
            for r in new_records:
                existing.add(r['date'])

        total_inserted += len(new_records)
        total_skipped += skipped
        print(f"  [{year}] {len(records)} rows fetched → inserted={len(new_records)}, skipped={skipped}")
        time.sleep(1.5)  # polite crawl

    print(f"\n{'='*60}")
    print(f"Done. Total inserted: {total_inserted}, skipped: {total_skipped}")

    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM vn_macro_silver_daily"
        )).fetchone()
        r2 = conn.execute(text(
            "SELECT source, COUNT(*) FROM vn_macro_silver_daily GROUP BY source ORDER BY source"
        )).fetchall()
    print(f"DB total: {r[0]} rows, {r[1]} → {r[2]}")
    print("By source:")
    for row in r2:
        print(f"  {row[0]}: {row[1]} rows")
    print(f"\nTo remove this data: DELETE FROM vn_macro_silver_daily WHERE source = '{SOURCE}';")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
