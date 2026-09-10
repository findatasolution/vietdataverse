"""Delta pass-through model for fuel price forecasting.

structural-v1 (two-stage OLS: world ~ Brent, then retail ~ Nghị định 80 formula)
was removed 2026-09-10 — it lost to random-walk in every walk-forward backtest
(skill -0.19..0.00, see git history / CLAUDE.md for the numbers) because Brent/RBOB
are only loosely correlated with the Singapore MOPS price the regulator's formula
actually uses. The delta pass-through model below, fit directly on the MOPS-based
world_avg_price MOIT itself publishes each cycle, is the only model that has ever
beaten random-walk here (skill +0.53..+0.82, p<0.01 on all three fuels — see
docs/research or CLAUDE.md for the full stats). It is now the only model in this
module.

Pure functions, stdlib + numpy only.
"""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CyclePoint:
    """One observation from a fuel price adjustment cycle.

    Attributes:
        period: Date of the cycle.
        fuel: Fuel type code (e.g., "RON95", "E5RON92", "DO005S").
        world_avg: World refined-product price (USD/barrel) MOIT publishes in the
            bulletin itself — this IS the MOPS (Mean of Platts Singapore) window
            average the regulator's formula uses, not a proxy.
        retail: Published retail price (VND/liter).
    """

    period: date
    fuel: str
    world_avg: float  # USD/barrel (MOPS, from MOIT announcement)
    retail: float  # VND/liter (published retail)


def fit_passthrough(points: list[CyclePoint]) -> float:
    """Fit k (VND/L per USD/bbl) by OLS through the origin on consecutive-cycle
    deltas: Δretail ~ k·Δworld. Points must be one fuel, sorted by period ASC.
    Raises ValueError if fewer than 4 points (i.e. <3 deltas) or zero Δworld variance."""
    if len(points) < 4:
        raise ValueError(f"fit_passthrough needs >=4 points, got {len(points)}")
    fuels = {p.fuel for p in points}
    if len(fuels) != 1:
        raise ValueError(f"fit_passthrough expects a single fuel, got {sorted(fuels)}")
    dx = [points[j].world_avg - points[j - 1].world_avg for j in range(1, len(points))]
    dy = [points[j].retail - points[j - 1].retail for j in range(1, len(points))]
    sxx = sum(x * x for x in dx)
    if sxx == 0:
        raise ValueError("zero variance in world deltas")
    return sum(x * y for x, y in zip(dx, dy)) / sxx


def predict_retail_from_world_delta(prev_retail: float, k: float,
                                    world_prev: float, world_now: float) -> float:
    """Delta pass-through prediction: prev_retail + k·(world_now − world_prev)."""
    return prev_retail + k * (world_now - world_prev)
