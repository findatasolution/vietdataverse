"""Fuel price forecast generator — cycle points to forecast rows.

This module implements:
1. build_cycle_points: Converts published cycles + Brent daily data into CyclePoint observations
2. make_forecast_rows: Generates forecast rows from calibrated models
3. load_silver/write_forecasts: DB integration (not pure)
4. main: Orchestrator

Pure functions (testable without DB):
- build_cycle_points
- make_forecast_rows

DB functions:
- load_silver
- write_forecasts
- main
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import os
import json
from decimal import Decimal

# Allow running as a plain script (python3 be/fuel/forecast.py) — put repo root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text

from be.fuel.calibration import (
    CyclePoint,
    fit_calibration,
    predict_world,
    predict_retail,
    STANDARD_PARAMS,
)
from be.fuel.world_model import brent_window_avg, daily_log_return_sigma, fan_bands
from be.fuel.formula import base_price_vnd_per_liter

MODEL_VERSION = "structural-v1"
METHODOLOGY_VERSION = "nd80-linear-2026.07"
FX_DEFAULT = 26000.0
CYCLE_DAYS = 7
DISCLAIMER = (
    "Uoc tinh theo mo hinh phuc vu lap ngan sach; gia chinh thuc do "
    "Bo Cong Thuong cong bo; khong phai khuyen nghi dau tu."
)


def build_cycle_points(cycles: list[dict], brent_daily: list[tuple[date, float]]) -> dict[str, list[CyclePoint]]:
    """PURE. Build CyclePoint observations from published cycles and Brent daily prices.

    For each fuel, processes cycles in period order. The first cycle per fuel is used only
    as a previous-boundary reference; cycles 2+ become CyclePoints if their window has
    Brent data. Each cycle's window is (previous cycle period + 1 day) .. (current cycle period).

    Args:
        cycles: List of dicts with keys: period, fuel, world_avg_price, retail_price.
                Must be sorted by period (ascending).
        brent_daily: List of (date, close_price) tuples, sorted by date.

    Returns:
        Dict {fuel: [CyclePoint, ...]} where each fuel's points are in period order.
        Fuels with <2 cycles are excluded (no points generated).
    """
    # Group cycles by fuel, sorted by period
    by_fuel = {}
    for cycle in cycles:
        fuel = cycle["fuel"]
        if fuel not in by_fuel:
            by_fuel[fuel] = []
        by_fuel[fuel].append(cycle)

    for fuel in by_fuel:
        by_fuel[fuel].sort(key=lambda c: c["period"])

    # For each fuel, build CyclePoints
    result = {}
    for fuel, fuel_cycles in by_fuel.items():
        if len(fuel_cycles) < 2:
            continue  # Skip fuels with <2 cycles (no point to generate)

        points = []
        for i in range(1, len(fuel_cycles)):
            prev_period = fuel_cycles[i - 1]["period"]
            curr_cycle = fuel_cycles[i]
            curr_period = curr_cycle["period"]

            # Window: (prev_period + 1 day) .. (curr_period)
            window_start = prev_period + timedelta(days=1)
            window_end = curr_period

            # Try to compute brent_avg for this window
            try:
                brent_avg = brent_window_avg(brent_daily, window_start, window_end, rw_fill=None)
            except ValueError:
                # No Brent data in window; skip this cycle
                continue

            point = CyclePoint(
                period=curr_period,
                fuel=fuel,
                world_avg=float(curr_cycle["world_avg_price"]),
                retail=float(curr_cycle["retail_price"]),
                brent_avg=brent_avg,
            )
            points.append(point)

        if points:
            result[fuel] = points

    return result


def make_forecast_rows(
    points_by_fuel: dict[str, list[CyclePoint]],
    brent_daily: list[tuple[date, float]],
    run_ts: datetime,
    fx: float = FX_DEFAULT,
    horizons: int = 4,
) -> list[dict]:
    """PURE. Generate forecast rows from calibrated models.

    For each fuel with >=4 points, fits a calibration and generates forecast rows for
    horizons 1..horizons. For each horizon, computes three scenarios (low/base/high)
    using Brent fan bands.

    Args:
        points_by_fuel: Dict {fuel: [CyclePoint, ...]} (same as output from build_cycle_points).
        brent_daily: List of (date, close_price) tuples, sorted by date.
        run_ts: Forecast run timestamp (datetime, UTC).
        fx: USD/VND exchange rate (default 26000.0).
        horizons: Number of horizons to forecast (default 4).

    Returns:
        List of dicts, each with keys:
        - run_ts, fuel, target_cycle, horizon, scenario
        - point, lo, hi (VND/L, rounded to int)
        - breakdown (dict with brent_avg, world_hat, formula_vnd, calibration, fx, disclaimer)
        - model_version, methodology_version
        Total rows = sum(1 for fuel with >=4 points) * horizons * 3 scenarios.
    """
    rows = []

    if not brent_daily or not points_by_fuel:
        return rows

    # Get last observed Brent close
    sorted_daily = sorted(brent_daily, key=lambda x: x[0])
    last_brent_date = sorted_daily[-1][0]
    last_close = sorted_daily[-1][1]

    # Compute Brent volatility (can raise ValueError if <3 observations)
    try:
        sigma = daily_log_return_sigma(brent_daily)
    except ValueError:
        sigma = 0.0  # Fallback to zero volatility if insufficient data

    # For each fuel with >=4 points
    for fuel, points in points_by_fuel.items():
        if len(points) < 4:
            continue  # Skip fuels with insufficient data

        # Fit calibration
        try:
            cal = fit_calibration(points, fx)
        except ValueError:
            continue  # Skip if calibration fails

        # Last cycle period (latest point)
        last_cycle = points[-1].period

        # Generate forecasts for each horizon
        for h in range(1, horizons + 1):
            target_cycle = last_cycle + timedelta(days=h * CYCLE_DAYS)

            # Window for target cycle: (previous boundary + 1) .. (target_cycle)
            # The "previous boundary" is the period before target_cycle, which is
            # last_cycle + (h-1)*CYCLE_DAYS
            if h == 1:
                window_start = last_cycle + timedelta(days=1)
            else:
                window_start = last_cycle + timedelta(days=(h - 1) * CYCLE_DAYS + 1)
            window_end = target_cycle

            days_ahead = max(1, (target_cycle - last_brent_date).days)

            # Compute fan bands (low, base, high) for Brent
            low_b, base_b, high_b = fan_bands(last_close, sigma, days_ahead)

            # For each scenario, compute forecast
            for scenario_name, brent_scen in [
                ("low", low_b),
                ("base", base_b),
                ("high", high_b),
            ]:
                # Compute Brent average for this scenario window
                try:
                    brent_avg_scen = brent_window_avg(brent_daily, window_start, window_end, rw_fill=brent_scen)
                except ValueError:
                    # If window is entirely in the future, use rw_fill for entire window
                    brent_avg_scen = brent_scen

                # Predict retail price
                retail_hat = predict_retail(cal, brent_avg_scen, fx)
                world_hat = predict_world(cal, brent_avg_scen)

                # Compute formula (for breakdown transparency)
                formula_vnd = base_price_vnd_per_liter(world_hat, fx, STANDARD_PARAMS[fuel])

                # Build breakdown
                breakdown = {
                    "brent_avg": round(brent_avg_scen, 2),
                    "world_hat": round(world_hat, 2),
                    "formula_vnd": round(formula_vnd, 0),
                    "calibration": {
                        "alpha": round(cal.alpha, 2),
                        "beta": round(cal.beta, 4),
                        "a": round(cal.a, 2),
                        "b": round(cal.b, 4),
                    },
                    "fx": fx,
                    "disclaimer": DISCLAIMER,
                }

                row = {
                    "run_ts": run_ts,
                    "fuel": fuel,
                    "target_cycle": target_cycle,
                    "horizon": h,
                    "scenario": scenario_name,
                    "point": round(retail_hat),
                    "lo": None,  # Will be set after all three scenarios
                    "hi": None,
                    "breakdown": breakdown,
                    "model_version": MODEL_VERSION,
                    "methodology_version": METHODOLOGY_VERSION,
                }
                rows.append(row)

        # Now set lo/hi for each horizon (same lo/hi for all three scenarios of one horizon)
        for h in range(1, horizons + 1):
            h_rows = [r for r in rows if r["fuel"] == fuel and r["horizon"] == h]
            if h_rows:
                points_vals = [r["point"] for r in h_rows]
                lo = min(points_vals)
                hi = max(points_vals)
                for r in h_rows:
                    r["lo"] = lo
                    r["hi"] = hi

    return rows


def load_silver(engine) -> tuple[list[dict], list[tuple[date, float]]]:
    """Load Silver layer: fuel_price_cycle and fuel_world_daily.

    Returns:
        (cycles, brent_daily) where:
        - cycles: List of dicts with period, fuel, world_avg_price, retail_price (sorted by period, fuel).
        - brent_daily: List of (date, close) tuples for instrument='BRENT' (sorted by date).
    """
    cycles = []
    brent_daily = []

    with engine.connect() as conn:
        # Load cycles
        result = conn.execute(
            text(
                """
                SELECT period, fuel, world_avg_price, retail_price
                FROM fuel_price_cycle
                ORDER BY period, fuel
                """
            )
        )
        for row in result:
            cycles.append({
                "period": row[0],
                "fuel": row[1],
                "world_avg_price": float(row[2]),
                "retail_price": float(row[3]),
            })

        # Load Brent daily
        result = conn.execute(
            text(
                """
                SELECT period, close
                FROM fuel_world_daily
                WHERE instrument = 'BRENT'
                ORDER BY period
                """
            )
        )
        for row in result:
            brent_daily.append((row[0], float(row[1])))

    return cycles, brent_daily


def write_forecasts(engine, rows: list[dict]) -> int:
    """Write forecast rows to fuel_forecast table with upsert.

    Uses INSERT with ON CONFLICT (run_ts, fuel, target_cycle, scenario) DO UPDATE.

    Args:
        engine: SQLAlchemy engine.
        rows: List of forecast row dicts.

    Returns:
        Number of rows written.
    """
    if not rows:
        return 0

    with engine.connect() as conn:
        for row in rows:
            # Convert breakdown dict to JSON string
            breakdown_json = json.dumps(row["breakdown"])

            stmt = text(
                """
                INSERT INTO fuel_forecast (
                    run_ts, fuel, target_cycle, horizon, scenario,
                    point, lo, hi, breakdown, model_version, methodology_version
                ) VALUES (:run_ts, :fuel, :target_cycle, :horizon, :scenario,
                          :point, :lo, :hi, :breakdown, :model_version, :methodology_version)
                ON CONFLICT (run_ts, fuel, target_cycle, scenario) DO UPDATE SET
                    horizon = EXCLUDED.horizon,
                    point = EXCLUDED.point,
                    lo = EXCLUDED.lo,
                    hi = EXCLUDED.hi,
                    breakdown = EXCLUDED.breakdown,
                    model_version = EXCLUDED.model_version,
                    methodology_version = EXCLUDED.methodology_version
                """
            )
            conn.execute(
                stmt,
                {
                    "run_ts": row["run_ts"],
                    "fuel": row["fuel"],
                    "target_cycle": row["target_cycle"],
                    "horizon": row["horizon"],
                    "scenario": row["scenario"],
                    "point": row["point"],
                    "lo": row["lo"],
                    "hi": row["hi"],
                    "breakdown": breakdown_json,
                    "model_version": row["model_version"],
                    "methodology_version": row["methodology_version"],
                },
            )

        conn.commit()

    return len(rows)


def main():
    """Main orchestrator: load env, DB, Silver layer, generate and write forecasts."""
    # Load .env from repo root
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set in environment")

    # Import SQLAlchemy here to avoid issues if not in all environments
    from sqlalchemy import create_engine

    engine = create_engine(db_url)

    # Load Silver data
    try:
        cycles, brent_daily = load_silver(engine)
    except Exception as e:
        sys.exit(f"Failed to load Silver data: {e}")

    if not cycles or not brent_daily:
        print("No data found in Silver layer; skipping forecast generation")
        return

    # Build cycle points
    points_by_fuel = build_cycle_points(cycles, brent_daily)

    # Generate forecasts
    run_ts = datetime.utcnow()
    rows = make_forecast_rows(points_by_fuel, brent_daily, run_ts, fx=FX_DEFAULT, horizons=4)

    if not rows:
        print("No forecast rows generated")
        return

    # Write to Gold layer
    count = write_forecasts(engine, rows)

    # Print summary
    print(f"Forecast generation complete: {count} rows written")
    print(f"Run timestamp: {run_ts}")

    # Summary by fuel
    fuels = set(r["fuel"] for r in rows)
    for fuel in sorted(fuels):
        fuel_rows = [r for r in rows if r["fuel"] == fuel]
        fuel_points_count = len(points_by_fuel.get(fuel, []))
        h1_base = [r for r in fuel_rows if r["horizon"] == 1 and r["scenario"] == "base"]
        if h1_base:
            point = h1_base[0]["point"]
            lo = h1_base[0]["lo"]
            hi = h1_base[0]["hi"]
            print(f"  {fuel}: {fuel_points_count} historical points → T+1 base={point} VND/L [{lo}, {hi}]")
        else:
            print(f"  {fuel}: {fuel_points_count} historical points → skipped (insufficient data)")


if __name__ == "__main__":
    main()
