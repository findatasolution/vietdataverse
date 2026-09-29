"""Build the Google Sheets template: copy the file, paste a key, done.

**One API call feeds all nine tabs.** A hidden `_raw` tab holds a single
IMPORTDATA against `/api/v1/excel/refresh-data?format=csv`, which returns every
dataset stacked; each visible tab pulls its own rows out of that tab with
QUERY — a pure spreadsheet function that costs no network.

That structure is the whole point. Measured on a real customer 2026-09-29: the
previous design, nine live IMPORTDATA formulas, made **315 calls in 2.7 days**
(116/day, 03:00 included) because Sheets refreshes each formula about hourly
while a tab is open. Nine formulas -> one drops the ceiling from ~216 calls/day
to 24, so a file left open every hour of a 30-day month costs ~720 of the
1.000/month paid quota. That is what guarantees a paying customer can pull the
full dataset daily for a month without running out.

There is deliberately no Apps Script. A bound script travels with a Drive copy
and becomes *the copier's own* project, so Google shows every customer
"Google hasn't verified this app" naming them as the developer.

Run:  python3 integrations/google-sheets/build_template.py
Then File -> Import -> Replace spreadsheet on the live template.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

API = "https://api.vietdataverse.online/api/v1"
COVER = "Bắt đầu"
RAW = "_dữ liệu thô"
KEY_CELL = "$C$6"
PERIOD = "1y"
MAX_ROWS = 2000          # stacked payload is ~1.5k rows; headroom for 'all'

BRAND = "2F5FDE"
INK = "141413"
MUTED = "5E5D59"
INPUT_FILL = "FFF8DC"
WARN = "B53333"

UPGRADE_URL = "https://vietdataverse.online/pages/pricing.html"

# (tab, dataset id, headers, chart=(first_value_col, last_value_col, y label))
# Headers and column counts come from the live API, verified 2026-09-29.
# Column 1 is always the date or period, so charted values start at 2.
DATASETS = [
    ("Vàng SJC", "gold", ["Ngày", "Giá mua", "Giá bán"], (2, 3, "VND/lượng")),
    ("Bạc", "silver", ["Ngày", "Giá mua", "Giá bán"], (2, 3, "VND/lượng")),
    ("Lãi suất LNH", "interbank",
     ["Ngày", "Qua đêm", "1 tháng", "3 tháng", "6 tháng", "9 tháng", "Chiết khấu", "Tái cấp vốn"],
     (2, 6, "%/năm")),
    ("Tỷ giá", "fx", ["Ngày", "Tỷ giá trung tâm", "Mua tiền mặt", "Bán"], (2, 2, "VND/USD")),
    ("Tiền gửi ACB", "deposit",
     ["Ngày", "1 tháng", "3 tháng", "6 tháng", "12 tháng", "24 tháng"], (2, 6, "%/năm")),
    ("Thế giới", "global", ["Ngày", "Vàng (USD/oz)", "Bạc (USD/oz)", "NASDAQ"], (2, 4, "USD")),
    ("CPI", "cpi", ["Kỳ", "So tháng trước (%)", "So cùng kỳ (%)"], (2, 3, "%")),
    # GDP interleaves several series down one column (year, quarter, sector),
    # so a line through it would draw nonsense. No chart on purpose.
    ("GDP", "gdp", ["Năm", "Quý", "Khu vực", "GDP (tỷ VND)", "Tăng trưởng (%)"], None),
    ("Xuất nhập khẩu", "trade",
     ["Kỳ", "Xuất (tỷ USD)", "Nhập (tỷ USD)", "Cán cân", "XK cùng kỳ (%)", "NK cùng kỳ (%)"],
     (2, 4, "tỷ USD")),
]

PROMPT = "Dán API key vào ô C6 của tab Bắt đầu"
# Shown when the API refuses. The overwhelmingly common cause is a spent monthly
# quota, and a Sheets user never sees an HTTP body — IMPORTDATA renders #N/A and
# nothing else. Without this the file simply looks broken, which is exactly what
# happened on 2026-09-29.
ERROR_MSG = ("Không lấy được dữ liệu. Thường là đã hết lượt API của tháng — "
             "nâng gói tại " + UPGRADE_URL + " (hạn mức mới có hiệu lực ngay), "
             "hoặc kiểm tra lại API key ở ô C6.")


def raw_formula() -> str:
    """The single network call in the whole workbook."""
    url = f"{API}/excel/refresh-data?period={PERIOD}&format=csv&api_key="
    ref = f"'{COVER}'!{KEY_CELL}"
    return (f'=IF({ref}="","{PROMPT}",'
            f'IFERROR(IMPORTDATA("{url}"&{ref}),"{ERROR_MSG}"))')


def query_formula(dataset_id: str, n_cols: int) -> str:
    """Pull one dataset out of the stacked tab. Pure formula — no network."""
    cols = ", ".join(f"Col{i + 1}" for i in range(1, n_cols + 1))
    return (f"=IFERROR(QUERY('{RAW}'!A:I, \"select {cols} "
            f"where Col1 = '{dataset_id}'\", 0), \"\")")


def build_cover(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 44
    ws.column_dimensions["C"].width = 62

    ws["B2"] = "Viet Dataverse — Dữ liệu kinh tế Việt Nam"
    ws["B2"].font = Font(name="Georgia", size=18, bold=True, color=INK)
    ws["B3"] = "Chín bộ dữ liệu vĩ mô & thị trường Việt Nam."
    ws["B3"].font = Font(size=11, color=MUTED)

    ws["B5"] = "CHỈ CÓ MỘT BƯỚC"
    ws["B5"].font = Font(size=12, bold=True, color=BRAND)
    ws["B5"].fill = PatternFill("solid", fgColor="EEF2FF")

    ws["B6"] = "Dán API key của bạn vào ô bên phải  →"
    ws["B6"].font = Font(size=12, bold=True, color=INK)
    edge = Side(style="medium", color=BRAND)
    ws["C6"].fill = PatternFill("solid", fgColor=INPUT_FILL)
    ws["C6"].border = Border(left=edge, right=edge, top=edge, bottom=edge)
    ws["C6"].font = Font(size=12, bold=True, color=INK)

    ws["B7"] = "Làm mới ngay"
    ws["B7"].font = Font(size=12, bold=True, color=INK)
    ws["C7"] = 1
    ws["C7"].fill = PatternFill("solid", fgColor=INPUT_FILL)
    ws["C7"].border = Border(left=edge, right=edge, top=edge, bottom=edge)
    ws["C7"].font = Font(size=12, bold=True, color=INK)

    rows = [
        ("Xong.", "Chín tab bên dưới tự đổ dữ liệu, mỗi tab có biểu đồ và ngày dữ liệu mới nhất."),
        ("Chưa có key?", f"Lấy miễn phí tại https://vietdataverse.online/pages/developer.html"),
        ("Làm mới", "Tăng số ở ô C7 (1 → 2 → 3…). Tải lại trang KHÔNG làm mới — Google giữ cache ~1 giờ."),
        ("Hạn mức", "Cả file chỉ tốn 1 lượt API mỗi lần làm mới (không phải 9). "
                    "Miễn phí 20 lượt/tháng; gói trả phí 1.000 lượt/tháng."),
        ("Đổi khoảng thời gian", f"Sửa period={PERIOD} trong công thức ô A1 của tab \"{RAW}\" (7d, 1m, 1y, all)."),
        ("Bảo mật", "Key nằm trong ô C6 của bản copy của bạn. Đừng chia sẻ file này cho người lạ."),
    ]
    for offset, (label, text) in enumerate(rows):
        row = 9 + offset
        ws[f"B{row}"] = label
        ws[f"B{row}"].font = Font(size=11, bold=True, color=INK)
        ws[f"C{row}"] = text
        ws[f"C{row}"].font = Font(size=11, color=MUTED)
        ws[f"C{row}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 32


def build_raw(ws) -> None:
    """The one tab that talks to the API. Everything else reads from here."""
    ws["A1"] = raw_formula()
    ws.column_dimensions["A"].width = 16
    ws["K1"] = ("Tab kỹ thuật — đừng sửa. Đây là lượt gọi API DUY NHẤT của cả file; "
                "chín tab kia đọc lại từ đây bằng QUERY nên không tốn thêm lượt nào.")
    ws["K1"].font = Font(size=9, italic=True, color=MUTED)


def add_chart(ws, tab: str, spec, n_rows: int = MAX_ROWS) -> None:
    first_col, last_col, y_label = spec
    chart = LineChart()
    chart.title = tab
    chart.y_axis.title = y_label
    chart.height, chart.width = 8, 17
    chart.style = 2
    data = Reference(ws, min_col=first_col, max_col=last_col, min_row=3, max_row=n_rows)
    cats = Reference(ws, min_col=1, min_row=4, max_row=n_rows)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    ws.add_chart(chart, "K5")


def build_dataset_tab(ws, tab: str, dataset_id: str, headers: list, chart_spec) -> None:
    # Row 1: freshness. Row 3: headers. Row 4+: the QUERY spill.
    ws["A1"] = "Dữ liệu mới nhất:"
    ws["A1"].font = Font(size=10, bold=True, color=INK)
    # SORT descending, not MAX: three datasets key on a text period ("2026-08",
    # "2026") rather than a date, and MAX over text returns 0. Sorting handles
    # both, and TEXT is left off so a date stays a date and a period stays its
    # own label.
    ws["B1"] = '=IFERROR(INDEX(SORT(FILTER(A4:A, A4:A<>""), 1, FALSE), 1), "—")'
    ws["B1"].font = Font(size=10, bold=True, color=BRAND)
    ws["C1"] = "(ngày/kỳ gần nhất có trong bộ này)"
    ws["C1"].font = Font(size=9, italic=True, color=MUTED)

    for column, heading in enumerate(headers, start=1):
        cell = ws.cell(row=3, column=column, value=heading)
        cell.font = Font(size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
        ws.column_dimensions[get_column_letter(column)].width = max(13, len(heading) + 3)

    ws["A4"] = query_formula(dataset_id, len(headers))
    ws.freeze_panes = "A4"
    if chart_spec:
        add_chart(ws, tab, chart_spec)


def main() -> Path:
    wb = Workbook()
    build_cover(wb.active)
    wb.active.title = COVER

    for tab, dataset_id, headers, chart_spec in DATASETS:
        build_dataset_tab(wb.create_sheet(tab), tab, dataset_id, headers, chart_spec)

    # Last, so it sits at the end of the tab strip rather than between datasets.
    build_raw(wb.create_sheet(RAW))

    out = Path(__file__).resolve().parent / "Viet-Dataverse-Google-Sheets-Template.xlsx"
    wb.save(out)
    return out


if __name__ == "__main__":
    print(main())
