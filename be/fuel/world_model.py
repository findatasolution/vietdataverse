"""World model: Brent oil price analysis and random-walk fan bands.

Pure-function module for:
- Computing Brent averages over calendar windows with optional forward-fill
- Volatility (log-return std-dev)
- Random-walk confidence bands (geometric)
"""
from datetime import date, timedelta
import math


def brent_window_avg(daily: list[tuple[date, float]], window_start: date, window_end: date,
                     rw_fill: float | None = None) -> float:
    """Average Brent close over calendar window [window_start, window_end] inclusive.

    Uses only observations inside the window. Missing days inside the window are simply
    not counted (trading gaps) EXCEPT: if rw_fill is not None, every day in the window
    AFTER the last observed date in `daily` (i.e. future days not yet observed) is
    counted at value rw_fill.

    Args:
        daily: List of (date, close_price) tuples, sorted by date.
        window_start: Start of window (inclusive).
        window_end: End of window (inclusive).
        rw_fill: Optional fill value for future days (after last observed).

    Returns:
        Arithmetic mean of prices in window (including filled future days if applicable).

    Raises:
        ValueError: If window contains zero observed days and rw_fill is None.
    """
    # Filter observations inside window
    observed = [
        price for d, price in daily
        if window_start <= d <= window_end
    ]

    # If we have observed data, find the last date
    if observed:
        last_observed_date = None
        for d, price in daily:
            if window_start <= d <= window_end:
                last_observed_date = d

        # Count future days (after last observation, before window_end) to fill
        future_days = 0
        if rw_fill is not None and last_observed_date is not None:
            current_date = last_observed_date + timedelta(days=1)
            while current_date <= window_end:
                future_days += 1
                current_date += timedelta(days=1)

        # Compute average
        total = sum(observed)
        count = len(observed)
        if future_days > 0:
            total += rw_fill * future_days
            count += future_days

        return total / count
    else:
        # No observed data in window
        if rw_fill is None:
            raise ValueError("Window contains zero observed days and rw_fill is None")

        # All days in window are filled
        total_days = (window_end - window_start).days + 1
        return rw_fill


def daily_log_return_sigma(daily: list[tuple[date, float]]) -> float:
    """Std-dev (population, i.e. /n) of log returns ln(p_t/p_{t-1}) over consecutive
    observations sorted by date.

    Args:
        daily: List of (date, close_price) tuples.

    Returns:
        Population standard deviation of log returns.

    Raises:
        ValueError: If fewer than 3 observations (< 2 log returns).
    """
    if len(daily) < 3:
        raise ValueError(f"Need at least 3 observations for log returns; got {len(daily)}")

    # Sort by date to ensure correct order
    sorted_daily = sorted(daily, key=lambda x: x[0])

    # Compute log returns
    log_returns = []
    for i in range(1, len(sorted_daily)):
        prev_price = sorted_daily[i - 1][1]
        curr_price = sorted_daily[i][1]
        log_return = math.log(curr_price / prev_price)
        log_returns.append(log_return)

    # Compute mean of log returns
    mean_return = sum(log_returns) / len(log_returns)

    # Compute population variance (divide by n, not n-1)
    variance = sum((r - mean_return) ** 2 for r in log_returns) / len(log_returns)

    # Return population std-dev
    return math.sqrt(variance)


def fan_bands(last_close: float, sigma_daily: float, days_ahead: int, z: float = 1.0) -> tuple[float, float, float]:
    """Random-walk fan: geometric confidence bands.

    Computes base (= last_close), low and high bands using geometric Brownian motion
    approximation:
    - low  = last_close * exp(-z * sigma_daily * sqrt(days_ahead))
    - high = last_close * exp(+z * sigma_daily * sqrt(days_ahead))

    Args:
        last_close: Current (or last observed) price.
        sigma_daily: Daily volatility (std-dev of log returns).
        days_ahead: Number of days ahead to forecast (must be >= 1).
        z: Number of standard deviations (default 1.0 for ~68% confidence).

    Returns:
        Tuple (low, base, high) where base = last_close.

    Raises:
        ValueError: If days_ahead < 1 or last_close <= 0.
    """
    if days_ahead < 1:
        raise ValueError(f"days_ahead must be >= 1; got {days_ahead}")
    if last_close <= 0:
        raise ValueError(f"last_close must be > 0; got {last_close}")

    base = last_close
    exponent = z * sigma_daily * math.sqrt(days_ahead)
    low = last_close * math.exp(-exponent)
    high = last_close * math.exp(exponent)

    return (low, base, high)
