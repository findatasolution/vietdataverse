"""Tests for be.fuel.world_model module.

Covers:
- brent_window_avg: average over calendar windows with optional forward-fill
- daily_log_return_sigma: volatility from log returns
- fan_bands: random-walk confidence bands
"""
from datetime import date, timedelta
import math

import pytest

from be.fuel.world_model import brent_window_avg, daily_log_return_sigma, fan_bands


class TestBrentWindowAvg:
    """Test brent_window_avg with various windows and fill strategies."""

    def test_fully_observed_window_exact_mean(self):
        """Five consecutive dates with known values should return exact arithmetic mean."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 102.0),
            (date(2026, 7, 3), 101.0),
            (date(2026, 7, 4), 103.0),
            (date(2026, 7, 5), 104.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 5)
        result = brent_window_avg(daily, window_start, window_end)
        expected = (100.0 + 102.0 + 101.0 + 103.0 + 104.0) / 5
        assert result == expected

    def test_window_with_gaps_no_fill(self):
        """Missing days inside window are not counted; only observed days matter."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 3), 105.0),  # gap on 2nd
            (date(2026, 7, 5), 110.0),  # gap on 4th
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 5)
        result = brent_window_avg(daily, window_start, window_end)
        expected = (100.0 + 105.0 + 110.0) / 3
        assert result == expected

    def test_window_extending_past_last_observation_with_fill(self):
        """Days after last observation are filled with rw_fill if provided."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 102.0),
            (date(2026, 7, 3), 101.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 6)  # extends 3 days past last observation
        result = brent_window_avg(daily, window_start, window_end, rw_fill=80.0)
        # Last observation is 2026-07-03, so days 04, 05, 06 are filled at 80.0
        expected = (100.0 + 102.0 + 101.0 + 80.0 + 80.0 + 80.0) / 6
        assert result == expected

    def test_zero_observed_days_no_fill_raises(self):
        """Zero observed days in window + rw_fill=None should raise ValueError."""
        daily = [
            (date(2026, 6, 1), 100.0),
            (date(2026, 6, 2), 102.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 5)  # no overlap
        with pytest.raises(ValueError):
            brent_window_avg(daily, window_start, window_end)

    def test_zero_observed_days_with_fill_returns_fill(self):
        """Zero observed days in window + rw_fill=75.0 should return 75.0."""
        daily = [
            (date(2026, 6, 1), 100.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 5)
        result = brent_window_avg(daily, window_start, window_end, rw_fill=75.0)
        assert result == 75.0

    def test_partial_window_overlap_beginning(self):
        """Window starts before first observation; only overlapping days counted."""
        daily = [
            (date(2026, 7, 3), 100.0),
            (date(2026, 7, 4), 102.0),
            (date(2026, 7, 5), 101.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 5)
        result = brent_window_avg(daily, window_start, window_end)
        expected = (100.0 + 102.0 + 101.0) / 3
        assert result == expected

    def test_partial_window_overlap_end(self):
        """Window ends before last observation; only overlapping days counted."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 102.0),
            (date(2026, 7, 5), 110.0),
        ]
        window_start = date(2026, 7, 1)
        window_end = date(2026, 7, 2)
        result = brent_window_avg(daily, window_start, window_end)
        expected = (100.0 + 102.0) / 2
        assert result == expected


class TestDailyLogReturnSigma:
    """Test daily_log_return_sigma (volatility)."""

    def test_constant_series_zero_volatility(self):
        """If all prices are the same, sigma is 0.0."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 100.0),
            (date(2026, 7, 3), 100.0),
            (date(2026, 7, 4), 100.0),
        ]
        result = daily_log_return_sigma(daily)
        assert result == 0.0

    def test_four_point_known_series(self):
        """Hand-computed 4-point series to verify calculation."""
        # prices: 100, 110, 99, 108
        # log returns: ln(110/100)=0.0953, ln(99/110)=-0.1054, ln(108/99)=0.0870
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 110.0),
            (date(2026, 7, 3), 99.0),
            (date(2026, 7, 4), 108.0),
        ]
        result = daily_log_return_sigma(daily)

        # Compute expected value manually
        r1 = math.log(110.0 / 100.0)
        r2 = math.log(99.0 / 110.0)
        r3 = math.log(108.0 / 99.0)
        returns = [r1, r2, r3]
        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        expected = math.sqrt(variance)

        assert math.isclose(result, expected, rel_tol=1e-9)

    def test_two_observations_raises(self):
        """Fewer than 3 observations should raise ValueError."""
        daily = [
            (date(2026, 7, 1), 100.0),
            (date(2026, 7, 2), 102.0),
        ]
        with pytest.raises(ValueError):
            daily_log_return_sigma(daily)

    def test_one_observation_raises(self):
        """Single observation should raise ValueError."""
        daily = [(date(2026, 7, 1), 100.0)]
        with pytest.raises(ValueError):
            daily_log_return_sigma(daily)

    def test_empty_raises(self):
        """Empty series should raise ValueError."""
        with pytest.raises(ValueError):
            daily_log_return_sigma([])


class TestFanBands:
    """Test fan_bands random-walk confidence intervals."""

    def test_base_equals_last_close(self):
        """Central band should equal last_close."""
        last_close = 100.0
        sigma_daily = 0.02
        days_ahead = 10
        low, central, high = fan_bands(last_close, sigma_daily, days_ahead)
        assert central == last_close

    def test_low_below_high(self):
        """Low band must be strictly below high band."""
        last_close = 100.0
        sigma_daily = 0.02
        days_ahead = 10
        low, central, high = fan_bands(last_close, sigma_daily, days_ahead)
        assert low < central < high

    def test_symmetry_in_log_space(self):
        """Geometric mean of low and high should equal last_close."""
        last_close = 100.0
        sigma_daily = 0.02
        days_ahead = 10
        low, central, high = fan_bands(last_close, sigma_daily, days_ahead)
        geometric_mean = math.sqrt(low * high)
        assert math.isclose(geometric_mean, last_close, rel_tol=1e-9)

    def test_days_ahead_zero_raises(self):
        """days_ahead < 1 should raise ValueError."""
        with pytest.raises(ValueError):
            fan_bands(100.0, 0.02, 0)

    def test_last_close_nonpositive_raises(self):
        """last_close <= 0 should raise ValueError."""
        with pytest.raises(ValueError):
            fan_bands(0.0, 0.02, 10)
        with pytest.raises(ValueError):
            fan_bands(-5.0, 0.02, 10)

    def test_bands_widen_with_days_ahead(self):
        """Bands should be wider (further from center) with more days ahead."""
        last_close = 100.0
        sigma_daily = 0.02

        low1, c1, high1 = fan_bands(last_close, sigma_daily, 4)
        low9, c9, high9 = fan_bands(last_close, sigma_daily, 9)

        # Width at days=4
        width_4 = high1 - low1
        # Width at days=9
        width_9 = high9 - low9

        assert width_9 > width_4

    def test_z_parameter_widens_bands(self):
        """Higher z should produce wider bands."""
        last_close = 100.0
        sigma_daily = 0.02
        days_ahead = 10

        low1, c1, high1 = fan_bands(last_close, sigma_daily, days_ahead, z=1.0)
        low2, c2, high2 = fan_bands(last_close, sigma_daily, days_ahead, z=2.0)

        width_z1 = high1 - low1
        width_z2 = high2 - low2

        assert width_z2 > width_z1
