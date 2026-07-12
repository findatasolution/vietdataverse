"""Two-stage OLS calibration for fuel price prediction.

This module implements:
1. Simple OLS regression (_ols) to fit linear relationships
2. Two-stage calibration (fit_calibration) that:
   - Stage 1: world_avg ~ brent_avg
   - Stage 2: retail ~ formula_vnd(predicted_world)

The second stage absorbs regulator damping (b<1) and any cost-norm miscalibration.

Pure functions, stdlib only.
"""
from dataclasses import dataclass
from datetime import date
from be.fuel.formula import FormulaParams, base_price_vnd_per_liter

# Standard fuel parameters per regulation (Nghị định 80/2023)
STANDARD_PARAMS = {
    "RON95": FormulaParams(
        import_pct=0.10,
        excise_pct=0.10,
        env_vnd=2000.0,
        vat_pct=0.10,
        business_cost_norm=1050.0,
        profit_norm=300.0,
        freight_premium=2.5,
    ),
    "E5RON92": FormulaParams(
        import_pct=0.10,
        excise_pct=0.08,
        env_vnd=1900.0,
        vat_pct=0.10,
        business_cost_norm=1050.0,
        profit_norm=300.0,
        freight_premium=2.5,
    ),
    "DO005S": FormulaParams(
        import_pct=0.10,
        excise_pct=0.0,
        env_vnd=1000.0,
        vat_pct=0.10,
        business_cost_norm=1000.0,
        profit_norm=300.0,
        freight_premium=3.0,
    ),
}


@dataclass(frozen=True)
class CyclePoint:
    """One observation from a fuel price adjustment cycle.

    Attributes:
        period: Date of the cycle (usually month start).
        fuel: Fuel type code (e.g., "RON95", "E5RON92", "DO005S").
        world_avg: Published world refined-product price (USD/barrel) from MOIT.
        retail: Published retail retail price (VND/liter).
        brent_avg: Brent crude price averaged over the cycle window (USD/barrel).
    """

    period: date
    fuel: str
    world_avg: float  # USD/barrel (from MOIT announcement)
    retail: float  # VND/liter (published retail)
    brent_avg: float  # USD/barrel (Brent averaged over cycle window)


@dataclass(frozen=True)
class FuelCalibration:
    """Fitted two-stage OLS calibration for a single fuel type.

    Attributes:
        fuel: Fuel type code.
        alpha, beta: Stage 1 parameters. world_hat = alpha + beta * brent_avg.
        a, b: Stage 2 parameters. retail_hat = a + b * formula_vnd(world_hat).
               b < 1 indicates regulator damping.
    """

    fuel: str
    alpha: float
    beta: float
    a: float
    b: float


def _ols(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Closed-form OLS regression: fit y = intercept + slope * x.

    Args:
        xs: List of x values (predictor).
        ys: List of y values (response).

    Returns:
        (intercept, slope) tuple.

    Raises:
        ValueError: If len(xs) < 2 or xs have zero variance.
    """
    if len(xs) < 2:
        raise ValueError("_ols requires at least 2 points")

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    # Compute variance and covariance
    var_x = sum((x - mean_x) ** 2 for x in xs) / n
    cov_xy = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n

    if var_x == 0:
        raise ValueError("xs have zero variance (cannot fit OLS)")

    slope = cov_xy / var_x
    intercept = mean_y - slope * mean_x

    return intercept, slope


def fit_calibration(points: list[CyclePoint], fx: float) -> FuelCalibration:
    """Fit a two-stage OLS calibration for fuel price prediction.

    Stage 1: OLS world_avg ~ brent_avg
    Stage 2: OLS retail ~ base_price_vnd_per_liter(world_avg, fx, standard_params)

    Args:
        points: List of CyclePoint observations (all must have the same fuel).
        fx: USD/VND exchange rate.

    Returns:
        FuelCalibration with (alpha, beta, a, b).

    Raises:
        ValueError: If len(points) < 4 or points contain mixed fuel types.
    """
    if len(points) < 4:
        raise ValueError("fit_calibration requires at least 4 points")

    # Verify all points are for the same fuel
    fuels = set(p.fuel for p in points)
    if len(fuels) != 1:
        raise ValueError(f"All points must use a single fuel, got {fuels}")

    fuel = points[0].fuel

    # Stage 1: world_avg ~ brent_avg
    brent_avgs = [p.brent_avg for p in points]
    world_avgs = [p.world_avg for p in points]
    alpha, beta = _ols(brent_avgs, world_avgs)

    # Stage 2: retail ~ formula_vnd(world_avg, fx, standard_params[fuel])
    # Use OBSERVED world_avg, not predicted world_hat
    params = STANDARD_PARAMS[fuel]
    formula_vnds = [base_price_vnd_per_liter(p.world_avg, fx, params) for p in points]
    retails = [p.retail for p in points]
    a, b = _ols(formula_vnds, retails)

    return FuelCalibration(fuel=fuel, alpha=alpha, beta=beta, a=a, b=b)


def predict_world(cal: FuelCalibration, brent_avg: float) -> float:
    """Predict world refined-product price from Brent using stage-1 fit.

    Args:
        cal: FuelCalibration.
        brent_avg: Brent crude price (USD/barrel).

    Returns:
        Predicted world price (USD/barrel).
    """
    return cal.alpha + cal.beta * brent_avg


def predict_retail(cal: FuelCalibration, brent_avg: float, fx: float) -> float:
    """Predict retail fuel price from Brent using two-stage fit.

    Args:
        cal: FuelCalibration.
        brent_avg: Brent crude price (USD/barrel).
        fx: USD/VND exchange rate.

    Returns:
        Predicted retail price (VND/liter).
    """
    # Step 1: predict world from brent
    world_hat = predict_world(cal, brent_avg)

    # Step 2: compute formula_vnd from predicted world
    params = STANDARD_PARAMS[cal.fuel]
    formula_vnd = base_price_vnd_per_liter(world_hat, fx, params)

    # Step 3: predict retail from formula_vnd
    return cal.a + cal.b * formula_vnd
