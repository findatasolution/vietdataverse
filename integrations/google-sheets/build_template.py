"""Build the Google Sheets template: copy the file, paste a key, done.

The template is nine IMPORTDATA formulas and one input cell. There is
deliberately no Apps Script: a bound script is copied into the customer's own
Drive, which makes *them* its developer, so Google shows every customer the
"Google hasn't verified this app" warning about a script they just acquired.
No project setting removes that — only Workspace Marketplace verification
would, and that is weeks of review. IMPORTDATA needs no authorization at all.

Run:  python3 integrations/google-sheets/build_template.py
Then upload the .xlsx to Drive, letting Drive convert it to a Google Sheet.
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

API = "https://api.vietdataverse.online/api/v1"
COVER = "Bắt đầu"
KEY_CELL = "$C$6"          # the one cell a customer ever types into
# Cache-buster. IMPORTDATA keys its cache on the exact URL and refreshes only
# about hourly, so reloading the page does NOT refetch. Appending a cell the
# customer can change gives a genuine "refresh now": a new value is a new URL,
# which Google must fetch. This is the only refresh control Sheets offers
# without an Apps Script — and an Apps Script is what puts the "Google hasn't
# verified this app" warning in front of every customer.
REFRESH_CELL = "$C$7"
PERIOD = "1y"
MAX_CHART_ROWS = 400    # 1y of daily rows, with headroom

BRAND = "2F5FDE"
INK = "141413"
MUTED = "5E5D59"
PAPER = "F5F4ED"
INPUT_FILL = "FFF8DC"

# (tab, query, human description). Queries mirror be/routers/sheets_export.py
# `_datasets()`; every one was verified to return CSV against the live DBs.
# (tab, query, description, chart) where chart is (first_value_col,
# last_value_col, y-axis label) or None. Column numbers come from the CSV
# headers verified against the live databases; column 1 is always the date or
# period, so values start at 2.
DATASETS = [
    ("Vàng SJC",       "gold?period={p}&type=SJC",                 "Giá vàng SJC mua vào / bán ra theo ngày",
     (2, 3, "VND/lượng")),
    ("Bạc",            "silver?period={p}",                        "Giá bạc Phú Quý theo ngày",
     (2, 3, "VND/lượng")),
    ("Lãi suất LNH",   "sbv-interbank?period={p}",                 "Lãi suất liên ngân hàng + lãi suất điều hành SBV",
     (2, 6, "%/năm")),
    ("Tỷ giá",         "sbv-rate?period={p}&bank=SBV&currency=USD", "Tỷ giá trung tâm USD/VND",
     (2, 2, "VND/USD")),
    ("Tiền gửi ACB",   "termdepo?period={p}&bank=ACB",             "Lãi suất tiền gửi theo kỳ hạn",
     (2, 6, "%/năm")),
    ("Thế giới",       "global-macro?period={p}",                  "Vàng, bạc, NASDAQ thế giới",
     (2, 4, "USD")),
    ("CPI",            "macro/cpi?view=monthly&years=5",           "Chỉ số giá tiêu dùng theo tháng",
     (2, 3, "%")),
    # GDP rows are (year, quarter, sector, value, growth) — several series
    # interleaved down one column, so a line chart over it would draw nonsense.
    ("GDP",            "macro/gdp",                                "GDP theo quý và khu vực", None),
    ("Xuất nhập khẩu", "macro/trade?months=24",                    "Kim ngạch xuất nhập khẩu theo tháng",
     (2, 4, "tỷ USD")),
]

PROMPT = "← Dán API key vào ô C6 của tab Bắt đầu để đổ dữ liệu"


def formula(query: str) -> str:
    """One self-contained cell: the prompt until a key exists, then the data.

    Without the IF, an empty key cell sends `api_key=` to a metered endpoint,
    which answers 401 and paints every tab with #REF! — a customer who has done
    nothing wrong would open the file to nine errors.
    """
    url = f"{API}/{query.format(p=PERIOD)}&format=csv&api_key="
    if "?" not in query:
        url = f"{API}/{query}?format=csv&api_key="
    ref = f"'{COVER}'!{KEY_CELL}"
    bust = f"'{COVER}'!{REFRESH_CELL}"
    return (f'=IF({ref}="","{PROMPT}",'
            f'IMPORTDATA("{url}"&{ref}&"&_r="&{bust}))')


def build_cover(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 46
    ws.column_dimensions["C"].width = 54

    ws["B2"] = "Viet Dataverse — Dữ liệu kinh tế Việt Nam"
    ws["B2"].font = Font(name="Georgia", size=18, bold=True, color=INK)
    ws["B3"] = "Chín bộ dữ liệu vĩ mô & thị trường Việt Nam, cập nhật tự động."
    ws["B3"].font = Font(size=11, color=MUTED)

    ws["B5"] = "CHỈ CÓ MỘT BƯỚC"
    ws["B5"].font = Font(size=12, bold=True, color=BRAND)
    ws["B5"].fill = PatternFill("solid", fgColor="EEF2FF")

    ws["B6"] = "Dán API key của bạn vào ô bên phải  →"
    ws["B6"].font = Font(size=12, bold=True, color=INK)
    ws["B6"].alignment = Alignment(vertical="center")
    edge = Side(style="medium", color=BRAND)
    ws["C6"].fill = PatternFill("solid", fgColor=INPUT_FILL)
    ws["C6"].border = Border(left=edge, right=edge, top=edge, bottom=edge)
    ws["C6"].font = Font(size=12, bold=True, color=INK)

    ws["B7"] = "Làm mới toàn bộ 9 tab"
    ws["B7"].font = Font(size=12, bold=True, color=INK)
    ws["C7"] = 1
    ws["C7"].fill = PatternFill("solid", fgColor=INPUT_FILL)
    ws["C7"].border = Border(left=edge, right=edge, top=edge, bottom=edge)
    ws["C7"].font = Font(size=12, bold=True, color=INK)

    rows = [
        ("Xong.", "Chín tab bên dưới tự đổ dữ liệu ngay. Không cần cấp quyền, không cài gì."),
        ("Chưa có key?", "Lấy miễn phí tại https://vietdataverse.online/pages/developer.html"),
        ("Làm mới ngay", "Tăng số trong ô C7 lên 1 đơn vị (1 → 2 → 3…). Cả 9 tab tải lại cùng lúc. "
                         "Tải lại trang KHÔNG làm mới — Google giữ cache ~1 giờ."),
        ("Đổi khoảng thời gian", f"Sửa period={PERIOD} trong công thức ở ô A1 của tab bất kỳ (7d, 1m, 1y, all)."),
        ("Hạn mức", "Mỗi tab là một lượt gọi API (9 tab = 9 lượt mỗi lần mở). Gói miễn phí 20 lượt/tháng; "
                    "mở file thường xuyên thì cần gói trả phí."),
        ("Bảo mật", "Key nằm trong ô C6 của bản copy của bạn. Đừng chia sẻ file này cho người lạ."),
    ]
    for offset, (label, text) in enumerate(rows):
        row = 9 + offset
        ws[f"B{row}"] = label
        ws[f"B{row}"].font = Font(size=11, bold=True, color=INK)
        ws[f"C{row}"] = text
        ws[f"C{row}"].font = Font(size=11, color=MUTED)
        ws[f"C{row}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 30


def add_chart(ws, tab: str, spec) -> None:
    """A line chart over the range IMPORTDATA will fill.

    The range is fixed (rows 1..MAX_CHART_ROWS) because the formula's output
    size is not known until Google runs it. Blank trailing rows are simply not
    plotted, so over-reaching costs nothing; under-reaching would silently crop
    the series.
    """
    first_col, last_col, y_label = spec
    chart = LineChart()
    chart.title = tab
    chart.y_axis.title = y_label
    chart.height, chart.width = 8, 17
    chart.style = 2

    data = Reference(ws, min_col=first_col, max_col=last_col,
                     min_row=1, max_row=MAX_CHART_ROWS)
    categories = Reference(ws, min_col=1, min_row=2, max_row=MAX_CHART_ROWS)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(categories)
    # Column L: clear of both the CSV block (A..~H) and the J1 description.
    ws.add_chart(chart, "L3")


def main() -> Path:
    wb = Workbook()
    build_cover(wb.active)
    wb.active.title = COVER

    for tab, query, description, chart_spec in DATASETS:
        ws = wb.create_sheet(tab)
        ws["A1"] = formula(query)
        ws.column_dimensions["A"].width = 30
        for column in "BCDEFGH":
            ws.column_dimensions[column].width = 18
        ws.freeze_panes = "A2"
        # The description lives off to the right so it can never collide with
        # the CSV block IMPORTDATA expands into from A1.
        ws["J1"] = description
        ws["J1"].font = Font(size=9, italic=True, color=MUTED)
        if chart_spec:
            add_chart(ws, tab, chart_spec)

    out = Path(__file__).resolve().parent / "Viet-Dataverse-Google-Sheets-Template.xlsx"
    wb.save(out)
    return out


if __name__ == "__main__":
    print(main())
