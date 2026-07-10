from be.fuel.formula import base_price_vnd_per_liter, FormulaParams, LITERS_PER_BARREL

PARAMS_RON95 = FormulaParams(
    import_pct=0.10, excise_pct=0.10, env_vnd=2000.0, vat_pct=0.10,
    business_cost_norm=1050.0, profit_norm=300.0, freight_premium=2.5,
    import_weight_pct=100.0, domestic_weight_pct=0.0,
)


def test_liters_per_barrel_constant():
    assert abs(LITERS_PER_BARREL - 158.987) < 1e-6


def test_units_and_positive():
    price = base_price_vnd_per_liter(73.582, 26000.0, PARAMS_RON95)
    # Sanity: a plausible VN pump base-price band (VND/L)
    assert 15000 < price < 35000


def test_monotonic_in_world_price():
    lo = base_price_vnd_per_liter(70.0, 26000.0, PARAMS_RON95)
    hi = base_price_vnd_per_liter(90.0, 26000.0, PARAMS_RON95)
    assert hi > lo


def test_monotonic_in_fx():
    lo = base_price_vnd_per_liter(73.582, 25000.0, PARAMS_RON95)
    hi = base_price_vnd_per_liter(73.582, 27000.0, PARAMS_RON95)
    assert hi > lo
