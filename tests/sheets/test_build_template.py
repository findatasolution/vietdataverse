"""Guards for the Google Sheets template.

Every assertion below is a regression that reached a customer. They check the
generated workbook and its formula strings — no Sheets instance needed — so
they cannot prove the formulas evaluate; README "Verifying a rebuild" covers
the manual check in a real Sheet.
"""
import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "build_template", ROOT / "integrations/google-sheets/build_template.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)


@pytest.fixture(scope="module")
def wb():
    return bt.build_workbook()


def all_formulas(wb):
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    yield ws.title, cell.coordinate, cell.value


def test_refresh_cell_is_part_of_the_url():
    # IMPORTDATA caches on the exact URL. The cover tells the customer to bump
    # C7 to refresh; that only works if C7 is in the URL. 724b86677 dropped it
    # when collapsing nine formulas into one, and the refresh cell went dead.
    formula = bt.raw_formula()
    assert "_r=" in formula
    assert f"'{bt.COVER}'!{bt.REFRESH_CELL}" in formula


def test_period_comes_from_the_cover():
    # The raw tab is hidden, so period cannot be "edit the formula" any more.
    assert f"'{bt.COVER}'!{bt.PERIOD_CELL}" in bt.raw_formula()


def test_locale_is_forced():
    assert '"en_US"' in bt.raw_formula()


def test_key_cell_ships_empty(wb):
    # The live template is shared anyone-with-link; a key in C6 is published
    # to every copier. Found there 2026-09-29 and again 2026-10-03.
    assert wb[bt.COVER]["C6"].value is None


def test_raw_tab_is_hidden(wb):
    # Customers saw headers c1..c8 and serial dates and asked what it was.
    assert wb[bt.RAW].sheet_state == "hidden"
    visible = [ws.title for ws in wb.worksheets if ws.sheet_state == "visible"]
    assert visible[:2] == [bt.COVER, bt.DASH]


def test_one_network_call_in_the_whole_workbook(wb):
    calls = [f for f in all_formulas(wb) if "IMPORTDATA(" in f[2]]
    assert [(t, c) for t, c, _ in calls] == [(bt.RAW, "A1")]


def test_no_query_over_the_raw_tab(wb):
    # QUERY types each column by majority and nulls the minority; the raw tab
    # mixes nine datasets, so every GDP sector name came back blank.
    for title, coord, formula in all_formulas(wb):
        if bt.RAW in formula:
            assert "QUERY(" not in formula, (title, coord)


def test_no_excel_dynamic_array_functions(wb):
    # Written bare into an .xlsx these did not survive the import: the old
    # freshness cell (SORT/FILTER) showed "—" forever, even with data loaded.
    banned = re.compile(r"\b(SORT|SORTN|LET|XLOOKUP|UNIQUE|SEQUENCE|LAMBDA)\(")
    for title, coord, formula in all_formulas(wb):
        assert not banned.search(formula), (title, coord, formula)


@pytest.mark.parametrize("spec", [d for d in bt.DATASETS], ids=lambda d: d["id"])
def test_dates_leave_the_formula_as_text(wb, spec):
    # IMPORTDATA turns 2025-10-03 into the serial 45933. A pre-applied cell
    # format did not survive the import past the first rows, so customers saw
    # 46155 where a date belonged. The value itself must already be the label.
    header, _col, kind, _fmt = spec["cols"][0]
    formula = wb[spec["tab"]].cell(row=bt.DATA_ROW, column=1).value
    if kind == "date":
        assert 'TEXT(' in formula and '"yyyy-mm-dd"' in formula
    elif kind == "month":
        assert 'TEXT(' in formula and '"yyyy-mm"' in formula


@pytest.mark.parametrize("spec", [d for d in bt.DATASETS], ids=lambda d: d["id"])
def test_every_tab_surfaces_the_refusal_reason(wb, spec):
    # A tab that goes blank on refusal looks like a broken file (2026-09-29).
    formula = wb[spec["tab"]].cell(row=bt.DATA_ROW, column=1).value
    assert f"'{bt.RAW}'!A1" in formula


def test_gdp_sectors_are_translated_not_dropped(wb):
    ws = wb["GDP"]
    sector = [c for c in ws[bt.DATA_ROW] if isinstance(c.value, str) and "SUBSTITUTE(" in c.value]
    assert len(sector) == 1
    for src, label in bt.SECTORS:
        assert f'"{src}", "{label}"' in sector[0].value


def test_always_empty_api_columns_are_not_shown(wb):
    # fx buy/sell and GDP level are never filled by the API; an always-empty
    # column reads as broken data.
    assert [c.value for c in wb["Tỷ giá"][bt.DATA_ROW - 1] if c.value] == ["Ngày", "Tỷ giá trung tâm"]
    assert "GDP (tỷ VND)" not in [c.value for c in wb["GDP"][bt.DATA_ROW - 1]]


def test_dashboard_reads_existing_columns(wb):
    # A KPI pointing at a renamed header would silently show "—".
    for label, ds, header, *_ in bt.KPIS:
        bt._col_of(bt.BY_ID[ds], header)
    assert len(wb[bt.DASH]._charts) >= 6
