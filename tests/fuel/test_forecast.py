"""Test suite for be.fuel.forecast — cycle-point builder and forecast generator.

Tests focus on the two PURE functions (no DB I/O):
1. build_cycle_points: converts cycles + brent_daily into CyclePoint observations
2. make_forecast_rows: generates forecast rows from calibrated models
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
    """Test build_cycle_points function."""

    def test_basic_two_cycles_creates_one_point(self):
        """Two cycles for one fuel create one CyclePoint (first used as boundary, second as point)."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
        ]
        # Window for cycle 2: 2026-01-02 to 2026-01-08 (from prev+1 to current)
        # Brent data: 72 for the window to get clean average
        brent_daily = [
            (date(2026, 1, 2), 72.0),
            (date(2026, 1, 3), 72.0),
            (date(2026, 1, 4), 72.0),
            (date(2026, 1, 5), 72.0),
            (date(2026, 1, 6), 72.0),
            (date(2026, 1, 7), 72.0),
            (date(2026, 1, 8), 72.0),
        ]
        points_by_fuel = build_cycle_points(cycles, brent_daily)
        assert "RON95" in points_by_fuel
        assert len(points_by_fuel["RON95"]) == 1
        point = points_by_fuel["RON95"][0]
        assert point.period == date(2026, 1, 8)
        assert point.fuel == "RON95"
        assert point.world_avg == 75.0
        assert point.retail == 18500.0
        assert abs(point.brent_avg - 72.0) < 0.01

    def test_three_cycles_creates_two_points(self):
        """Three cycles create two CyclePoints (first as boundary, second and third as points)."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
            {"period": date(2026, 1, 15), "fuel": "RON95", "world_avg_price": 80.0, "retail_price": 19000.0},
        ]
        # Window 1: 2026-01-02 to 2026-01-08 → Brent 72
        # Window 2: 2026-01-09 to 2026-01-15 → Brent 76
        brent_daily = [
            (date(2026, 1, 2), 72.0),
            (date(2026, 1, 3), 72.0),
            (date(2026, 1, 4), 72.0),
            (date(2026, 1, 5), 72.0),
            (date(2026, 1, 6), 72.0),
            (date(2026, 1, 7), 72.0),
            (date(2026, 1, 8), 72.0),
            (date(2026, 1, 9), 76.0),
            (date(2026, 1, 10), 76.0),
            (date(2026, 1, 11), 76.0),
            (date(2026, 1, 12), 76.0),
            (date(2026, 1, 13), 76.0),
            (date(2026, 1, 14), 76.0),
            (date(2026, 1, 15), 76.0),
        ]
        points_by_fuel = build_cycle_points(cycles, brent_daily)
        assert len(points_by_fuel["RON95"]) == 2
        # First point: window 2026-01-02 to 2026-01-08, brent_avg 72
        assert points_by_fuel["RON95"][0].period == date(2026, 1, 8)
        assert abs(points_by_fuel["RON95"][0].brent_avg - 72.0) < 0.01
        # Second point: window 2026-01-09 to 2026-01-15, brent_avg 76
        assert points_by_fuel["RON95"][1].period == date(2026, 1, 15)
        assert abs(points_by_fuel["RON95"][1].brent_avg - 76.0) < 0.01

    def test_missing_brent_data_skips_cycle(self):
        """If a cycle window has no Brent data, that cycle is skipped."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
            {"period": date(2026, 1, 15), "fuel": "RON95", "world_avg_price": 80.0, "retail_price": 19000.0},
        ]
        # Window 1: 2026-01-02 to 2026-01-08 → has Brent data (72)
        # Window 2: 2026-01-09 to 2026-01-15 → NO Brent data in this range
        # Window 3: 2026-01-16+ → has Brent data (76)
        brent_daily = [
            (date(2026, 1, 2), 72.0),
            (date(2026, 1, 3), 72.0),
            (date(2026, 1, 4), 72.0),
            (date(2026, 1, 5), 72.0),
            (date(2026, 1, 6), 72.0),
            (date(2026, 1, 7), 72.0),
            (date(2026, 1, 8), 72.0),
            # Gap in Jan 9-15: no data in second window
            (date(2026, 1, 16), 76.0),
            (date(2026, 1, 17), 76.0),
            (date(2026, 1, 18), 76.0),
            (date(2026, 1, 19), 76.0),
            (date(2026, 1, 20), 76.0),
            (date(2026, 1, 21), 76.0),
            (date(2026, 1, 22), 76.0),
        ]
        points_by_fuel = build_cycle_points(cycles, brent_daily)
        # Only two points should be created:
        # - Cycle 1 (01-08): window 01-02 to 01-08 has data → point created
        # - Cycle 2 (01-15): window 01-09 to 01-15 has NO data → SKIP
        # - Cycle 3 (01-22): would be next, but we only have 3 cycles
        assert len(points_by_fuel["RON95"]) == 1
        assert points_by_fuel["RON95"][0].period == date(2026, 1, 8)

    def test_multiple_fuels(self):
        """Multiple fuels are tracked separately."""
        cycles = [
            {"period": date(2026, 1, 1), "fuel": "RON95", "world_avg_price": 70.0, "retail_price": 18000.0},
            {"period": date(2026, 1, 8), "fuel": "RON95", "world_avg_price": 75.0, "retail_price": 18500.0},
            {"period": date(2026, 1, 1), "fuel": "E5RON92", "world_avg_price": 68.0, "retail_price": 17500.0},
            {"period": date(2026, 1, 8), "fuel": "E5RON92", "world_avg_price": 72.0, "retail_price": 18000.0},
        ]
        brent_daily = [
            (date(2026, 1, 1), 68.0),
            (date(2026, 1, 2), 68.0),
            (date(2026, 1, 3), 68.0),
            (date(2026, 1, 4), 68.0),
            (date(2026, 1, 5), 68.0),
            (date(2026, 1, 6), 68.0),
            (date(2026, 1, 7), 68.0),
            (date(2026, 1, 8), 72.0),
            (date(2026, 1, 9), 72.0),
            (date(2026, 1, 10), 72.0),
            (date(2026, 1, 11), 72.0),
            (date(2026, 1, 12), 72.0),
            (date(2026, 1, 13), 72.0),
            (date(2026, 1, 14), 72.0),
            (date(2026, 1, 15), 72.0),
        ]
        points_by_fuel = build_cycle_points(cycles, brent_daily)
        assert set(points_by_fuel.keys()) == {"RON95", "E5RON92"}
        assert len(points_by_fuel["RON95"]) == 1
        assert len(points_by_fuel["E5RON92"]) == 1
        assert points_by_fuel["RON95"][0].fuel == "RON95"
        assert points_by_fuel["E5RON92"][0].fuel == "E5RON92"


class TestMakeForecastRows:
    """Test make_forecast_rows function."""

    def test_basic_forecast_structure(self):
        """make_forecast_rows generates rows with correct structure."""
        # Synthetic 5 cycles for RON95: world = 5 + 0.9*brent, retail = 500 + 0.8*formula
        # Using simple linear model to generate deterministic data
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}

        # Brent daily with constant close (sigma=0)
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=4)

        # Should have 5 fuels * 4 horizons * 3 scenarios (only RON95 has >=4 points)
        assert len(rows) == 1 * 4 * 3

        # Check structure of first row
        first_row = rows[0]
        assert first_row["run_ts"] == run_ts
        assert first_row["fuel"] == "RON95"
        assert first_row["horizon"] == 1
        assert first_row["scenario"] in ["low", "base", "high"]
        assert isinstance(first_row["point"], (int, float))
        assert isinstance(first_row["lo"], (int, float))
        assert isinstance(first_row["hi"], (int, float))
        assert isinstance(first_row["breakdown"], dict)
        assert first_row["model_version"] == MODEL_VERSION
        assert first_row["methodology_version"] == METHODOLOGY_VERSION

    def test_horizons_increment_correctly(self):
        """Target cycles increment by CYCLE_DAYS for each horizon."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=4)

        # Filter rows by scenario to check horizon progression
        base_rows = [r for r in rows if r["scenario"] == "base"]
        assert len(base_rows) == 4

        for i, row in enumerate(base_rows, start=1):
            assert row["horizon"] == i
            expected_target = date(2026, 2, 5) + timedelta(days=i * CYCLE_DAYS)
            assert row["target_cycle"] == expected_target

    def test_zero_sigma_all_scenarios_equal(self):
        """With sigma=0 (no volatility), all three scenarios have identical point values."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=2)

        # Group by horizon
        for h in [1, 2]:
            h_rows = [r for r in rows if r["horizon"] == h]
            points_by_scenario = {r["scenario"]: r["point"] for r in h_rows}
            # All scenarios should have identical point
            assert len(set(points_by_scenario.values())) == 1

    def test_lo_hi_bounds_with_zero_sigma(self):
        """With sigma=0, lo==hi==point (no fan bounds)."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=1)

        row = rows[0]  # Any scenario row since they're all identical
        assert row["lo"] == row["point"]
        assert row["hi"] == row["point"]

    def test_breakdown_includes_required_keys(self):
        """breakdown dict includes brent_avg, world_hat, formula_vnd, calibration, fx, disclaimer."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=1)

        breakdown = rows[0]["breakdown"]
        assert "brent_avg" in breakdown
        assert "world_hat" in breakdown
        assert "formula_vnd" in breakdown
        assert "calibration" in breakdown
        assert "fx" in breakdown
        assert "disclaimer" in breakdown
        assert breakdown["disclaimer"] == DISCLAIMER
        assert breakdown["fx"] == 26000.0

    def test_fewer_than_4_points_skipped(self):
        """A fuel with <4 points is skipped."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=1)

        # No rows for RON95 since it has only 2 points
        assert len(rows) == 0

    def test_multiple_fuels_with_mixed_point_counts(self):
        """Only fuels with >=4 points generate forecast rows."""
        points_by_fuel = {
            "RON95": [
                CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
                CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
                CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
                CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
                CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
            ],
            "E5RON92": [  # Only 2 points, should be skipped
                CyclePoint(date(2026, 1, 8), "E5RON92", 65.0, 17500.0, 66.0),
                CyclePoint(date(2026, 1, 15), "E5RON92", 70.0, 18000.0, 70.0),
            ],
            "DO005S": [  # Exactly 4 points, should be included
                CyclePoint(date(2026, 1, 8), "DO005S", 62.0, 17000.0, 63.0),
                CyclePoint(date(2026, 1, 15), "DO005S", 67.0, 17500.0, 67.0),
                CyclePoint(date(2026, 1, 22), "DO005S", 72.0, 18000.0, 70.0),
                CyclePoint(date(2026, 1, 29), "DO005S", 76.0, 18500.0, 74.0),
            ],
        }
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=2)

        # RON95: 5 points, 2 horizons, 3 scenarios = 6 rows
        # E5RON92: 2 points, skipped = 0 rows
        # DO005S: 4 points, 2 horizons, 3 scenarios = 6 rows
        assert len(rows) == 12

        fuels_in_rows = set(r["fuel"] for r in rows)
        assert fuels_in_rows == {"RON95", "DO005S"}
        assert not any(r["fuel"] == "E5RON92" for r in rows)

    def test_calibration_in_breakdown(self):
        """Calibration parameters are included in breakdown."""
        points = [
            CyclePoint(date(2026, 1, 8), "RON95", 67.0, 18000.0, 68.0),
            CyclePoint(date(2026, 1, 15), "RON95", 72.0, 18500.0, 72.0),
            CyclePoint(date(2026, 1, 22), "RON95", 76.0, 19000.0, 75.0),
            CyclePoint(date(2026, 1, 29), "RON95", 80.0, 19500.0, 78.0),
            CyclePoint(date(2026, 2, 5), "RON95", 84.0, 20000.0, 82.0),
        ]
        points_by_fuel = {"RON95": points}
        brent_daily = [(date(2026, 1, 1) + timedelta(days=i), 75.0) for i in range(50)]

        run_ts = datetime(2026, 2, 6, 10, 0, 0)
        rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=26000.0, horizons=1)

        cal_dict = rows[0]["breakdown"]["calibration"]
        assert "alpha" in cal_dict
        assert "beta" in cal_dict
        assert "a" in cal_dict
        assert "b" in cal_dict
        assert all(isinstance(v, (int, float)) for v in cal_dict.values())
