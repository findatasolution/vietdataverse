"""Watchdog for the fuel pipeline: is the data we SERVE actually current?

Why this exists as a separate step rather than trusting the crawlers' exit codes:
every silent failure this project has had looked like success at the crawler.
The MOIT crawl re-upserted the same row weekly and exited 0 for two months; the
gold crawl discarded correct values at the persistence step and exited 0 for 75
days. An exit code says "the script ran", not "the data moved".

Since 2026-09-19 the box is the only writer -- it crawls MOIT and refits the
model. That removes the duplicate-writer problem but concentrates the risk: if
the box stops, nothing else notices. This check runs on GitHub, off the box, and
is the thing that goes red. Same reasoning as uptime-check.yml being off-box.

Three questions, in the order a reader should care about:
  1. Has a new price cycle failed to appear for longer than the regulator's
     cadence allows?
  2. Has either world-price series stopped advancing?
  3. Did the model actually get recomputed after the newest cycle landed? A
     fresh fuel_price_cycle with a stale fuel_forecast means the box crawled but
     the refit failed -- the API would keep serving forecasts built without the
     newest cycle, and nothing else would report it.

Exit 0 = all clear. Exit 1 = at least one ERROR (printed, most severe first).
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

# The MOIT cadence went 7d -> 14d -> 7d during 2026 alone, so this threshold has
# to tolerate the slowest regime seen plus a missed cycle, or it cries wolf every
# time the regulator changes schedule. 25 days was the old value and it let three
# consecutive weekly cycles go missing; 17 is above the 14-day regime with room.
CYCLE_STALE_DAYS = 17
# Futures trade weekdays: a long weekend plus a holiday is the worst normal gap.
WORLD_STALE_DAYS = 6


def evaluate(latest_cycle, world_newest: dict, forecast_covers_cycle, today):
    """Return (errors, notes). PURE -- no DB, so the judgement is unit-testable.

    latest_cycle: date of the newest row in fuel_price_cycle, or None.
    world_newest: {instrument: newest date or None}.
    forecast_covers_cycle: True if the newest forecast run used the newest cycle.
    """
    errors, notes = [], []

    if latest_cycle is None:
        errors.append("fuel_price_cycle is EMPTY")
    else:
        age = (today - latest_cycle).days
        if age > CYCLE_STALE_DAYS:
            errors.append(
                f"fuel_price_cycle has not advanced in {age} days "
                f"(newest {latest_cycle}, threshold {CYCLE_STALE_DAYS}) -- "
                f"check moit.gov.vn for a moved bulletin, and the box's "
                f"crawl-fuel.service journal")
        else:
            notes.append(f"newest price cycle {latest_cycle} ({age} days old)")

    for instrument, newest in sorted(world_newest.items()):
        if newest is None:
            errors.append(f"fuel_world_daily has no rows for {instrument}")
            continue
        age = (today - newest).days
        if age > WORLD_STALE_DAYS:
            errors.append(f"fuel_world_daily/{instrument} frozen at {newest} "
                          f"({age} days old, threshold {WORLD_STALE_DAYS})")
        else:
            notes.append(f"{instrument} newest {newest} ({age} days old)")

    # Only meaningful once a cycle exists; an empty table already errored above.
    if latest_cycle is not None and not forecast_covers_cycle:
        errors.append(
            "fuel_forecast was not rebuilt after the newest price cycle -- the "
            "API is serving forecasts that do not include it. The box crawled "
            "but the model step failed: check crawl-fuel.service on the box.")
    elif latest_cycle is not None:
        notes.append("forecast includes the newest cycle")

    return errors, notes


def main() -> None:
    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set")

    with create_engine(db_url).connect() as conn:
        latest_cycle = conn.execute(text(
            "SELECT max(period) FROM fuel_price_cycle")).scalar()
        world_newest = dict(conn.execute(text(
            "SELECT instrument, max(period) FROM fuel_world_daily "
            "GROUP BY instrument")).fetchall())
        # The newest forecast run stores the cycle it was built from in its
        # breakdown; comparing that to the newest stored cycle is what catches a
        # crawl that landed without a refit following it.
        last_known = conn.execute(text(
            "SELECT breakdown->>'last_known_cycle' FROM fuel_forecast "
            "ORDER BY run_ts DESC LIMIT 1")).scalar()

    covers = (last_known is not None and latest_cycle is not None
              and str(last_known) == str(latest_cycle))
    errors, notes = evaluate(latest_cycle, world_newest, covers, date.today())

    for n in notes:
        print(f"  ok    {n}")
    for e in errors:
        print(f"  ERROR {e}")
    if errors:
        sys.exit(f"{len(errors)} freshness error(s)")
    print("fuel pipeline freshness: all clear")


if __name__ == "__main__":
    main()
