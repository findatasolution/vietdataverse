"""Guards for the Google Sheets template's formulas.

Both regressions below reached a customer. They are formula strings, so a
string-level test is the whole check — no Sheets instance needed.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "build_template", ROOT / "integrations/google-sheets/build_template.py")
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)


def test_refresh_cell_is_part_of_the_url():
    # IMPORTDATA caches on the exact URL. The cover tells the customer to bump
    # C7 to refresh; that only works if C7 is in the URL. 724b86677 dropped it
    # when collapsing nine formulas into one, and the refresh cell went dead.
    formula = bt.raw_formula()
    assert "_r=" in formula
    assert f"'{bt.COVER}'!{bt.REFRESH_CELL}" in formula


def test_locale_is_forced():
    assert '"en_US"' in bt.raw_formula()


def test_dataset_tab_surfaces_the_refusal_reason():
    # The reason (quota spent, bad key, no key) is printed only in the raw tab.
    # A visible tab that goes blank on refusal looks like a broken file — the
    # exact report of 2026-09-29. It must fall back to the raw tab's message.
    formula = bt.query_formula("gold", 3)
    assert f"'{bt.RAW}'!A1" in formula
    assert "QUERY(" in formula
