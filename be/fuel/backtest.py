"""Walk-forward backtest for the fuel price delta pass-through model.

structural-v1 removed 2026-09-10 (see calibration.py docstring) — this module now
only validates delta-world-v1, the sole surviving model.

Pure functions (testable without DB):
- walk_forward_delta

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

from be.fuel.calibration import CyclePoint, fit_passthrough, predict_retail_from_world_delta
from be.fuel.forecast import load_silver, build_cycle_points

__all__ = ['BacktestResult', 'walk_forward_delta', 'write_backtest', 'main']

MODEL_VERSION = "delta-world-v1"


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
            Equivalent to 1 - MASE (mean absolute scaled error, Hyndman & Koehler 2006) —
            MASE < 1 (skill > 0) means the model beats the naive one-step forecast.
        model_version: Model version identifier.
    """
    fuel: str
    horizon: int
    mae: float
    rmse: float
    coverage: float
    n: int
    skill_vs_rw: float
    model_version: str = MODEL_VERSION


def walk_forward_delta(points: list["CyclePoint"], min_train: int = 6,
                       z: float = 1.28) -> BacktestResult:
    """Horizon-1 walk-forward of the delta pass-through model:
        pred_t = retail_{t-1} + k·(world_t − world_{t-1}),  k fit on train deltas.
    world_t is the MOPS window average MOIT itself publishes each cycle — this
    backtest measures end-of-window (ex-post) accuracy of the pass-through formula,
    not a pre-announcement forecast (see forecast.py for why the live forecaster
    cannot use this same world_t). PURE — no DB."""
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
                          model_version=MODEL_VERSION)


def write_backtest(engine, results: list[BacktestResult], run_ts: datetime) -> int:
    """Write backtest results to fuel_backtest table with upsert.

    Uses INSERT ... ON CONFLICT (run_ts, fuel, horizon, model_version) DO UPDATE to
    allow re-runs.
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
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set in environment")

    engine = create_engine(db_url)

    try:
        cycles = load_silver(engine)
    except Exception as e:
        sys.exit(f"Failed to load Silver data: {e}")

    if not cycles:
        print("No data found in Silver layer; skipping backtest")
        return

    points_by_fuel = build_cycle_points(cycles)

    if not points_by_fuel:
        print("No CyclePoints generated from Silver data")
        return

    results = []
    run_ts = datetime.utcnow()

    print(f"\nBacktest Summary (run_ts={run_ts.isoformat()})")
    print("=" * 100)
    print(f"{'Fuel':<12} | {'N':<4} | {'MAE (VND/L)':<14} | {'RMSE':<12} | {'Coverage %':<12} | {'Skill vs RW':<12}")
    print("-" * 100)

    for fuel in sorted(points_by_fuel.keys()):
        points = points_by_fuel[fuel]

        if len(points) < 8:  # min_train=6 + 2
            print(f"{fuel:<12} | {len(points):<4} | {'(skip)':<14} | {'-':<12} | {'-':<12} | {'-':<12}")
            continue

        try:
            result = walk_forward_delta(points, min_train=6, z=1.28)
            results.append(result)
            print(
                f"{fuel:<12} | {result.n:<4} | {result.mae:>14.2f} | {result.rmse:>12.2f} | "
                f"{result.coverage * 100:>11.1f}% | {result.skill_vs_rw:>12.3f}  ({result.model_version})"
            )
        except ValueError as e:
            print(f"{fuel:<12} | {len(points):<4} | (error: {str(e)[:40]})")
            continue

    print("=" * 100)

    if results:
        count = write_backtest(engine, results, run_ts)
        print(f"\nWrote {count} backtest result(s) to fuel_backtest table")
    else:
        print("\nNo backtest results generated")


if __name__ == "__main__":
    main()
