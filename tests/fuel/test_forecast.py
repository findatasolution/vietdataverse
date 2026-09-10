"""Test suite for be.fuel.forecast — cycle-point builder and world-conditional
scenario forecast generator.

structural-v1's Brent-fed make_forecast_rows was removed 2026-09-10; forecasts are
now delta-world-v1 scenarios with no Brent/RBOB dependency (see forecast.py
docstring for why).
"""
import pytest
from datetime import date, datetime, timedelta
from be.fuel.forecast import (
    build_cycle_points,
    make_forecast_rows,
    MODEL_VERSION,
    METHODOLOGY_VERSION,
    CYCLE_DAYS,
    DISCLAIMER,
)
from be.fuel.calibration import CyclePoint


class TestBuildCyclePoints:
    def test_basic_two_cycles_creates_two_points(self):
        """Two cycles for one fuel create two CyclePoints (no boundary cycle needed
        now — the delta model uses consecutive points directly, unlike the removed
        Brent-window approach)."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
        ]
        points_by_fuel = build_cycle_points(cycles)
        assert "RON95" in points_by_fuel
        assert len(points_by_fuel["RON95"]) == 2
        assert points_by_fuel["RON95"][0].period == date(2026, 1, 1)
        assert points_by_fuel["RON95"][1].period == date(2026, 1, 8)
        assert points_by_fuel["RON95"][1].world_avg == 75.0
        assert points_by_fuel["RON95"][1].retail == 18500.0

    def test_single_cycle_excluded(self):
        """A fuel with only 1 cycle has no delta and is excluded."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
        ]
        points_by_fuel = build_cycle_points(cycles)
        assert "RON95" not in points_by_fuel

    def test_multiple_fuels_tracked_separately(self):
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
            {"period": date(2026, 1, 1), "fuel": "E5RON92", "world_avg_price": 68.0, "retail_price": 17500.0},
            {"period": date(2026, 1, 8), "fuel": "E5RON92", "world_avg_price": 72.0, "retail_price": 18000.0},
        ]
        points_by_fuel = build_cycle_points(cycles)
        assert set(points_by_fuel.keys()) == {"RON95", "E5RON92"}
        assert len(points_by_fuel["RON95"]) == 2
        assert len(points_by_fuel["E5RON92"]) == 2

    def test_points_sorted_by_period(self):
        """Cycles given out of order are sorted before building points."""
        cycles = [
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
        ]
        points_by_fuel = build_cycle_points(cycles)
        periods = [p.period for p in points_by_fuel["RON95"]]
        assert periods == sorted(periods)


def _points(fuel, worlds, retails, start=date(2026, 1, 1), step_days=7):
    return [
        CyclePoint(period=date.fromordinal(start.toordinal() + i * step_days),
                   fuel=fuel, world_avg=w, retail=r)
        for i, (w, r) in enumerate(zip(worlds, retails))
    ]


class TestMakeForecastRows:
    def test_basic_forecast_structure(self):
        points = _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                         [18000.0, 18500.0, 19000.0, 19500.0, 20000.0])
        points_by_fuel = {"RON95": points}
        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, run_ts, horizons=4)

        # 1 fuel * 4 horizons * 3 scenarios
        assert len(rows) == 1 * 4 * 3

        row = rows[0]
        assert row["run_ts"] == run_ts
        assert row["fuel"] == "RON95"
        assert row["scenario"] in ("low", "base", "high")
        assert isinstance(row["point"], int)
        assert isinstance(row["lo"], int)
        assert isinstance(row["hi"], int)
        assert row["model_version"] == MODEL_VERSION
        assert row["methodology_version"] == METHODOLOGY_VERSION

    def test_base_scenario_equals_last_retail_no_change(self):
        """base scenario assumes zero Δworld → point == last known retail."""
        points = _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                         [18000.0, 18500.0, 19000.0, 19500.0, 20000.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=1)
        base_row = next(r for r in rows if r["scenario"] == "base")
        assert base_row["point"] == 20000

    def test_low_high_symmetric_around_base(self):
        points = _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                         [18000.0, 18500.0, 19000.0, 19500.0, 20000.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=1)
        by_scenario = {r["scenario"]: r["point"] for r in rows}
        base = by_scenario["base"]
        assert (by_scenario["high"] - base) == (base - by_scenario["low"])

    def test_horizon_target_cycle_increments(self):
        points = _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                         [18000.0, 18500.0, 19000.0, 19500.0, 20000.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=3)
        base_rows = sorted((r for r in rows if r["scenario"] == "base"), key=lambda r: r["horizon"])
        last_period = points[-1].period
        for h, row in enumerate(base_rows, start=1):
            assert row["horizon"] == h
            assert row["target_cycle"] == last_period + timedelta(days=h * CYCLE_DAYS)

    def test_scenario_spread_grows_with_horizon(self):
        """world_shift scales with sqrt(h), so horizon 4's spread > horizon 1's."""
        points = _points("RON95", [67.0, 72.0, 68.0, 80.0, 74.0, 90.0],
                         [18000.0, 18500.0, 18200.0, 19500.0, 18900.0, 20500.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=4)
        spread_by_h = {}
        for h in (1, 4):
            h_rows = [r for r in rows if r["horizon"] == h]
            spread_by_h[h] = h_rows[0]["hi"] - h_rows[0]["lo"]
        assert spread_by_h[4] > spread_by_h[1]

    def test_breakdown_includes_required_keys(self):
        points = _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                         [18000.0, 18500.0, 19000.0, 19500.0, 20000.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=1)
        breakdown = rows[0]["breakdown"]
        for key in ("k_vnd_per_usd_bbl", "assumed_world_delta_usd_bbl", "resid_std_vnd_l",
                    "sigma_world_usd_bbl", "last_known_cycle", "last_known_retail", "disclaimer"):
            assert key in breakdown
        assert breakdown["disclaimer"] == DISCLAIMER

    def test_fewer_than_4_points_skipped(self):
        points = _points("RON95", [67.0, 72.0], [18000.0, 18500.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=1)
        assert len(rows) == 0

    def test_zero_world_variance_skipped(self):
        """fit_passthrough raises on zero Δworld variance → fuel silently skipped,
        not a crash."""
        points = _points("RON95", [70.0, 70.0, 70.0, 70.0, 70.0],
                         [18000.0, 18100.0, 18000.0, 18100.0, 18000.0])
        rows = make_forecast_rows({"RON95": points}, datetime(2026, 2, 6), horizons=1)
        assert rows == []

    def test_multiple_fuels_mixed_point_counts(self):
        points_by_fuel = {
            "RON95": _points("RON95", [67.0, 72.0, 76.0, 80.0, 84.0],
                             [18000.0, 18500.0, 19000.0, 19500.0, 20000.0]),
            "E5RON92": _points("E5RON92", [65.0, 70.0], [17500.0, 18000.0]),  # skipped, <4
            "DO005S": _points("DO005S", [62.0, 67.0, 72.0, 76.0],
                              [17000.0, 17500.0, 18000.0, 18500.0]),
        }
        rows = make_forecast_rows(points_by_fuel, datetime(2026, 2, 6), horizons=2)
        fuels_in_rows = {r["fuel"] for r in rows}
        assert fuels_in_rows == {"RON95", "DO005S"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
