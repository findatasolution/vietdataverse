"""One-shot repair of 16 SJC rows left wrong by the 75-day freeze bug (2026-09-15).

The freeze bug (CLAUDE.md, "Gold is SJC-only, and the daily row now tracks
intraday moves") pinned each day's stored price to the morning quote from
2026-06-29 to 2026-09-12. The 2026-09-13 correction only covered 2026-08-13
onward; these 16 days, from 2026-06-30 to 2026-08-12, were the part of the
freeze window it never reached.

`crawl_tools/reconcile_sjc.py` found them by comparing each stored value against
SJC's own published history on webgia.com/gia-vang/sjc/DD-MM-YYYY.html — the
same source used for the 2026-09-13 batch. Every row below is `stale`: a real
quote SJC published that day, just not the day's last one, confirmed by the
archive's own per-day adjustment log (2-4 changes per day, each timestamped).

Deliberately NOT included:
  - 2026-08-07 (`carry_forward`) — already correct. SJC's only change that day
    landed at 18:35, after the crawl; the stored value is the previous close,
    which is the right thing to store.
  - 2026-07-08/09/15/16/17 (`unconfirmed`) — the archive lists no change for
    these days and the stored value differs from the previous close. That is
    absence of evidence, not evidence of a wrong row: the archive may simply be
    missing an entry. Left alone until there is stronger evidence either way.

Every value below was read from the archive by hand (via reconcile_sjc.py's
classify(), not guessed or interpolated. Run with --apply to write; default is
a dry run. Every changed row is dumped to a CSV first so the edit can be
reversed.
"""
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv('CRAWLING_BOT_DB')
if not DB_URL:
    sys.exit('CRAWLING_BOT_DB not set')

# date -> (correct_buy, correct_sell), VND/lượng. Source: webgia.com's own
# per-day adjustment log, the closing (last) quote of each day.
CORRECTIONS = {
    '2026-06-30': (144_000_000, 147_000_000),
    '2026-07-07': (147_000_000, 150_000_000),
    '2026-07-14': (144_500_000, 147_500_000),
    '2026-07-20': (143_000_000, 146_000_000),
    '2026-07-22': (142_000_000, 146_000_000),
    '2026-07-24': (135_500_000, 140_500_000),
    '2026-07-29': (137_500_000, 141_500_000),
    '2026-07-30': (137_700_000, 141_700_000),
    '2026-07-31': (137_900_000, 141_900_000),
    '2026-08-03': (137_500_000, 141_000_000),
    '2026-08-04': (137_500_000, 140_500_000),
    '2026-08-05': (138_800_000, 141_800_000),
    '2026-08-06': (139_700_000, 142_700_000),
    '2026-08-10': (141_100_000, 144_100_000),
    '2026-08-11': (140_500_000, 143_500_000),
    '2026-08-12': (141_300_000, 144_300_000),
}


def main():
    apply = '--apply' in sys.argv
    engine = create_engine(DB_URL)
    backup_path = Path(__file__).parent / f"gold_freeze_fix_backup_{datetime.now():%Y%m%d-%H%M%S}.csv"

    with engine.begin() as conn:
        stmt = text("""
            SELECT date, buy_price, sell_price, source, crawl_time
            FROM vn_macro_gold_daily
            WHERE type = 'SJC' AND date IN :dates
            ORDER BY date
        """).bindparams(bindparam('dates', expanding=True))
        rows = conn.execute(stmt, {"dates": list(CORRECTIONS.keys())}).fetchall()

        if len(rows) != len(CORRECTIONS):
            found = {str(r[0]) for r in rows}
            missing = set(CORRECTIONS) - found
            sys.exit(f"expected {len(CORRECTIONS)} rows, found {len(rows)}. "
                     f"Missing: {sorted(missing)}. Aborting — do not guess.")

        with open(backup_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'old_buy_price', 'old_sell_price', 'new_buy_price',
                        'new_sell_price', 'source', 'crawl_time'])
            for date, buy, sell, source, crawl_time in rows:
                new_buy, new_sell = CORRECTIONS[str(date)]
                w.writerow([date, buy, sell, new_buy, new_sell, source, crawl_time])
        print(f"Backup written: {backup_path} ({len(rows)} rows)")

        print(f"\n{'DRY RUN' if not apply else 'APPLYING'} — {len(rows)} rows:")
        for date, buy, sell, source, _ct in rows:
            new_buy, new_sell = CORRECTIONS[str(date)]
            print(f"  {date}  {float(buy)/1e6:.1f}/{float(sell)/1e6:.1f}"
                  f"  ->  {new_buy/1e6:.1f}/{new_sell/1e6:.1f}   ({source})")

        if not apply:
            print("\nDry run only. Re-run with --apply to write.")
            return

        for date, correction in CORRECTIONS.items():
            new_buy, new_sell = correction
            conn.execute(text("""
                UPDATE vn_macro_gold_daily
                SET buy_price = :buy, sell_price = :sell
                WHERE type = 'SJC' AND date = :date
            """), {"buy": new_buy, "sell": new_sell, "date": date})

        print(f"\nApplied {len(CORRECTIONS)} corrections.")


if __name__ == '__main__':
    main()
