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
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

API = "https://api.vietdataverse.online/api/v1"
COVER = "Bắt đầu"
KEY_CELL = "$C$4"          # the one cell a customer ever types into
PERIOD = "1y"

BRAND = "2F5FDE"
INK = "141413"
MUTED = "5E5D59"
PAPER = "F5F4ED"
INPUT_FILL = "FFF8DC"

# (tab, query, human description). Queries mirror be/routers/sheets_export.py
# `_datasets()`; every one was verified to return CSV against the live DBs.
DATASETS = [
    ("Vàng SJC",       "gold?period={p}&type=SJC",                 "Giá vàng SJC mua vào / bán ra theo ngày"),
    ("Bạc",            "silver?period={p}",                        "Giá bạc Phú Quý theo ngày"),
    ("Lãi suất LNH",   "sbv-interbank?period={p}",                 "Lãi suất liên ngân hàng + lãi suất điều hành SBV"),
    ("Tỷ giá",         "sbv-rate?period={p}&bank=SBV&currency=USD", "Tỷ giá trung tâm USD/VND"),
    ("Tiền gửi ACB",   "termdepo?period={p}&bank=ACB",             "Lãi suất tiền gửi theo kỳ hạn"),
    ("Thế giới",       "global-macro?period={p}",                  "Vàng, bạc, NASDAQ thế giới"),
    ("CPI",            "macro/cpi?view=monthly&years=5",           "Chỉ số giá tiêu dùng theo tháng"),
    ("GDP",            "macro/gdp",                                "GDP theo quý và khu vực"),
    ("Xuất nhập khẩu", "macro/trade?months=24",                    "Kim ngạch xuất nhập khẩu theo tháng"),
]

# No double quotes: this is embedded inside a formula string literal, and an
# inner quote silently produces a broken formula in every one of the nine tabs.
PROMPT = "← Dán API key vào ô C4 của tab Bắt đầu để đổ dữ liệu"


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
    return f'=IF({ref}="","{PROMPT}",IMPORTDATA("{url}"&{ref}))'


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

    ws["B4"] = "Dán API key của bạn vào ô bên phải  →"
    ws["B4"].font = Font(size=12, bold=True, color=INK)
    ws["B4"].alignment = Alignment(vertical="center")
    edge = Side(style="medium", color=BRAND)
    ws["C4"].fill = PatternFill("solid", fgColor=INPUT_FILL)
    ws["C4"].border = Border(left=edge, right=edge, top=edge, bottom=edge)
    ws["C4"].font = Font(size=12, bold=True, color=INK)

    rows = [
        ("Xong.", "Chín tab bên dưới tự đổ dữ liệu ngay. Không cần cấp quyền, không cài gì."),
        ("Chưa có key?", "Lấy miễn phí tại https://vietdataverse.online/pages/developer.html"),
        ("Làm mới dữ liệu", "Google tự làm mới khi bạn mở file. Muốn ép ngay: menu Xem → làm mới, hoặc F5."),
        ("Đổi khoảng thời gian", f"Sửa period={PERIOD} trong công thức ở ô A1 của tab bất kỳ (7d, 1m, 1y, all)."),
        ("Hạn mức", "Mỗi tab là một lượt gọi API. Gói miễn phí 2 lượt/tháng chỉ đủ để thử; "
                    "mở file thường xuyên thì cần gói trả phí."),
        ("Bảo mật", "Key nằm trong ô C4 của bản copy của bạn. Đừng chia sẻ file này cho người lạ."),
    ]
    for offset, (label, text) in enumerate(rows):
        row = 7 + offset
        ws[f"B{row}"] = label
        ws[f"B{row}"].font = Font(size=11, bold=True, color=INK)
        ws[f"C{row}"] = text
        ws[f"C{row}"].font = Font(size=11, color=MUTED)
        ws[f"C{row}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 30


def main() -> Path:
    wb = Workbook()
    build_cover(wb.active)
    wb.active.title = COVER

    for tab, query, description in DATASETS:
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

    out = Path(__file__).resolve().parent / "Viet-Dataverse-Google-Sheets-Template.xlsx"
    wb.save(out)
    return out


if __name__ == "__main__":
    print(main())
