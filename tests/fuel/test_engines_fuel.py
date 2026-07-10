import pytest

from be.core import engines


def test_get_engine_fuel_requires_env(monkeypatch):
    monkeypatch.delenv("FUEL_FORECAST_DB", raising=False)
    engines._engine_fuel = None
    with pytest.raises(Exception):
        engines.get_engine_fuel()
