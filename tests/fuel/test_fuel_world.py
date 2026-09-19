from datetime import date

import crawl_tools.crawl_fuel_world as cw


class _FakeSeries:
    """Minimal stand-in for a pandas Close series: items() of (Timestamp-like, value)."""
    def __init__(self, pairs):
        self._pairs = pairs

    def items(self):
        return iter(self._pairs)


class _TS:
    def __init__(self, d):
        self._d = d

    def date(self):
        return self._d


def test_to_world_rows_maps_and_skips_nan():
    series = _FakeSeries([
        (_TS(date(2026, 7, 9)), 70.5),
        (_TS(date(2026, 7, 10)), float("nan")),
        (_TS(date(2026, 7, 11)), 71.2),
    ])
    rows = cw.to_world_rows(series, "BRENT")
    assert rows == [
        {"period": date(2026, 7, 9), "instrument": "BRENT", "close": 70.5},
        {"period": date(2026, 7, 11), "instrument": "BRENT", "close": 71.2},
    ]


def test_to_world_rows_empty():
    assert cw.to_world_rows(_FakeSeries([]), "RBOB") == []


def test_validate_per_instrument_units():
    assert cw.validate([{"period": date(2026, 7, 9), "instrument": "RBOB", "close": 2.3}])
    assert cw.validate([{"period": date(2026, 7, 9), "instrument": "BRENT", "close": 70.0}])
    # RBOB is USD/gallon — a barrel-scale value must be rejected
    assert not cw.validate([{"period": date(2026, 7, 9), "instrument": "RBOB", "close": 70.0}])
    assert not cw.validate([])


# --- staleness guard (added 2026-09-19) ------------------------------------
# The crawl can write rows, exit 0, and still be frozen: yfinance re-serving an
# unchanged history upserts identical rows forever. Row counts cannot see that;
# only the newest stored date can. Same failure that kept the MOIT crawl green
# for two months.
from datetime import date


def test_fresh_series_reports_nothing():
    today = date(2026, 9, 19)
    assert cw.staleness_report(
        {"BRENT": date(2026, 9, 18), "RBOB": date(2026, 9, 18)}, today) == []


def test_long_weekend_is_not_stale():
    # Fri 2026-09-11 close, checked the following Thu: 5 days, under the threshold.
    assert cw.staleness_report({"BRENT": date(2026, 9, 11)}, date(2026, 9, 16)) == []


def test_frozen_series_is_reported():
    out = cw.staleness_report({"BRENT": date(2026, 9, 1)}, date(2026, 9, 19))
    assert len(out) == 1 and "BRENT" in out[0] and "18 days old" in out[0]


def test_missing_instrument_is_reported():
    out = cw.staleness_report({"BRENT": date(2026, 9, 18), "RBOB": None},
                              date(2026, 9, 19))
    assert out == ["RBOB: no rows at all"]


def test_each_stale_instrument_listed_separately():
    out = cw.staleness_report({"BRENT": date(2026, 8, 1), "RBOB": date(2026, 8, 2)},
                              date(2026, 9, 19))
    assert len(out) == 2
