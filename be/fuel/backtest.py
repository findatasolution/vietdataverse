"""Walk-forward backtest for fuel price forecasting models.

This module implements:
1. BacktestResult: dataclass capturing horizon-specific backtest metrics
2. walk_forward: PURE horizon-1 walk-forward validation (no DB)
3. write_backtest: DB insert with upsert
4. main: orchestrator (load Silver, run backtest per fuel, write Gold, print summary)

Pure functions (testable without DB):
- walk_forward

DB functions:
- write_backtest
- main
"""
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import os

# Allow running as a plain script (python3 be/fuel/backtest.py) — put repo root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text, create_engine

from be.fuel.calibration import CyclePoint, fit_calibration, predict_retail
from be.fuel.forecast import load_silver, build_cycle_points, FX_DEFAULT, MODEL_VERSION

__all__ = ['BacktestResult', 'walk_forward', 'write_backtest', 'main']


@dataclass(frozen=True)
class BacktestResult:
    """Horizon-specific backtest metrics for a single fuel.

    Attributes:
        fuel: Fuel type code (e.g., "RON95", "E5RON92", "DO005S").
        horizon: Forecast horizon (days ahead). Currently 1 for walk-forward.
        mae: Mean absolute error (VND/liter).
        rmse: Root mean squared error (VND/liter).
        coverage: Fraction of test points inside [lo, hi] confidence interval.
        n: Number of test points (walk-forward steps).
        skill_vs_rw: Improvement over random-walk benchmark. 1.0 = perfect; 0 = tie; -1 = worse.
        model_version: Model version identifier (default "structural-v1").
    """
    fuel: str
    horizon: int
    mae: float
    rmse: float
    coverage: float
    n: int
    skill_vs_rw: float
    model_version: str = MODEL_VERSION


def walk_forward(
    points: list[CyclePoint],
    fx: float = FX_DEFAULT,
    min_train: int = 6,
    z: float = 1.28,
) -> BacktestResult:
    """Horizon-1 walk-forward backtest. PURE function (no DB).

    For each point from index min_train onwards:
    - Fit calibration on train[:i]
    - Predict test[i] using brent_avg[i]
    - Compute residual std from train
    - Build confidence interval [lo, hi]
    - Compute error and coverage
    - Compare to random-walk benchmark

    Args:
        points: List of CyclePoint (must be sorted by period ASC, single fuel type).
        fx: USD/VND exchange rate (default 26000.0).
        min_train: Minimum training points before starting test (default 6).
        z: Z-score for confidence interval (default 1.28 ≈ 80% coverage under normality).

    Returns:
        BacktestResult with mae, rmse, coverage, skill_vs_rw.

    Raises:
        ValueError: If len(points) < min_train + 2 (need >=2 test points).
    """
    n_required = min_train + 2
    if len(points) < n_required:
        raise ValueError(
            f"walk_forward requires at least {n_required} points "
            f"(min_train={min_train} + 2 test), got {len(points)}"
        )

    # Extract fuel type (all points must be same fuel)
    fuel = points[0].fuel

    # Collect errors and coverage indicators
    errors = []
    rw_errors = []
    covered_count = 0

    # Walk-forward loop: for each point from min_train onwards
    for i in range(min_train, len(points)):
        train = points[:i]
        test = points[i]

        # Fit calibration on training data
        try:
            cal = fit_calibration(train, fx)
        except ValueError:
            # Should not happen if we have >=4 train points, but skip on error
            continue

        # Predict test point using its brent_avg
        pred = predict_retail(cal, test.brent_avg, fx)

        # Compute residual std from training set
        train_preds = [predict_retail(cal, p.brent_avg, fx) for p in train]
        train_residuals = [train[j].retail - train_preds[j] for j in range(len(train))]
        resid_mean = sum(train_residuals) / len(train_residuals)
        resid_variance = sum((r - resid_mean) ** 2 for r in train_residuals) / len(train_residuals)
        resid_std = resid_variance ** 0.5

        # Confidence interval
        lo = pred - z * resid_std
        hi = pred + z * resid_std

        # Compute errors
        err = pred - test.retail
        errors.append(err)

        # Coverage
        if lo <= test.retail <= hi:
            covered_count += 1

        # Random-walk benchmark: use previous retail as prediction
        if i > 0:
            rw_pred = points[i - 1].retail
            rw_err = rw_pred - test.retail
            rw_errors.append(rw_err)

    # Compute aggregated metrics
    n_test = len(errors)
    if n_test == 0:
        raise ValueError("No test points generated (calibration failed for all windows)")

    mae = sum(abs(e) for e in errors) / n_test
    rmse = (sum(e ** 2 for e in errors) / n_test) ** 0.5
    coverage = covered_count / n_test

    # Compute skill vs random-walk
    rw_mae = sum(abs(e) for e in rw_errors) / len(rw_errors) if rw_errors else 0.0
    if rw_mae > 0:
        skill_vs_rw = 1.0 - (mae / rw_mae)
    else:
        # Degenerate: rw_mae == 0
        # If mae == 0 (model perfect), skill = 1.0
        # If mae > 0 (model worse), skill = -1.0
        skill_vs_rw = 1.0 if mae == 0.0 else -1.0

    return BacktestResult(
        fuel=fuel,
        horizon=1,
        mae=mae,
        rmse=rmse,
        coverage=coverage,
        n=n_test,
        skill_vs_rw=skill_vs_rw,
        model_version=MODEL_VERSION,
    )


def write_backtest(engine, results: list[BacktestResult], run_ts: datetime) -> int:
    """Write backtest results to fuel_backtest table with upsert.

    Uses INSERT ... ON CONFLICT (run_ts, fuel, horizon) DO UPDATE to allow re-runs.

    Args:
        engine: SQLAlchemy engine pointing to FUEL_FORECAST_DB.
        results: List of BacktestResult objects.
        run_ts: Backtest run timestamp (datetime, UTC).

    Returns:
        Number of rows written.
    """
    if not results:
        return 0

    with engine.connect() as conn:
        for result in results:
            stmt = text(
                """
                INSERT INTO fuel_backtest (
                    run_ts, fuel, horizon, mae, rmse, coverage, n, skill_vs_rw, model_version
                ) VALUES (:run_ts, :fuel, :horizon, :mae, :rmse, :coverage, :n, :skill_vs_rw, :model_version)
                ON CONFLICT (run_ts, fuel, horizon, model_version) DO UPDATE SET
                    mae = EXCLUDED.mae,
                    rmse = EXCLUDED.rmse,
                    coverage = EXCLUDED.coverage,
                    n = EXCLUDED.n,
                    skill_vs_rw = EXCLUDED.skill_vs_rw
                """
            )
            conn.execute(
                stmt,
                {
                    "run_ts": run_ts,
                    "fuel": result.fuel,
                    "horizon": result.horizon,
                    "mae": float(result.mae),
                    "rmse": float(result.rmse),
                    "coverage": float(result.coverage),
                    "n": int(result.n),
                    "skill_vs_rw": float(result.skill_vs_rw),
                    "model_version": result.model_version,
                },
            )

        conn.commit()

    return len(results)


def main():
    """Main orchestrator: load Silver, run walk-forward per fuel, write Gold, print summary."""
    # Load .env from repo root
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set in environment")

    engine = create_engine(db_url)

    # Load Silver data
    try:
        cycles, brent_daily = load_silver(engine)
    except Exception as e:
        sys.exit(f"Failed to load Silver data: {e}")

    if not cycles or not brent_daily:
        print("No data found in Silver layer; skipping backtest")
        return

    # Build cycle points
    points_by_fuel = build_cycle_points(cycles, brent_daily)

    if not points_by_fuel:
        print("No CyclePoints generated from Silver data")
        return

    # Run walk-forward for each fuel
    results = []
    run_ts = datetime.utcnow()

    print(f"\nBacktest Summary (run_ts={run_ts.isoformat()})")
    print("=" * 100)
    print(f"{'Fuel':<12} | {'N':<4} | {'MAE (VND/L)':<14} | {'RMSE':<12} | {'Coverage %':<12} | {'Skill vs RW':<12}")
    print("-" * 100)

    for fuel in sorted(points_by_fuel.keys()):
        points = points_by_fuel[fuel]

        # Skip fuels with insufficient data for walk-forward
        if len(points) < 8:  # min_train=6 + 2
            print(f"{fuel:<12} | {len(points):<4} | {'(skip)':<14} | {'-':<12} | {'-':<12} | {'-':<12}")
            continue

        # Run BOTH models: level (scenario baseline, fails the RW gate) and
        # delta-world (primary — the only formulation that beats random-walk).
        for runner, tag in ((lambda p: walk_forward(p, fx=FX_DEFAULT, min_train=6, z=1.28), "level"),
                            (lambda p: walk_forward_delta(p, min_train=6, z=1.28), "delta")):
            try:
                result = runner(points)
                results.append(result)
                print(
                    f"{fuel:<12} | {result.n:<4} | {result.mae:>14.2f} | {result.rmse:>12.2f} | "
                    f"{result.coverage * 100:>11.1f}% | {result.skill_vs_rw:>12.3f}  ({result.model_version})"
                )
            except ValueError as e:
                print(f"{fuel:<12} | {len(points):<4} | ({tag} error: {str(e)[:20]})")
                continue

    print("=" * 100)

    # Write to Gold layer
    if results:
        count = write_backtest(engine, results, run_ts)
        print(f"\nWrote {count} backtest result(s) to fuel_backtest table")
    else:
        print("\nNo backtest results generated")




DELTA_MODEL_VERSION = "delta-world-v1"


def walk_forward_delta(points: list["CyclePoint"], min_train: int = 6,
                       z: float = 1.28) -> BacktestResult:
    """Horizon-1 walk-forward of the delta pass-through model (see calibration.py):
        pred_t = retail_{t-1} + k·(world_t − world_{t-1}),  k fit on train deltas.
    world_t is the MOPS window average (known in real time only with a licensed
    Platts feed; the backtest measures end-of-window accuracy). PURE."""
    from be.fuel.calibration import fit_passthrough, predict_retail_from_world_delta

    if len(points) < min_train + 2:
        raise ValueError(
            f"walk_forward_delta needs >= {min_train + 2} points, got {len(points)}")

    abs_errs, sq_errs, covered, rw_abs = [], [], [], []
    for i in range(min_train, len(points)):
        train, test, prev = points[:i], points[i], points[i - 1]
        k = fit_passthrough(train)
        # residual std over train deltas (population)
        resids = [
            (train[j].retail - train[j - 1].retail) - k * (train[j].world_avg - train[j - 1].world_avg)
            for j in range(1, len(train))
        ]
        mean_r = sum(resids) / len(resids)
        resid_std = math.sqrt(sum((r - mean_r) ** 2 for r in resids) / len(resids))
        pred = predict_retail_from_world_delta(prev.retail, k, prev.world_avg, test.world_avg)
        lo, hi = pred - z * resid_std, pred + z * resid_std
        err = pred - test.retail
        abs_errs.append(abs(err)); sq_errs.append(err * err)
        covered.append(1.0 if lo <= test.retail <= hi else 0.0)
        rw_abs.append(abs(prev.retail - test.retail))

    n = len(abs_errs)
    mae = sum(abs_errs) / n
    rmse = math.sqrt(sum(sq_errs) / n)
    coverage = sum(covered) / n
    rw_mae = sum(rw_abs) / n
    skill = (1 - mae / rw_mae) if rw_mae > 0 else (1.0 if mae == 0 else -1.0)
    return BacktestResult(fuel=points[0].fuel, horizon=1, mae=mae, rmse=rmse,
                          coverage=coverage, n=n, skill_vs_rw=skill,
                          model_version=DELTA_MODEL_VERSION)


if __name__ == "__main__":
    main()
