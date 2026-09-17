from datetime import date
from pathlib import Path

from be.fuel.moit_parser import parse_moit

FIXTURE = Path(__file__).parent / "fixtures" / "moit_2026-01-29.html"


def _rows():
    html = FIXTURE.read_text(encoding="utf-8")
    return {r.fuel: r for r in parse_moit(html, date(2026, 1, 29))}


def test_parses_only_the_product_fuels():
    # RON95 was dropped 2026-09-15 (product scope: commercial/transport fuel).
    assert set(_rows()) == {"E5RON92", "DO005S"}


def test_world_avg_prices():
    rows = _rows()
    assert 84.0 <= rows["DO005S"].world_avg_price <= 86.0     # 85.154
    assert 71.0 <= rows["E5RON92"].world_avg_price <= 72.0    # 71.468 (RON92 basis)


def test_retail_prices_vnd_per_liter():
    rows = _rows()
    assert rows["E5RON92"].retail_price == 18339
    assert rows["DO005S"].retail_price == 18173


def test_period_and_source_set():
    rows = _rows()
    assert all(r.retail_price > 15000 for r in rows.values())


def test_e10_ron95_line_is_not_mistaken_for_another_fuel():
    # Vietnam relabelled RON95 gasoline "E10RON95-III" during the E10 rollout;
    # its retail line sits right before E5RON92's and must not leak into it.
    html = (
        "<p>Bình quân giá ... 73,582 USD/thùng xăng RON95 (tăng); "
        "71,468 USD/thùng xăng RON92 (tăng); "
        "85,154 USD/thùng dầu điêzen 0,05S (tăng).</p>"
        "<p>- Xăng E10RON95-III: không cao hơn 20.003 đồng/lít; "
        "- Xăng E5RON92: không cao hơn 19.191 đồng/lít; "
        "- Dầu điêzen 0.05S: không cao hơn 21.745 đồng/lít.</p>"
    )
    rows = {r.fuel: r for r in parse_moit(html, date(2026, 7, 9))}
    assert "RON95" not in rows
    assert rows["E5RON92"].retail_price == 19191
    assert rows["DO005S"].retail_price == 21745
