"""Nghị định 80/2023 base-price formula (imported-source path).

Pure functions — no I/O. Parameters are calibrated per fuel/period against the
base prices MOIT publishes each cycle (see fuel_formula_params + Plan 2 calibration).

Formula ordering (imported source, VND/L):
    cif        = (world_usd_per_bbl + freight_premium) / LITERS_PER_BARREL * usd_vnd
    import_tax = cif * import_pct
    excise     = (cif + import_tax) * excise_pct
    subtotal   = cif + import_tax + excise + business_cost_norm + profit_norm + env_vnd
    vat        = subtotal * vat_pct
    base_price = subtotal + vat
"""
from dataclasses import dataclass

LITERS_PER_BARREL = 158.987


@dataclass(frozen=True)
class FormulaParams:
    import_pct: float          # e.g. 0.10
    excise_pct: float          # 0.10 RON95 / 0.08 E5 / 0.0 diesel
    env_vnd: float             # environmental protection tax, VND/L (fixed)
    vat_pct: float             # e.g. 0.10
    business_cost_norm: float  # VND/L
    profit_norm: float         # VND/L
    freight_premium: float     # USD/barrel added to world price (freight + premium)
    import_weight_pct: float = 100.0
    domestic_weight_pct: float = 0.0


def base_price_vnd_per_liter(world_usd_per_bbl: float, usd_vnd: float, p: FormulaParams) -> float:
    """Compute the Nghị định 80 base price in VND/liter from the world refined-product
    price (USD/barrel) and the USD/VND rate."""
    cif_usd_per_liter = (world_usd_per_bbl + p.freight_premium) / LITERS_PER_BARREL
    cif_vnd = cif_usd_per_liter * usd_vnd
    import_tax = cif_vnd * p.import_pct
    excise = (cif_vnd + import_tax) * p.excise_pct
    subtotal = cif_vnd + import_tax + excise + p.business_cost_norm + p.profit_norm + p.env_vnd
    vat = subtotal * p.vat_pct
    return subtotal + vat
