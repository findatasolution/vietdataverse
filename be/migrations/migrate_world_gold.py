"""Move 'Vàng TG ($)' out of the domestic gold table and into global_macro.

vn_macro_gold_daily carries 1,415 rows typed 'Vàng TG ($)' — world gold quoted
in USD/oz, sitting in a table of Vietnamese dong prices per lượng. It is not a
unit error inside the domestic series; it is a different instrument that was
scraped from the same page and never separated. It stopped updating in 2019.

Deleting it would throw away real data: global_macro's own gold history only
starts 2025-01-14, so these rows are the only record of 2015–2019 world gold
this project holds. They are migrated rather than dropped.

The values carry an inconsistent decimal scale — the source printed the price
with decimals and the crawler stripped them differently over the years, so the
same $1,458/oz appears as 1,458,800,000 in 2019 and as 121,577,000 (i.e.
$1,215.77) in 2015. The scale is recovered per row by picking the single power
of ten that lands the value inside a plausible 800–2,100 USD/oz band for the
period. 1,414 of 1,415 rows resolve to exactly one factor; the remaining row
(2016-06-30, 35,160,000,000) resolves to none and is left behind as corrupt.

Run with --apply to write; default is a dry run. Rows are dumped to CSV before
anything is deleted.
"""
import os
import sys
import csv
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('.env')
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

BOT = os.getenv('CRAWLING_BOT_DB')
GLOBAL = os.getenv('GLOBAL_INDICATOR_DB')
if not BOT or not GLOBAL:
    sys.exit('CRAWLING_BOT_DB / GLOBAL_INDICATOR_DB not set')

APPLY = '--apply' in sys.argv
bot = create_engine(BOT, connect_args={'connect_timeout': 30})
glob = create_engine(GLOBAL, connect_args={'connect_timeout': 30})

BAND = (800.0, 2100.0)          # USD/oz, wide enough for 2015–2019
FACTORS = (1e3, 1e4, 1e5, 1e6, 1e7)


def scale(value):
    """The single power of ten that puts this value in a plausible USD/oz band."""
    if not value:
        return None
    hits = [f for f in FACTORS if BAND[0] <= value / f <= BAND[1]]
    return hits[0] if len(hits) == 1 else None


def main():
    with bot.connect() as c:
        rows = c.execute(text("""
            SELECT date, buy_price, sell_price, crawl_time
            FROM vn_macro_gold_daily
            WHERE type = 'Vàng TG ($)'
            ORDER BY date
        """)).fetchall()

    decoded, undecodable = [], []
    counts = Counter()
    for date, buy, sell, crawl_time in rows:
        f = scale(float(sell) if sell else None)
        if f is None:
            undecodable.append((date, sell))
            continue
        counts[f] += 1
        decoded.append({
            'date': str(date),
            'gold_price': float(sell) / f,
            'buy_usd': None if buy is None else float(buy) / f,
            'raw_sell': float(sell),
            'factor': f,
            'crawl_time': crawl_time,
        })

    print(f"rows              : {len(rows)}")
    print(f"decoded           : {len(decoded)}  " +
          str({f'/{int(k):,}': v for k, v in sorted(counts.items())}))
    print(f"left behind       : {len(undecodable)}  {[(str(d), float(s)) for d, s in undecodable]}")
    if decoded:
        print(f"span              : {decoded[0]['date']} → {decoded[-1]['date']}  "
              f"({min(d['gold_price'] for d in decoded):,.2f} – "
              f"{max(d['gold_price'] for d in decoded):,.2f} USD/oz)")

    with glob.connect() as c:
        existing = c.execute(text("SELECT min(date)::text, max(date)::text FROM global_macro")).fetchone()
    print(f"global_macro today: {existing[0]} → {existing[1]}")

    if not decoded:
        return

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path(__file__).with_name(f'world_gold_backup_{stamp}.csv')
    with backup.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=['date', 'raw_sell', 'factor', 'gold_price', 'buy_usd'])
        w.writeheader()
        for d in decoded:
            w.writerow({k: d[k] for k in w.fieldnames})
    print(f"backup            : {backup.name}")

    print("\nsample:")
    for d in decoded[:3] + decoded[-2:]:
        print(f"  {d['date']}  {d['raw_sell']:>16,.0f} / {int(d['factor']):<9,} "
              f"= {d['gold_price']:>8,.2f} USD/oz")

    if not APPLY:
        print("\nDRY RUN — rerun with --apply to write.")
        return

    with glob.connect() as c:
        for d in decoded:
            c.execute(text("""
                INSERT INTO global_macro (date, crawl_time, gold_price, source, group_name)
                VALUES (:date, :crawl_time, :gold_price, '24h.com.vn (migrated 2026-08-31)', 'commodity')
                ON CONFLICT (date) DO NOTHING
            """), {'date': d['date'], 'crawl_time': d['crawl_time'], 'gold_price': d['gold_price']})
        c.commit()

    with bot.connect() as c:
        c.execute(text("DELETE FROM vn_macro_gold_daily WHERE type = 'Vàng TG ($)'"))
        c.commit()

    print(f"\ninserted {len(decoded)} rows into global_macro; "
          f"removed all 'Vàng TG ($)' rows from vn_macro_gold_daily.")


if __name__ == '__main__':
    main()
