"""Fuel price forecast generator — cycle points to forecast rows.

structural-v1 (Brent/RBOB-proxied Nghị định 80 formula) was removed 2026-09-10 —
it lost to random-walk in backtest (see calibration.py docstring), so it was never
honest to use it to generate the live `fuel_forecast` rows either, even though it
was the only model actually wired into this file before this rewrite.

This file now generates delta-world-v1 forecasts. That model needs a Δworld input,
and the real one (next cycle's MOPS average) isn't known ahead of the MOIT
announcement without a licensed Platts feed (see BACKLOG.md — not pursued yet, no
free public access exists per S&P Global's own API accreditation requirement).
Rather than resurrect the Brent proxy that already failed once, forecasts here are
**world-conditional scenarios**, not point predictions: "if world price does X,
retail does k·X" for three illustrative Δworld draws (low/base/high) sized from
the historical cycle-to-cycle volatility of world_avg itself, under a random-walk
assumption on world price (spread grows with sqrt(horizon), same logic as an
ordinary random-walk forecast fan — see Hyndman & Athanasopoulos, "Forecasting:
Principles and Practice", ch. on prediction intervals). This is deliberately less
impressive-looking than a single point forecast, but it is the honest thing this
data supports without a paid feed.

Pure functions (testable without DB):
- build_cycle_points
- make_forecast_rows

DB functions:
- load_silver
- write_forecasts
- main
"""
import math
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import os
import json

# Allow running as a plain script (python3 be/fuel/forecast.py) — put repo root on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import text

from be.fuel.calibration import CyclePoint, fit_passthrough, predict_retail_from_world_delta

MODEL_VERSION = "delta-world-v1"
METHODOLOGY_VERSION = "delta-passthrough-2026.09"
CYCLE_DAYS = 7  # fallback only when <2 cycles are available to measure a real gap from
DISCLAIMER = (
    "World-conditional scenario, not a point forecast: assumes a Delta world price "
    "move, does not predict what that move will be (no licensed real-time MOPS/"
    "Platts feed). Uoc tinh phuc vu lap ngan sach; gia chinh thuc do Bo Cong Thuong "
    "cong bo; khong phai khuyen nghi dau tu."
)


def build_cycle_points(cycles: list[dict]) -> dict[str, list[CyclePoint]]:
    """PURE. Build CyclePoint observations from published cycles.

    Args:
        cycles: List of dicts with keys: period, fuel, world_avg_price, retail_price.
                Must be sorted by period (ascending) — see load_silver.

    Returns:
        Dict {fuel: [CyclePoint, ...]}. Fuels with <2 cycles are excluded (need at
        least one delta).
    """
    by_fuel: dict[str, list[dict]] = {}
    for cycle in cycles:
        by_fuel.setdefault(cycle["fuel"], []).append(cycle)

    for fuel in by_fuel:
        by_fuel[fuel].sort(key=lambda c: c["period"])

    result = {}
    for fuel, fuel_cycles in by_fuel.items():
        if len(fuel_cycles) < 2:
            continue
        result[fuel] = [
            CyclePoint(
                period=c["period"],
                fuel=fuel,
                world_avg=float(c["world_avg_price"]),
                retail=float(c["retail_price"]),
            )
            for c in fuel_cycles
        ]
    return result


def _population_std(xs: list[float]) -> float:
    n = len(xs)
    mean = sum(xs) / n
    return math.sqrt(sum((x - mean) ** 2 for x in xs) / n)


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def _estimate_cycle_days(points: list[CyclePoint], window: int = 6) -> int:
    """Median gap (days) between the last `window` cycles. The real MOIT cadence
    has moved between ~7 and ~14 days over this dataset's history (see CLAUDE.md
    "Fuel (domestic) crawl") — CYCLE_DAYS used to be a hardcoded 7, which silently
    mislabeled target_cycle dates by ~2x once the cadence shifted. Recent-windowed
    median instead of a fixed constant self-corrects when cadence shifts again."""
    recent = points[-(window + 1):]
    gaps = [(recent[i + 1].period - recent[i].period).days for i in range(len(recent) - 1)]
    return round(_median(gaps)) if gaps else CYCLE_DAYS


def make_forecast_rows(
    points_by_fuel: dict[str, list[CyclePoint]],
    run_ts: datetime,
    horizons: int = 4,
    z: float = 1.28,
) -> list[dict]:
    """PURE. Generate world-conditional scenario forecast rows.

    For each fuel with >=4 points, fits k (delta pass-through) on ALL available
    points (not a train/test split — this is the deployed model, not a backtest;
    see backtest.py for out-of-sample validation) and generates 3 world-price
    scenarios (low/base/high) per horizon:
        Δworld_scenario = {-1, 0, +1} * z * sigma_world * sqrt(horizon)
    where sigma_world is the population std-dev of historical cycle-to-cycle
    Δworld_avg (random-walk-on-world assumption — spread grows with sqrt(h)).
    point = predict_retail_from_world_delta(last.retail, k, 0, Δworld_scenario).

    lo/hi per horizon = min/max across the 3 scenario points (NOT further widened
    by the pass-through residual std — that uncertainty is reported separately in
    `breakdown.resid_std` for transparency, not folded into lo/hi, since lo/hi
    here already represents "what if world moves this much", a different question
    than "how much does the formula itself scatter around a known Δworld").

    Returns:
        List of dicts, each with keys: run_ts, fuel, target_cycle, horizon,
        scenario, point, lo, hi, breakdown, model_version, methodology_version.
    """
    rows = []

    for fuel, points in points_by_fuel.items():
        if len(points) < 4:
            continue

        try:
            k = fit_passthrough(points)
        except ValueError:
            continue

        world_deltas = [points[j].world_avg - points[j - 1].world_avg for j in range(1, len(points))]
        retail_deltas = [points[j].retail - points[j - 1].retail for j in range(1, len(points))]
        resids = [retail_deltas[j] - k * world_deltas[j] for j in range(len(world_deltas))]
        resid_std = _population_std(resids)
        sigma_world = _population_std(world_deltas)

        last = points[-1]
        cycle_days = _estimate_cycle_days(points)

        for h in range(1, horizons + 1):
            target_cycle = last.period + timedelta(days=h * cycle_days)
            world_shift = z * sigma_world * math.sqrt(h)

            h_points = {}
            for scenario_name, dworld in (("low", -world_shift), ("base", 0.0), ("high", world_shift)):
                point = predict_retail_from_world_delta(last.retail, k, 0.0, dworld)
                h_points[scenario_name] = round(point)

            lo, hi = min(h_points.values()), max(h_points.values())

            for scenario_name, point in h_points.items():
                rows.append({
                    "run_ts": run_ts,
                    "fuel": fuel,
                    "target_cycle": target_cycle,
                    "horizon": h,
                    "scenario": scenario_name,
                    "point": point,
                    "lo": lo,
                    "hi": hi,
                    "breakdown": {
                        "k_vnd_per_usd_bbl": round(k, 2),
                        "assumed_world_delta_usd_bbl": round(
                            {"low": -world_shift, "base": 0.0, "high": world_shift}[scenario_name], 2
                        ),
                        "resid_std_vnd_l": round(resid_std, 1),
                        "sigma_world_usd_bbl": round(sigma_world, 3),
                        "cycle_days_used": cycle_days,
                        "last_known_cycle": last.period.isoformat(),
                        "last_known_retail": last.retail,
                        "disclaimer": DISCLAIMER,
                    },
                    "model_version": MODEL_VERSION,
                    "methodology_version": METHODOLOGY_VERSION,
                })

    return rows


def load_silver(engine) -> list[dict]:
    """Load Silver layer: fuel_price_cycle.

    Returns:
        List of dicts with period, fuel, world_avg_price, retail_price (sorted by
        period, fuel).
    """
    cycles = []
    with engine.connect() as conn:
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
    return cycles


def write_forecasts(engine, rows: list[dict]) -> int:
    """Write forecast rows to fuel_forecast table with upsert."""
    if not rows:
        return 0

    with engine.connect() as conn:
        for row in rows:
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
    dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set in environment")

    from sqlalchemy import create_engine

    engine = create_engine(db_url)

    try:
        cycles = load_silver(engine)
    except Exception as e:
        sys.exit(f"Failed to load Silver data: {e}")

    if not cycles:
        print("No data found in Silver layer; skipping forecast generation")
        return

    points_by_fuel = build_cycle_points(cycles)

    run_ts = datetime.utcnow()
    rows = make_forecast_rows(points_by_fuel, run_ts, horizons=4)

    if not rows:
        print("No forecast rows generated")
        return

    count = write_forecasts(engine, rows)

    print(f"Forecast generation complete: {count} rows written")
    print(f"Run timestamp: {run_ts}")

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
