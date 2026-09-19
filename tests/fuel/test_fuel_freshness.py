"""The watchdog's judgement, exercised without a DB.

Each case here is a failure this project actually had, or the false alarm that
would make the watchdog get ignored -- which is how the last DQ report ended up
unread (CLAUDE.md, "The DQ agent's findings were invisible").
"""
from datetime import date

from crawl_tools.check_fuel_freshness import evaluate

TODAY = date(2026, 9, 19)
FRESH_WORLD = {"BRENT": date(2026, 9, 18), "RBOB": date(2026, 9, 18)}


def test_everything_current_is_clean():
    errors, notes = evaluate(date(2026, 9, 17), FRESH_WORLD, True, TODAY)
    assert errors == []
    assert len(notes) == 4  # cycle + 2 instruments + forecast coverage


def test_a_fortnight_gap_is_not_an_error():
    # The regulator ran a ~14-day cadence through mid-2026. Firing here would
    # train everyone to ignore this check.
    errors, _ = evaluate(date(2026, 9, 5), FRESH_WORLD, True, TODAY)
    assert errors == []


def test_three_missed_weekly_cycles_is_an_error():
    # The real 2026-09 incident: 09-03, 09-10 and 09-17 all missed while CI
    # stayed green, because the old threshold was 25 days.
    errors, _ = evaluate(date(2026, 8, 27), FRESH_WORLD, True, TODAY)
    assert len(errors) == 1 and "has not advanced in 23 days" in errors[0]


def test_empty_cycle_table_is_an_error():
    errors, _ = evaluate(None, FRESH_WORLD, True, TODAY)
    assert any("EMPTY" in e for e in errors)


def test_frozen_world_series_is_an_error():
    errors, _ = evaluate(date(2026, 9, 17),
                         {"BRENT": date(2026, 9, 1), "RBOB": date(2026, 9, 18)},
                         True, TODAY)
    assert len(errors) == 1 and "BRENT frozen at 2026-09-01" in errors[0]


def test_long_weekend_in_world_series_is_not_an_error():
    errors, _ = evaluate(date(2026, 9, 17),
                         {"BRENT": date(2026, 9, 14), "RBOB": date(2026, 9, 14)},
                         True, TODAY)
    assert errors == []


def test_missing_instrument_is_an_error():
    errors, _ = evaluate(date(2026, 9, 17),
                         {"BRENT": date(2026, 9, 18), "RBOB": None}, True, TODAY)
    assert any("no rows for RBOB" in e for e in errors)


def test_fresh_cycle_but_stale_forecast_is_an_error():
    # The box crawled the new cycle and the model step then failed. Data looks
    # perfectly fresh; the API is serving forecasts that predate the newest
    # cycle. Nothing but this check would report it.
    errors, _ = evaluate(date(2026, 9, 17), FRESH_WORLD, False, TODAY)
    assert len(errors) == 1 and "not rebuilt" in errors[0]


def test_forecast_coverage_not_reported_when_table_is_empty():
    # An empty fuel_price_cycle already errors; adding "forecast not rebuilt"
    # on top is noise pointing at the wrong component.
    errors, _ = evaluate(None, FRESH_WORLD, False, TODAY)
    assert len(errors) == 1 and "EMPTY" in errors[0]


def test_errors_accumulate_across_independent_failures():
    errors, _ = evaluate(date(2026, 8, 1),
                         {"BRENT": date(2026, 8, 1), "RBOB": None}, False, TODAY)
    assert len(errors) == 4
