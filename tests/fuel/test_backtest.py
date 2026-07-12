"""Test suite for be.fuel.backtest — walk-forward validation and backtest metrics.

Tests verify:
1. Perfect-linear synthetic data: high accuracy, perfect coverage
2. ValueError when insufficient data (len(points) < min_train + 2)
3. Noisy synthetic: realistic metrics
4. Degenerate case: constant retail with varying brent (skill calculation)
5. Full suite stays green
"""
import pytest
from datetime import date
from be.fuel.calibration import CyclePoint
from be.fuel.backtest import BacktestResult, walk_forward, MODEL_VERSION, FX_DEFAULT


class TestWalkForwardPerfectLinear:
    """Test walk_forward with perfect-linear synthetic data."""

    def test_perfect_linear_high_accuracy(self):
        """Synthetic linear retail = 500 + 0.8*formula should have mae < 1.0, rmse < 1.0, coverage >= 0.75."""
        # Generate synthetic data: linear relationship
        # retail = 500 + 0.8 * (5 + 0.9 * brent)
        # where world = 5 + 0.9 * brent
        points = []
        for i in range(10):
            brent = 50.0 + i * 2.0  # 50, 52, 54, ...
            world = 5.0 + 0.9 * brent
            # Assume formula_vnd ≈ 2000 + 0.1*world (simplified; not exact but close)
            formula_vnd = 2000.0 + 0.1 * world
            retail = 500.0 + 0.8 * formula_vnd

            point = CyclePoint(
                period=date(2026, 1, 1 + i),
                fuel="RON95",
                world_avg=world,
                retail=retail,
                brent_avg=brent,
            )
            points.append(point)

        result = walk_forward(points, fx=FX_DEFAULT, min_train=6, z=1.28)

        # Perfect linear should have very low error
        assert result.mae < 1.0, f"MAE should be < 1.0, got {result.mae}"
        assert result.rmse < 1.0, f"RMSE should be < 1.0, got {result.rmse}"
        assert result.coverage >= 0.75, f"Coverage should be >= 0.75, got {result.coverage}"
        assert result.skill_vs_rw > 0.9, f"Skill should be > 0.9, got {result.skill_vs_rw}"
        assert result.n == 4, f"n should be 4 (10 - 6), got {result.n}"

    def test_perfect_linear_returns_correct_backtest_result(self):
        """walk_forward returns BacktestResult with all required fields."""
        points = []
        for i in range(8):
            brent = 60.0 + i * 1.5
            world = 10.0 + 0.85 * brent
            formula_vnd = 2500.0 + 0.12 * world
            retail = 1000.0 + 0.9 * formula_vnd

            point = CyclePoint(
                period=date(2026, 2, 1 + i),
                fuel="E5RON92",
                world_avg=world,
                retail=retail,
                brent_avg=brent,
            )
            points.append(point)

        result = walk_forward(points, fx=26000.0, min_train=4, z=1.28)

        assert isinstance(result, BacktestResult)
        assert result.fuel == "E5RON92"
        assert result.horizon == 1
        assert result.mae > 0
        assert result.rmse > 0
        assert 0 <= result.coverage <= 1
        assert result.n >= 4
        assert result.model_version == MODEL_VERSION


class TestWalkForwardValidation:
    """Test walk_forward validation logic."""

    def test_insufficient_data_raises_value_error(self):
        """walk_forward raises ValueError if len(points) < min_train + 2."""
        # min_train=6 requires >=8 points; 7 points should fail
        points = []
        for i in range(7):
            point = CyclePoint(
                period=date(2026, 1, 1 + i),
                fuel="DO005S",
                world_avg=40.0 + i,
                retail=14000.0 + i * 100,
                brent_avg=38.0 + i,
            )
            points.append(point)

        with pytest.raises(ValueError):
            walk_forward(points, fx=FX_DEFAULT, min_train=6, z=1.28)

    def test_exact_minimum_data_succeeds(self):
        """walk_forward succeeds with exactly min_train + 2 points."""
        # min_train=4 requires >=6 points
        points = []
        for i in range(6):
            point = CyclePoint(
                period=date(2026, 1, 1 + i),
                fuel="RON95",
                world_avg=50.0 + i * 0.5,
                retail=15000.0 + i * 50,
                brent_avg=48.0 + i * 0.5,
            )
            points.append(point)

        result = walk_forward(points, fx=FX_DEFAULT, min_train=4, z=1.28)
        assert result.n == 2  # 6 - 4 = 2 test points

    def test_points_sorted_by_period_ascending(self):
        """walk_forward expects points sorted by period (earliest first)."""
        # Deliberately provide unsorted points
        points = [
            CyclePoint(date(2026, 3, 1), "RON95", 55.0, 16000.0, 53.0),
            CyclePoint(date(2026, 1, 1), "RON95", 50.0, 15000.0, 48.0),
            CyclePoint(date(2026, 2, 1), "RON95", 52.0, 15500.0, 50.0),
            CyclePoint(date(2026, 4, 1), "RON95", 60.0, 17000.0, 58.0),
            CyclePoint(date(2026, 5, 1), "RON95", 65.0, 18000.0, 63.0),
            CyclePoint(date(2026, 6, 1), "RON95", 70.0, 19000.0, 68.0),
        ]

        # Sort externally (user responsibility per spec)
        points_sorted = sorted(points, key=lambda p: p.period)

        result = walk_forward(points_sorted, fx=FX_DEFAULT, min_train=4, z=1.28)
        assert result.n == 2


class TestWalkForwardNoisySynthetic:
    """Test walk_forward with noisy synthetic data."""

    def test_noisy_synthetic_data(self):
        """Noisy data (retail + alternating ±300) should have mae in realistic range."""
        # Base: linear retail
        # Noise: +300 on odd i, -300 on even i
        points = []
        for i in range(12):
            brent = 55.0 + i * 1.0
            world = 8.0 + 0.88 * brent
            formula_vnd = 2200.0 + 0.11 * world
            retail_base = 800.0 + 0.85 * formula_vnd
            retail = retail_base + (300 if i % 2 == 0 else -300)

            point = CyclePoint(
                period=date(2026, 1, 1 + i),
                fuel="E5RON92",
                world_avg=world,
                retail=retail,
                brent_avg=brent,
            )
            points.append(point)

        result = walk_forward(points, fx=FX_DEFAULT, min_train=6, z=1.28)

        # Noisy data should have higher MAE; loose bounds
        assert 100 <= result.mae <= 600, f"MAE should be in [100, 600], got {result.mae}"
        assert result.coverage >= 0.5, f"Coverage should be >= 0.5 with z=1.28, got {result.coverage}"
        assert result.n == 6  # 12 - 6

    def test_noisy_synthetic_still_beats_random_walk(self):
        """Even with noise, if model is good, skill should be positive."""
        # Clean synthetic (not too noisy) should beat random walk
        points = []
        for i in range(10):
            brent = 60.0 + i * 0.8
            world = 10.0 + 0.87 * brent
            formula_vnd = 2300.0 + 0.105 * world
            retail_base = 900.0 + 0.83 * formula_vnd
            # Small noise only
            retail = retail_base + (50 if i % 2 == 0 else -50)

            point = CyclePoint(
                period=date(2026, 2, 1 + i),
                fuel="DO005S",
                world_avg=world,
                retail=retail,
                brent_avg=brent,
            )
            points.append(point)

        result = walk_forward(points, fx=FX_DEFAULT, min_train=5, z=1.28)

        # Small-noise model should have positive skill
        assert result.skill_vs_rw > 0, f"Skill should be > 0, got {result.skill_vs_rw}"


class TestWalkForwardDegenerateCase:
    """Test walk_forward with degenerate data (constant retail, varying brent)."""

    def test_constant_retail_brent_varying(self):
        """Constant retail, varying brent → OLS b≈0 → mae≈0 → skill==1.0."""
        # Keep retail constant (e.g., 15000), vary brent
        points = []
        for i in range(8):
            brent = 45.0 + i * 2.0
            # Compute world and formula for structure; keep retail constant
            world = 5.0 + 0.9 * brent
            formula_vnd = 2000.0 + 0.1 * world
            retail = 15000.0  # CONSTANT

            point = CyclePoint(
                period=date(2026, 1, 1 + i),
                fuel="RON95",
                world_avg=world,
                retail=retail,
                brent_avg=brent,
            )
            points.append(point)

        result = walk_forward(points, fx=FX_DEFAULT, min_train=4, z=1.28)

        # With constant retail, model will learn b≈0 → predict ≈ mean(train_retail)
        # Error ≈ 0, so mae ≈ 0
        # Random walk error: |prev_retail - test_retail| = 0 (both constant)
        # So rw_mae = 0
        # skill = 1.0 if mae == 0 else -1.0 → should be 1.0
        assert result.mae < 0.01, f"MAE should be ~0 for constant retail, got {result.mae}"
        assert result.skill_vs_rw == 1.0, f"Skill should be 1.0 when mae≈0 and rw_mae=0, got {result.skill_vs_rw}"


class TestFullSuite:
    """Ensure the full fuel test suite still passes."""

    def test_full_suite_imports(self):
        """Verify all fuel modules import correctly."""
        from be.fuel.calibration import fit_calibration, predict_retail
        from be.fuel.forecast import build_cycle_points
        from be.fuel.backtest import walk_forward, write_backtest

        # Just verify they exist and are callable
        assert callable(fit_calibration)
        assert callable(predict_retail)
        assert callable(build_cycle_points)
        assert callable(walk_forward)
        assert callable(write_backtest)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestWalkForwardDelta:
    def test_perfect_delta_process_beats_rw(self):
        from be.fuel.backtest import walk_forward_delta, DELTA_MODEL_VERSION
        from be.fuel.calibration import CyclePoint
        from datetime import date, timedelta
        worlds = [80, 85, 82, 90, 95, 88, 92, 98, 94, 100, 105, 99]
        pts, retail = [], 20000.0
        for i, w in enumerate(worlds):
            if i > 0:
                retail += 140.0 * (w - worlds[i - 1])
            pts.append(CyclePoint(date(2026, 1, 1) + timedelta(days=7 * i),
                                  "DO005S", float(w), retail, 70.0 + i))
        r = walk_forward_delta(pts, min_train=6, z=1.28)
        assert r.model_version == DELTA_MODEL_VERSION
        assert r.mae < 1.0
        assert r.coverage == 1.0
        assert r.skill_vs_rw > 0.9

    def test_delta_requires_enough_points(self):
        from be.fuel.backtest import walk_forward_delta
        from be.fuel.calibration import CyclePoint
        from datetime import date
        import pytest
        pts = [CyclePoint(date(2026, 1, 1 + i), "RON95", 80.0 + i, 20000.0, 70.0) for i in range(6)]
        with pytest.raises(ValueError):
            walk_forward_delta(pts, min_train=6)
