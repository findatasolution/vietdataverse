from datetime import date
from pathlib import Path

from be.fuel.moit_parser import parse_moit

FIXTURE = Path(__file__).parent / "fixtures" / "moit_2026-01-29.html"


def _rows():
    html = FIXTURE.read_text(encoding="utf-8")
    return {r.fuel: r for r in parse_moit(html, date(2026, 1, 29))}


def test_parses_three_core_fuels():
    rows = _rows()
    assert {"RON95", "E5RON92", "DO005S"} <= set(rows)


def test_world_avg_prices():
    rows = _rows()
    assert 73.0 <= rows["RON95"].world_avg_price <= 74.0      # 73.582
    assert 84.0 <= rows["DO005S"].world_avg_price <= 86.0     # 85.154
    assert 71.0 <= rows["E5RON92"].world_avg_price <= 72.0    # 71.468 (RON92 basis)


def test_retail_prices_vnd_per_liter():
    rows = _rows()
    assert rows["RON95"].retail_price == 18845
    assert rows["E5RON92"].retail_price == 18339
    assert rows["DO005S"].retail_price == 18173


def test_period_and_source_set():
    rows = _rows()
    assert all(r.retail_price > 15000 for r in rows.values())
