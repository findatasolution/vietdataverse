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
