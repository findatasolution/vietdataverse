"""CSV export shape, without a database or network.

`format=csv` is what makes a dataset usable from Google Sheets IMPORTDATA and
from a plain HTTP GET in Excel — neither can parse our JSON. Until 2026-09-23
only /gold offered it, which is why DESIGN.md §13.7 said not to promise Sheets
support for anything else.

Two converters exist because the API answers two shapes: market_data.py returns
parallel arrays keyed by column name, the macro endpoints return a list of
records. Both are loaded here as pure functions, so these tests need no DB.

The /gold header check is the important one: `date,buy_price,sell_price` is
already inside other people's spreadsheet formulas. Renaming those columns
would silently break every sheet built on them.
"""
import ast
import csv
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class _Response:
    """Stand-in for fastapi.responses.Response — records what was written."""
    def __init__(self, content=b"", media_type=None, headers=None):
        self.content = content
        self.media_type = media_type
        self.headers = headers or {}

    @property
    def text(self):
        return self.content.decode("utf-8")


def load_definitions(path, names, namespace):
    tree = ast.parse(Path(path).read_text())
    selected = []
    for node in tree.body:
        name = getattr(node, "name", None)
        if isinstance(node, ast.Assign):
            name = getattr(node.targets[0], "id", None)
        if name in names:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                node.decorator_list = []
            selected.append(node)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), "exec"), namespace)


def parse_csv(response):
    return list(csv.reader(io.StringIO(response.text)))


class ColumnCsvTests(unittest.TestCase):
    def setUp(self):
        self.ns = {"Response": _Response, "csv": csv, "io": io}
        load_definitions(ROOT / "be/routers/market_data.py",
                         {"_csv_response", "_columns_to_csv"}, self.ns)

    def test_dates_column_leads_and_is_singular(self):
        out = parse_csv(self.ns["_columns_to_csv"](
            {"buy_prices": [1, 2], "dates": ["2026-01-01", "2026-01-02"]}))
        self.assertEqual(out[0], ["date", "buy_prices"])
        self.assertEqual(out[1], ["2026-01-01", "1"])

    def test_gold_keeps_its_published_headers(self):
        """These three names are in other people's IMPORTDATA formulas."""
        out = parse_csv(self.ns["_columns_to_csv"](
            {"dates": ["2026-01-01"], "buy_prices": [100], "sell_prices": [102]},
            rename={"dates": "date", "buy_prices": "buy_price", "sell_prices": "sell_price"}))
        self.assertEqual(out[0], ["date", "buy_price", "sell_price"])
        self.assertEqual(out[1], ["2026-01-01", "100", "102"])

    def test_ragged_arrays_do_not_shift_rows(self):
        """A short series truncates the table instead of raising IndexError.

        Emitting a half-row would silently misalign every column after it —
        worse than emitting fewer rows.
        """
        out = parse_csv(self.ns["_columns_to_csv"](
            {"dates": ["a", "b", "c"], "x": [1, 2]}))
        self.assertEqual(len(out), 3)          # header + 2 rows
        self.assertEqual(out[-1], ["b", "2"])

    def test_non_list_fields_are_ignored(self):
        out = parse_csv(self.ns["_columns_to_csv"](
            {"dates": ["a"], "x": [1], "period": "7d", "count": 1}))
        self.assertEqual(out[0], ["date", "x"])

    def test_empty_payload_is_empty_not_an_error(self):
        self.assertEqual(self.ns["_columns_to_csv"]({}).text, "")


class RecordCsvTests(unittest.TestCase):
    def setUp(self):
        self.ns = {"Response": _Response, "csv": csv, "io": io}
        load_definitions(ROOT / "be/routers/vn30_data.py", {"_records_to_csv"}, self.ns)

    def test_header_from_first_record(self):
        out = parse_csv(self.ns["_records_to_csv"](
            [{"period": "2026-01", "yoy_pct": 3.2}, {"period": "2026-02", "yoy_pct": 3.4}]))
        self.assertEqual(out[0], ["period", "yoy_pct"])
        self.assertEqual(out[2], ["2026-02", "3.4"])

    def test_missing_key_writes_a_blank_cell(self):
        out = parse_csv(self.ns["_records_to_csv"](
            [{"a": 1, "b": 2}, {"a": 3}]))
        self.assertEqual(out[2], ["3", ""])

    def test_no_records_is_empty_not_an_error(self):
        self.assertEqual(self.ns["_records_to_csv"]([]).text, "")


if __name__ == "__main__":
    unittest.main()
