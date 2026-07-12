"""Test suite for be.fuel.calibration — OLS regression and two-stage fuel price calibration.

Tests are ordered to verify:
1. Core _ols function (perfect fit, errors)
2. fit_calibration contract (validation, errors)
3. Round-trip prediction accuracy
4. Regulator damping detection
"""
import pytest
from datetime import date
from be.fuel.calibration import (
    _ols,
    fit_calibration,
    FuelCalibration,
    CyclePoint,
    STANDARD_PARAMS,
    predict_world,
    predict_retail,
)
from be.fuel.formula import base_price_vnd_per_liter


class TestOLS:
    """Test the core _ols function."""

    def test_perfect_line_exact_fit(self):
        """OLS recovers intercept/slope exactly from y = 2 + 3*x."""
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [5.0, 8.0, 11.0, 14.0]  # 2 + 3*x
        intercept, slope = _ols(xs, ys)
        assert abs(intercept - 2.0) < 1e-10
        assert abs(slope - 3.0) < 1e-10

    def test_perfect_line_with_noise(self):
        """OLS recovers approximately correct slope/intercept with small noise."""
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0 + 3.0 * x + 0.01 for x in xs]  # y = 2 + 3*x + small noise
        intercept, slope = _ols(xs, ys)
        assert abs(intercept - 2.0) < 0.1
        assert abs(slope - 3.0) < 0.01

    def test_ols_rejects_too_few_points(self):
        """_ols raises ValueError if len(xs) < 2."""
        with pytest.raises(ValueError):
            _ols([1.0], [2.0])
        with pytest.raises(ValueError):
            _ols([], [])

    def test_ols_rejects_constant_xs(self):
        """_ols raises ValueError if xs have zero variance."""
        xs = [5.0, 5.0, 5.0]
        ys = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError):
            _ols(xs, ys)

    def test_ols_horizontal_line(self):
        """OLS fits horizontal line (slope=0) when all ys are the same."""
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [7.0, 7.0, 7.0, 7.0]
        intercept, slope = _ols(xs, ys)
        assert abs(intercept - 7.0) < 1e-10
        assert abs(slope - 0.0) < 1e-10


class TestFitCalibrationValidation:
    """Test fit_calibration contract and validation."""

    def test_fit_calibration_requires_at_least_4_points(self):
        """fit_calibration raises ValueError if len(points) < 4."""
        points = [
            CyclePoint(date(2026, 1, 1), "RON95", 50.0, 15000.0, 48.0),
            CyclePoint(date(2026, 2, 1), "RON95", 55.0, 16000.0, 53.0),
            CyclePoint(date(2026, 3, 1), "RON95", 60.0, 17000.0, 58.0),
        ]
        with pytest.raises(ValueError, match="at least 4"):
            fit_calibration(points, fx=26000.0)

    def test_fit_calibration_rejects_mixed_fuels(self):
        """fit_calibration raises ValueError if points have different fuels."""
        points = [
            CyclePoint(date(2026, 1, 1), "RON95", 50.0, 15000.0, 48.0),
            CyclePoint(date(2026, 2, 1), "RON95", 55.0, 16000.0, 53.0),
            CyclePoint(date(2026, 3, 1), "E5RON92", 55.0, 15500.0, 53.0),
            CyclePoint(date(2026, 4, 1), "RON95", 60.0, 17000.0, 58.0),
        ]
        with pytest.raises(ValueError, match="single fuel"):
            fit_calibration(points, fx=26000.0)

    def test_fit_calibration_accepts_exactly_4_points(self):
        """fit_calibration accepts exactly 4 points with one fuel."""
        points = [
            CyclePoint(date(2026, 1, 1), "RON95", 50.0, 15000.0, 48.0),
            CyclePoint(date(2026, 2, 1), "RON95", 55.0, 16000.0, 53.0),
            CyclePoint(date(2026, 3, 1), "RON95", 60.0, 17000.0, 58.0),
            CyclePoint(date(2026, 4, 1), "RON95", 65.0, 18000.0, 63.0),
        ]
        cal = fit_calibration(points, fx=26000.0)
        assert cal.fuel == "RON95"
        assert isinstance(cal.alpha, float)
        assert isinstance(cal.beta, float)
        assert isinstance(cal.a, float)
        assert isinstance(cal.b, float)


class TestSyntheticRoundTrip:
    """Synthetic test: generate points from a known model, fit, and verify recovery."""

    def test_round_trip_recovery(self):
        """Build 6 synthetic points with known α=5, β=0.9, a=500, b=0.8; fit and verify."""
        # Ground truth: world = 5 + 0.9*brent
        alpha_true = 5.0
        beta_true = 0.9
        # Ground truth: retail = 500 + 0.8 * formula_vnd
        a_true = 500.0
        b_true = 0.8

        fx = 26000.0
        fuel = "RON95"

        # Generate 6 points by varying brent from 70 to 120
        points = []
        for i, brent_avg in enumerate([70, 80, 90, 100, 110, 120]):
            world_avg = alpha_true + beta_true * brent_avg
            # Compute formula_vnd using the standard params
            formula_vnd = base_price_vnd_per_liter(world_avg, fx, STANDARD_PARAMS[fuel])
            retail = a_true + b_true * formula_vnd
            points.append(
                CyclePoint(
                    period=date(2026, 1, 1) if i == 0 else date(2026, 1, i),
                    fuel=fuel,
                    world_avg=world_avg,
                    retail=retail,
                    brent_avg=brent_avg,
                )
            )

        # Fit
        cal = fit_calibration(points, fx=fx)

        # Verify recovery of α, β to 1e-6 tolerance
        assert abs(cal.alpha - alpha_true) < 1e-6, f"alpha: expected {alpha_true}, got {cal.alpha}"
        assert abs(cal.beta - beta_true) < 1e-6, f"beta: expected {beta_true}, got {cal.beta}"

        # Verify recovery of a, b to 1e-3 tolerance (looser because of formula_vnd rounding)
        assert abs(cal.a - a_true) < 1e-3, f"a: expected {a_true}, got {cal.a}"
        assert abs(cal.b - b_true) < 1e-3, f"b: expected {b_true}, got {cal.b}"

    def test_round_trip_predict_retail_matches_generating_equation(self):
        """At brent=100, predict_retail should match the generating equation within 1 VND."""
        alpha_true = 5.0
        beta_true = 0.9
        a_true = 500.0
        b_true = 0.8

        fx = 26000.0
        fuel = "RON95"

        # Generate 6 points
        points = []
        for i, brent_avg in enumerate([70, 80, 90, 100, 110, 120]):
            world_avg = alpha_true + beta_true * brent_avg
            formula_vnd = base_price_vnd_per_liter(world_avg, fx, STANDARD_PARAMS[fuel])
            retail = a_true + b_true * formula_vnd
            points.append(
                CyclePoint(
                    period=date(2026, 1, i + 1) if i > 0 else date(2026, 1, 1),
                    fuel=fuel,
                    world_avg=world_avg,
                    retail=retail,
                    brent_avg=brent_avg,
                )
            )

        # Fit and predict at brent=100
        cal = fit_calibration(points, fx=fx)
        predicted_retail = predict_retail(cal, brent_avg=100.0, fx=fx)

        # Compute expected retail using the generating equation
        world_expected = alpha_true + beta_true * 100.0
        formula_vnd_expected = base_price_vnd_per_liter(world_expected, fx, STANDARD_PARAMS[fuel])
        expected_retail = a_true + b_true * formula_vnd_expected

        # Should match within 1 VND
        assert abs(predicted_retail - expected_retail) < 1.0, \
            f"predicted {predicted_retail} vs expected {expected_retail}"


class TestDampingDetection:
    """Test that regulatory damping is detected (b < 1)."""

    def test_damping_detection_b_less_than_one(self):
        """When retail is generated with b=0.7, fitted b should be < 0.75."""
        alpha_true = 5.0
        beta_true = 0.9
        a_true = 500.0
        b_true = 0.7  # Damping: retail doesn't track formula fully

        fx = 26000.0
        fuel = "RON95"

        # Generate 6 points with damping
        points = []
        for i, brent_avg in enumerate([70, 80, 90, 100, 110, 120]):
            world_avg = alpha_true + beta_true * brent_avg
            formula_vnd = base_price_vnd_per_liter(world_avg, fx, STANDARD_PARAMS[fuel])
            retail = a_true + b_true * formula_vnd  # b=0.7 damping
            points.append(
                CyclePoint(
                    period=date(2026, 1, i + 1) if i > 0 else date(2026, 1, 1),
                    fuel=fuel,
                    world_avg=world_avg,
                    retail=retail,
                    brent_avg=brent_avg,
                )
            )

        # Fit
        cal = fit_calibration(points, fx=fx)

        # Verify b < 0.75 (indicating damping)
        assert cal.b < 0.75, f"Expected b < 0.75 to indicate damping, got b={cal.b}"


class TestPredictionFunctions:
    """Test predict_world and predict_retail helper functions."""

    def test_predict_world_simple(self):
        """predict_world applies the linear transformation."""
        # Manually create a calibration
        cal = FuelCalibration(fuel="RON95", alpha=5.0, beta=0.9, a=500.0, b=0.8)
        world = predict_world(cal, brent_avg=100.0)
        assert abs(world - (5.0 + 0.9 * 100.0)) < 1e-10

    def test_predict_retail_uses_formula(self):
        """predict_retail applies formula_vnd transformation."""
        cal = FuelCalibration(fuel="RON95", alpha=5.0, beta=0.9, a=500.0, b=0.8)
        fx = 26000.0

        # Predict retail at brent=100
        retail = predict_retail(cal, brent_avg=100.0, fx=fx)

        # Manually compute expected
        world = 5.0 + 0.9 * 100.0
        formula_vnd = base_price_vnd_per_liter(world, fx, STANDARD_PARAMS["RON95"])
        expected = 500.0 + 0.8 * formula_vnd

        assert abs(retail - expected) < 0.01, \
            f"predict_retail mismatch: got {retail}, expected {expected}"


class TestMultipleFuels:
    """Test that calibration works for different fuel types."""

    def test_e5ron92_calibration(self):
        """fit_calibration works for E5RON92 with its standard params."""
        points = []
        for i, brent_avg in enumerate([70, 80, 90, 100]):
            world_avg = 5.0 + 0.9 * brent_avg
            formula_vnd = base_price_vnd_per_liter(world_avg, 26000.0, STANDARD_PARAMS["E5RON92"])
            retail = 450.0 + 0.8 * formula_vnd
            points.append(
                CyclePoint(
                    period=date(2026, 1, i + 1),
                    fuel="E5RON92",
                    world_avg=world_avg,
                    retail=retail,
                    brent_avg=brent_avg,
                )
            )

        cal = fit_calibration(points, fx=26000.0)
        assert cal.fuel == "E5RON92"
        assert isinstance(cal.alpha, float)
        assert isinstance(cal.beta, float)

    def test_do005s_calibration(self):
        """fit_calibration works for DO005S (diesel) with excise_pct=0."""
        points = []
        for i, brent_avg in enumerate([60, 70, 80, 90]):
            world_avg = 4.0 + 0.85 * brent_avg
            formula_vnd = base_price_vnd_per_liter(world_avg, 26000.0, STANDARD_PARAMS["DO005S"])
            retail = 400.0 + 0.75 * formula_vnd
            points.append(
                CyclePoint(
                    period=date(2026, 1, i + 1),
                    fuel="DO005S",
                    world_avg=world_avg,
                    retail=retail,
                    brent_avg=brent_avg,
                )
            )

        cal = fit_calibration(points, fx=26000.0)
        assert cal.fuel == "DO005S"
