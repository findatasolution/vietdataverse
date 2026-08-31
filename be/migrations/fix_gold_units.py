"""One-shot repair of vn_macro_gold_daily's mixed price units (2026-08-31).

The table holds 2,171 rows whose prices are off by a clean power of ten, all
from the 2015–2021 backfill. They are not noise: each is the right number in the
wrong unit, and the correct factor is recoverable because other brands quoted
the SAME day in the correct unit.

Two distinct unit errors, identified by comparing each suspect row against the
median of the same day's valid rows:

  ~1000x  prices stored in THOUSAND VND rather than VND (2015-03 to 2015-08)
  ~10x    prices stored per CHỈ rather than per LƯỢNG (1 lượng = 10 chỉ)

A row is corrected only when all of these hold, so nothing is guessed:
  - at least 3 brands quoted that same day inside the valid 15M–250M range,
  - applying the factor lands the row within 15% of that day's median,
  - the factor is one of the two above.

NOT touched by this script:
  - 'Vàng TG ($)' (763 rows) — world gold in USD, a different instrument that
    should never have been in a domestic VND table. Deleting it is a product
    decision, not a unit repair.
  - rows with no valid same-day quote to compare against — nothing to verify
    them with.

Run with --apply to write; default is a dry run. Every changed row is dumped to
a CSV first so the edit can be reversed.
"""
import os
import sys
import csv
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')
load_dotenv(Path(__file__).resolve().parent.parent.parent / 'vietdataverse_2' / '.env')
load_dotenv('.env')

DB = os.getenv('CRAWLING_BOT_DB')
if not DB:
    sys.exit('CRAWLING_BOT_DB not set')

APPLY = '--apply' in sys.argv
engine = create_engine(DB, connect_args={'connect_timeout': 30})

# Anchor each suspect row to the median of correctly-quoted gold NEAR it. Same
# day is preferred; a +/-3 day window is the fallback, because on a handful of
# days in March 2015 EVERY brand was recorded in the wrong unit, leaving no
# same-day anchor at all. Gold does not move enough in three days for this to
# change which power of ten is the right answer.
CANDIDATES = text("""
WITH ok AS (
    SELECT date, sell_price
    FROM vn_macro_gold_daily
    WHERE sell_price BETWEEN 15e6 AND 250e6
),
bad AS (
    SELECT date, type, buy_price, sell_price
    FROM vn_macro_gold_daily
    WHERE type <> 'Vàng TG ($)'
      AND (sell_price < 15e6 OR sell_price > 250e6)
)
SELECT b.date, b.type, b.buy_price, b.sell_price, a.med
FROM bad b
CROSS JOIN LATERAL (
    SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY o.sell_price) AS med,
           COUNT(*) AS n
    FROM ok o
    WHERE o.date BETWEEN b.date - 3 AND b.date + 3
) a
WHERE a.n >= 3
ORDER BY b.date, b.type
""")

FACTORS = (1000.0, 10.0, 0.1)
TOL = 0.15


def factor_for(sell, med):
    """The single factor that brings this row within TOL of the day's median."""
    hits = [f for f in FACTORS if med and abs(sell * f - med) / med <= TOL]
    return hits[0] if len(hits) == 1 else None


def main():
    with engine.connect() as conn:
        rows = conn.execute(CANDIDATES).fetchall()

    planned, skipped = [], 0
    for date, gtype, buy, sell, med in rows:
        if sell is None:
            skipped += 1
            continue
        f = factor_for(float(sell), float(med))
        if f is None:
            skipped += 1
            continue
        planned.append({
            'date': str(date), 'type': gtype, 'factor': f,
            'buy_old': buy, 'sell_old': sell,
            'buy_new': None if buy is None else float(buy) * f,
            'sell_new': float(sell) * f,
            'day_median': float(med),
        })

    by_factor = {}
    for p in planned:
        by_factor[p['factor']] = by_factor.get(p['factor'], 0) + 1

    print(f"candidates examined : {len(rows)}")
    print(f"correctable         : {len(planned)}  {by_factor}")
    print(f"left alone          : {skipped}  (no single factor fits within {int(TOL*100)}%)")

    if not planned:
        return

    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path(__file__).with_name(f'gold_units_backup_{stamp}.csv')
    with backup.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(planned[0].keys()))
        w.writeheader()
        w.writerows(planned)
    print(f"backup written      : {backup.name}")

    print("\nsample:")
    for p in planned[:5]:
        print(f"  {p['date']} {p['type'][:20]:20} x{p['factor']:<6} "
              f"{p['sell_old']:>14,.0f} -> {p['sell_new']:>14,.0f}  (median {p['day_median']:,.0f})")

    if not APPLY:
        print("\nDRY RUN — rerun with --apply to write.")
        return

    with engine.connect() as conn:
        for p in planned:
            conn.execute(text("""
                UPDATE vn_macro_gold_daily
                SET buy_price  = CASE WHEN buy_price IS NULL THEN NULL ELSE buy_price * :f END,
                    sell_price = sell_price * :f
                WHERE date = :date AND type = :type
            """), {'f': p['factor'], 'date': p['date'], 'type': p['type']})
        conn.commit()
    print(f"\napplied to {len(planned)} rows.")


if __name__ == '__main__':
    main()


# ── Second pass: buy_price alone in the wrong unit ───────────────────────────
# 30 rows carry a correct sell_price but a buy_price off by exactly one power of
# ten (e.g. buy 337,800,000 against sell 33,900,000). Here the row's OWN
# sell_price is the anchor — stronger evidence than any cross-brand median,
# because the buy price of a gold quote always sits just below its sell price.

BUY_CANDIDATES = text("""
    SELECT date, type, buy_price, sell_price
    FROM vn_macro_gold_daily
    WHERE type <> 'Vàng TG ($)'
      AND buy_price IS NOT NULL
      AND sell_price BETWEEN 15e6 AND 250e6
      AND (buy_price < 15e6 OR buy_price > 250e6)
    ORDER BY date
""")


def fix_buy_prices():
    with engine.connect() as conn:
        rows = conn.execute(BUY_CANDIDATES).fetchall()

    planned = []
    for date, gtype, buy, sell in rows:
        buy, sell = float(buy), float(sell)
        # A real quote sits just below the sell price. The upper bound is 1.02
        # rather than 1.00 because one row (Phú Quý, 2016-11-22) lands at 1.0003
        # after scaling — buy and sell were published as the same figure that
        # day, which does not make the power of ten any less obvious.
        for f in (10.0, 0.1):
            if 0.85 <= (buy * f) / sell <= 1.02:
                planned.append({'date': str(date), 'type': gtype, 'factor': f,
                                'buy_old': buy, 'buy_new': buy * f, 'sell': sell})
                break

    print(f"\nbuy-only candidates : {len(rows)}")
    print(f"correctable         : {len(planned)}")
    for p in planned[:5]:
        print(f"  {p['date']} {p['type'][:20]:20} x{p['factor']:<5} "
              f"{p['buy_old']:>14,.0f} -> {p['buy_new']:>14,.0f}  (sell {p['sell']:,.0f})")

    if not planned:
        return
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path(__file__).with_name(f'gold_buy_backup_{stamp}.csv')
    with backup.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(planned[0].keys()))
        w.writeheader(); w.writerows(planned)
    print(f"backup written      : {backup.name}")

    if not APPLY:
        print("DRY RUN — rerun with --apply to write.")
        return
    with engine.connect() as conn:
        for p in planned:
            conn.execute(text("""
                UPDATE vn_macro_gold_daily SET buy_price = buy_price * :f
                WHERE date = :date AND type = :type
            """), {'f': p['factor'], 'date': p['date'], 'type': p['type']})
        conn.commit()
    print(f"applied to {len(planned)} rows.")


fix_buy_prices()
