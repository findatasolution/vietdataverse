"""Test suite for be.fuel.backtest — walk-forward validation of the delta
pass-through model.

structural-v1's walk_forward was removed 2026-09-10 along with the model itself
(see calibration.py docstring); this file now only covers walk_forward_delta.
"""
import pytest
from datetime import date, timedelta
from be.fuel.calibration import CyclePoint
from be.fuel.backtest import BacktestResult, walk_forward_delta, MODEL_VERSION


class TestWalkForwardDeltaPerfectProcess:
    def test_perfect_delta_process_beats_rw(self):
        worlds = [80, 85, 82, 90, 95, 88, 92, 98, 94, 100, 105, 99]
        pts, retail = [], 20000.0
        for i, w in enumerate(worlds):
            if i > 0:
                retail += 140.0 * (w - worlds[i - 1])
            pts.append(CyclePoint(date(2026, 1, 1) + timedelta(days=7 * i),
                                  "DO005S", float(w), retail))
        r = walk_forward_delta(pts, min_train=6, z=1.28)
        assert isinstance(r, BacktestResult)
        assert r.model_version == MODEL_VERSION
        assert r.fuel == "DO005S"
        assert r.horizon == 1
        assert r.mae < 1.0
        assert r.coverage == 1.0
        assert r.skill_vs_rw > 0.9


class TestWalkForwardDeltaValidation:
    def test_insufficient_data_raises_value_error(self):
        pts = [CyclePoint(date(2026, 1, 1 + i), "RON95", 80.0 + i, 20000.0) for i in range(6)]
        with pytest.raises(ValueError):
            walk_forward_delta(pts, min_train=6)

    def test_exact_minimum_data_succeeds(self):
        worlds = [80, 85, 82, 90, 95, 88, 92, 98]
        pts, retail = [], 20000.0
        for i, w in enumerate(worlds):
            if i > 0:
                retail += 100.0 * (w - worlds[i - 1])
            pts.append(CyclePoint(date(2026, 1, 1) + timedelta(days=7 * i),
                                  "RON95", float(w), retail))
        result = walk_forward_delta(pts, min_train=6, z=1.28)
        assert result.n == 2  # 8 - 6


class TestWalkForwardDeltaNoisy:
    def test_noisy_process_realistic_metrics(self):
        """Noisy pass-through (small alternating noise) still beats RW."""
        worlds = [80, 85, 82, 90, 95, 88, 92, 98, 94, 100, 105, 99]
        pts, retail = [], 20000.0
        for i, w in enumerate(worlds):
            if i > 0:
                retail += 140.0 * (w - worlds[i - 1]) + (50 if i % 2 == 0 else -50)
            pts.append(CyclePoint(date(2026, 1, 1) + timedelta(days=7 * i),
                                  "E5RON92", float(w), retail))
        result = walk_forward_delta(pts, min_train=6, z=1.28)
        assert result.mae > 0
        assert 0 <= result.coverage <= 1
        assert result.skill_vs_rw > 0


class TestFullSuite:
    def test_full_suite_imports(self):
        """Verify all fuel modules import correctly."""
        from be.fuel.calibration import fit_passthrough, predict_retail_from_world_delta
        from be.fuel.forecast import build_cycle_points
        from be.fuel.backtest import walk_forward_delta, write_backtest

        assert callable(fit_passthrough)
        assert callable(predict_retail_from_world_delta)
        assert callable(build_cycle_points)
        assert callable(walk_forward_delta)
        assert callable(write_backtest)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
