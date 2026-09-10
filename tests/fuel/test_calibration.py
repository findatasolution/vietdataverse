"""Test suite for be.fuel.calibration — the delta pass-through model.

structural-v1 (two-stage OLS calibration) was removed 2026-09-10; this file now
only covers the delta pass-through model (fit_passthrough, predict_retail_from_world_delta).
"""
import pytest
from datetime import date

from be.fuel.calibration import (
    CyclePoint,
    fit_passthrough,
    predict_retail_from_world_delta,
)


def _points(fuel, worlds, retails, start=date(2026, 1, 1), step_days=7):
    return [
        CyclePoint(period=date.fromordinal(start.toordinal() + i * step_days),
                   fuel=fuel, world_avg=w, retail=r)
        for i, (w, r) in enumerate(zip(worlds, retails))
    ]


class TestFitPassthrough:
    def test_requires_at_least_4_points(self):
        points = _points("RON95", [70.0, 72.0, 71.0], [18000.0, 18200.0, 18100.0])
        with pytest.raises(ValueError):
            fit_passthrough(points)

    def test_rejects_mixed_fuels(self):
        points = [
            CyclePoint(date(2026, 1, 1), "RON95", 70.0, 18000.0),
            CyclePoint(date(2026, 1, 8), "E5RON92", 68.0, 17500.0),
            CyclePoint(date(2026, 1, 15), "RON95", 74.0, 18500.0),
            CyclePoint(date(2026, 1, 22), "RON95", 78.0, 19000.0),
        ]
        with pytest.raises(ValueError):
            fit_passthrough(points)

    def test_recovers_known_k_on_noiseless_data(self):
        """Δretail = 150·Δworld exactly → fitted k should recover 150 within float tol."""
        worlds = [70.0, 75.0, 72.0, 80.0, 85.0, 78.0]
        retail = [18000.0]
        for j in range(1, len(worlds)):
            retail.append(retail[-1] + 150.0 * (worlds[j] - worlds[j - 1]))
        points = _points("DO005S", worlds, retail)

        k = fit_passthrough(points)
        assert abs(k - 150.0) < 1e-6

    def test_zero_world_variance_raises(self):
        """All Δworld == 0 → zero variance → ValueError."""
        points = _points("RON95", [70.0, 70.0, 70.0, 70.0], [18000.0, 18100.0, 18000.0, 18100.0])
        with pytest.raises(ValueError):
            fit_passthrough(points)


class TestPredictRetailFromWorldDelta:
    def test_basic_prediction(self):
        pred = predict_retail_from_world_delta(prev_retail=18000.0, k=150.0,
                                                world_prev=70.0, world_now=75.0)
        assert pred == 18000.0 + 150.0 * 5.0

    def test_zero_delta_returns_prev_retail(self):
        pred = predict_retail_from_world_delta(prev_retail=18000.0, k=150.0,
                                                world_prev=70.0, world_now=70.0)
        assert pred == 18000.0

    def test_negative_delta(self):
        pred = predict_retail_from_world_delta(prev_retail=18000.0, k=150.0,
                                                world_prev=75.0, world_now=70.0)
        assert pred == 18000.0 - 150.0 * 5.0
