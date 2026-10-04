"""Build the Google Sheets template: copy the file, paste a key, done.

**One API call feeds the whole workbook.** A hidden raw tab holds a single
IMPORTDATA against `/api/v1/excel/refresh-data?format=csv`, which returns every
dataset stacked; each visible tab pulls its own rows out of it with FILTER — a
pure spreadsheet function that costs no network. A dashboard tab
("Tổng quan") then reads the dataset tabs: KPI cards, sparklines and charts.

Measured on a real customer 2026-09-29: the previous design, nine live
IMPORTDATA formulas, made **315 calls in 2.7 days** because Sheets refreshes
each formula about hourly while a tab is open. One formula caps it at ~24/day,
~720 for a file left open all month — inside the 1.000/month paid quota.

Five rules below each cost a customer a broken file before they were written
down (2026-10-03 rebuild). Read them before changing anything:

1. **Dates leave the formula as text** (`TEXT(..., "yyyy-mm-dd")`). IMPORTDATA
   turns `2025-10-03` into the serial 45933 with no date format, and the old
   fix — a number format pre-applied to each cell — did not survive the
   customer's copy past the first rows, so they saw serials (cause unknown).
   A value that is already a string cannot be displayed wrongly.
2. **FILTER, never QUERY, over the raw tab.** QUERY gives each column one
   type, decided by majority, and silently nulls the minority. The raw tab
   stacks nine datasets, so GDP's sector names (text in a mostly-numeric
   column) all came back blank.
3. **No Excel "dynamic array" functions** (SORT, SORTN, LET, XLOOKUP...). An
   `.xlsx` stores them as `_xlfn.` names; the old freshness cell (SORT) showed
   "—" on the live template even with data loaded — suspected, not verified,
   to be the bare name. FILTER is Google-native like IMPORTDATA/SPARKLINE, but
   this rebuild is NOT yet verified in a real Sheet — README "Verifying a
   rebuild".
4. **No open-ended ranges** (`C2:C`). Valid in Sheets, invalid in `.xlsx`;
   the import turned every such formula into #ERROR!.
5. **The raw tab is hidden.** It is plumbing: headers `c1..c8`, serial dates.
   Customers asked what it was for.

There is deliberately no Apps Script. A bound script travels with a Drive copy
and becomes *the copier's own* project, so Google shows every customer
"Google hasn't verified this app" naming them as the developer.

Run:  python3 integrations/google-sheets/build_template.py
Then File -> Import -> Replace spreadsheet on the live template, and check C6
of the live template is EMPTY afterwards (see README "Never paste a real key").
"""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

API = "https://api.vietdataverse.online/api/v1"
COVER = "Bắt đầu"
DASH = "Tổng quan"
RAW = "_raw"
KEY_CELL = "$C$6"
REFRESH_CELL = "$C$7"
PERIOD_CELL = "$C$8"
PERIODS = ["1m", "1y", "all"]
DEFAULT_PERIOD = "1y"
DATA_ROW = 6            # first data row on every dataset tab (row 5 = headers)
MAX_ROWS = 2500         # per-tab ceiling; the largest dataset at period=all is ~1.9k
RAW_ROWS = 8000         # raw-tab ceiling; period=all stacks ~4.1k rows today

BRAND = "2F5FDE"
INK = "141413"
MUTED = "5E5D59"
LINE = "E3E8F4"
CARD = "F6F8FE"
INPUT_FILL = "FFF8DC"
# A line palette that reads as an ordered ramp, matching the site's rate charts.
RAMP = ["2F5FDE", "6C93E4", "A3C0F2", "1E3FAE", "16307F", "26A69A", "EF5350"]

UPGRADE_URL = "https://vietdataverse.online/pages/pricing.html"
PROMPT = "Dán API key vào ô C6 của tab Bắt đầu"
# Shown when the API refuses. The overwhelmingly common cause is a spent monthly
# quota, and a Sheets user never sees an HTTP body — IMPORTDATA renders #N/A and
# nothing else. Without this the file simply looks broken (2026-09-29).
ERROR_MSG = ("Không lấy được dữ liệu. Thường là đã hết lượt API của tháng — "
             "nâng gói tại " + UPGRADE_URL + " (hạn mức mới có hiệu lực ngay), "
             "hoặc kiểm tra lại API key ở ô C6.")

# Each dataset: tab, id, title line, columns. A column is
#   (header, raw column letter, kind, number format)
# kind: "date" / "month" -> TEXT(); "sector" -> translated text; "num" -> as is.
# Raw columns: A = dataset id, B..I = the API's c1..c8. Columns the API sends
# but never fills (fx buy/sell, GDP level) are left out: an always-empty column
# reads as broken data.
DATASETS = [
    dict(tab="Vàng SJC", id="gold", title="Giá vàng SJC — VND/lượng · nguồn 24h.com.vn / giavang.org",
         cols=[("Ngày", "B", "date", None), ("Giá mua", "C", "num", "#,##0"),
               ("Giá bán", "D", "num", "#,##0")]),
    dict(tab="Bạc", id="silver", title="Giá bạc Phú Quý — VND/lượng",
         cols=[("Ngày", "B", "date", None), ("Giá mua", "C", "num", "#,##0"),
               ("Giá bán", "D", "num", "#,##0")]),
    dict(tab="Lãi suất LNH", id="interbank", title="Lãi suất liên ngân hàng & điều hành NHNN — %/năm",
         cols=[("Ngày", "B", "date", None), ("Qua đêm", "C", "num", "0.00"),
               ("1 tháng", "D", "num", "0.00"), ("3 tháng", "E", "num", "0.00"),
               ("6 tháng", "F", "num", "0.00"), ("9 tháng", "G", "num", "0.00"),
               ("Chiết khấu", "H", "num", "0.00"), ("Tái cấp vốn", "I", "num", "0.00")]),
    dict(tab="Tỷ giá", id="fx", title="Tỷ giá trung tâm USD/VND — NHNN",
         cols=[("Ngày", "B", "date", None), ("Tỷ giá trung tâm", "C", "num", "#,##0")]),
    dict(tab="Tiền gửi ACB", id="deposit", title="Lãi suất tiền gửi ACB theo kỳ hạn — %/năm",
         cols=[("Ngày", "B", "date", None), ("1 tháng", "C", "num", "0.00"),
               ("3 tháng", "D", "num", "0.00"), ("6 tháng", "E", "num", "0.00"),
               ("12 tháng", "F", "num", "0.00"), ("24 tháng", "G", "num", "0.00")]),
    dict(tab="Thế giới", id="global", title="Thị trường thế giới — vàng, bạc (USD/oz), NASDAQ (điểm)",
         cols=[("Ngày", "B", "date", None), ("Vàng (USD/oz)", "C", "num", "#,##0.0"),
               ("Bạc (USD/oz)", "D", "num", "#,##0.00"), ("NASDAQ", "E", "num", "#,##0")]),
    dict(tab="CPI", id="cpi", title="Chỉ số giá tiêu dùng — % · nguồn Tổng cục Thống kê",
         cols=[("Kỳ", "B", "month", None), ("So tháng trước (%)", "C", "num", "0.00"),
               ("So cùng kỳ (%)", "D", "num", "0.00")]),
    dict(tab="GDP", id="gdp", title="Tăng trưởng GDP theo quý và khu vực — % so cùng kỳ",
         cols=[("Năm", "B", "num", "0"), ("Quý", "C", "num", "0"),
               ("Khu vực", "D", "sector", None), ("Tăng trưởng (%)", "F", "num", "0.00")]),   # GDP: the dashboard charts its economy-wide total
    dict(tab="Xuất nhập khẩu", id="trade", title="Kim ngạch xuất nhập khẩu — tỷ USD · nguồn Tổng cục Thống kê",
         cols=[("Kỳ", "B", "month", None), ("Xuất khẩu (tỷ USD)", "C", "num", "0.00"),
               ("Nhập khẩu (tỷ USD)", "D", "num", "0.00"), ("Cán cân", "E", "num", "0.00"),
               ("XK so cùng kỳ (%)", "F", "num", "0.0"), ("NK so cùng kỳ (%)", "G", "num", "0.0")]),
]
BY_ID = {d["id"]: d for d in DATASETS}

SECTORS = [("agriculture", "Nông-lâm-thủy sản"), ("industry", "Công nghiệp-xây dựng"),
           ("services", "Dịch vụ"), ("total", "Toàn nền kinh tế")]

# Dashboard KPI cards: (label, dataset id, column header, scale, value format,
# change kind, unit). change "pct" = % vs previous observation, "pp" = change
# in percentage points (for rates, where a % of a % misleads).
KPIS = [
    ("Vàng SJC — bán ra", "gold", "Giá bán", 1e6, "#,##0.0", "pct", "triệu VND/lượng"),
    ("Bạc Phú Quý — bán ra", "silver", "Giá bán", 1e6, "#,##0.00", "pct", "triệu VND/lượng"),
    ("Tỷ giá trung tâm USD", "fx", "Tỷ giá trung tâm", 1, "#,##0", "pct", "VND/USD"),
    ("Vàng thế giới", "global", "Vàng (USD/oz)", 1, "#,##0", "pct", "USD/oz"),
    ("Lãi suất qua đêm LNH", "interbank", "Qua đêm", 1, "0.00", "pp", "%/năm"),
    ("Tiền gửi ACB 12 tháng", "deposit", "12 tháng", 1, "0.00", "pp", "%/năm"),
    ("CPI so cùng kỳ", "cpi", "So cùng kỳ (%)", 1, "0.00", "pp", "%"),
    ("Xuất khẩu tháng", "trade", "Xuất khẩu (tỷ USD)", 1, "0.00", "pct", "tỷ USD"),
]
# Dashboard chart blocks: (dataset, column header, title, sparkline kind, colour, value format).
# "gdp_total" reads the GDP tab's economy-wide helper column (I).
CHARTS = [
    ("gold", "Giá bán", "Giá vàng SJC bán ra (VND/lượng)", "line", "2F5FDE", "#,##0"),
    ("fx", "Tỷ giá trung tâm", "Tỷ giá trung tâm USD/VND", "line", "1E3FAE", "#,##0"),
    ("interbank", "Qua đêm", "Lãi suất qua đêm liên ngân hàng (%/năm)", "line", "6C93E4", "0.00"),
    ("global", "Vàng (USD/oz)", "Vàng thế giới (USD/oz)", "line", "16307F", "#,##0"),
    ("cpi", "So cùng kỳ (%)", "CPI so cùng kỳ (%)", "column", "2F5FDE", "0.00"),
    ("trade", "Cán cân", "Cán cân thương mại (tỷ USD)", "column", "26A69A", "0.00"),
    ("silver", "Giá bán", "Giá bạc Phú Quý bán ra (VND/lượng)", "line", "4D4C48", "#,##0"),
    ("gdp_total", None, "Tăng trưởng GDP toàn nền kinh tế (%)", "column", "26A69A", "0.00"),
]
PCT_FMT = '[Color10]▲ 0.0%;[Red]▼ 0.0%;"không đổi"'
PP_FMT = '[Color10]▲ 0.00 "điểm %";[Red]▼ 0.00 "điểm %";"không đổi"'


def q(tab: str) -> str:
    return f"'{tab}'"


def raw_formula() -> str:
    """The single network call in the whole workbook."""
    ref = f"{q(COVER)}!{KEY_CELL}"
    period = f"{q(COVER)}!{PERIOD_CELL}"
    # locale="en_US" is not cosmetic. A copy inherits the owner's spreadsheet
    # locale, and under vi_VN Sheets reads "4.5" as the DATE 4 May (46146):
    # every rate shaped X.Y with X<=12, Y<=31 was destroyed that way. In en_US
    # the decimal separator is "." and the date separator "/", so a rate cannot
    # be mistaken for a date.
    #
    # REFRESH_CELL is appended as &_r= because IMPORTDATA caches on the exact URL
    # (~1 hour); a new value makes a new URL Google must fetch. The API ignores
    # the parameter. 724b86677 dropped it once and the refresh cell went dead.
    bust = f"{q(COVER)}!{REFRESH_CELL}"
    url = f'"{API}/excel/refresh-data?format=csv&period="&{period}&"&api_key="&{ref}&"&_r="&{bust}'
    return (f'=IF({ref}="","{PROMPT}",'
            f'IFERROR(IMPORTDATA({url}, ",", "en_US"),"{ERROR_MSG}"))')


STATUS = "VDV_STATUS"    # named range for the raw tab's A1: "dataset" on success, else the reason


def _rows(col: str) -> str:
    # A workbook-level name (VDV_A .. VDV_I) instead of '_raw'!C2:C8000 written
    # out in every formula: it keeps the file small enough to publish (see
    # README "Publishing"), and one definition is one place to change.
    return f"VDV_{col}"


def raw_names() -> dict:
    """Defined names -> ranges. Bounded on purpose: Sheets accepts an open
    range like C2:C, but the .xlsx format does not, and the import turned every
    formula holding one into #ERROR! (first real-Sheet check, 2026-10-03)."""
    names = {f"VDV_{c}": f"{q(RAW)}!${c}$2:${c}${RAW_ROWS}" for c in "ABCDEFGHI"}
    names[STATUS] = f"{q(RAW)}!$A$1"
    return names


def _match(dataset_id: str) -> str:
    return f'{_rows("A")}="{dataset_id}"'


def column_formula(dataset_id: str, col: str, kind: str) -> str:
    """One output column of a dataset tab, pulled from the raw tab with FILTER.

    FILTER, not QUERY: QUERY types each column by majority and nulls the rest,
    which blanked every GDP sector name. TEXT on dates: see module docstring.
    """
    picked = f"FILTER({_rows(col)}, {_match(dataset_id)})"
    if kind == "date":
        expr = f'ARRAYFORMULA(TEXT({picked}, "yyyy-mm-dd"))'
    elif kind == "month":
        expr = f'ARRAYFORMULA(TEXT({picked}, "yyyy-mm"))'
    elif kind == "sector":
        expr = picked
        for src, label in SECTORS:
            expr = f'SUBSTITUTE({expr}, "{src}", "{label}")'
        expr = f"ARRAYFORMULA({expr})"
    else:
        expr = picked
    return f'=IFERROR({expr}, "")'


def key_formula(dataset_id: str, col: str, kind: str) -> str:
    """The first column also reports why there is no data, when there is none.

    The raw tab's A1 is the literal "dataset" header only when the call
    succeeded; otherwise it holds the reason (no key, bad key, quota spent).
    A blank tab reads as a broken file — the report of 2026-09-29.
    """
    body = column_formula(dataset_id, col, kind)[1:]
    return f'=IF({STATUS}<>"dataset", {STATUS}, {body})'


def last_formula(tab: str, col_letter: str, offset: int = 0) -> str:
    """Newest (offset=0) or earlier value of a column. Rows are oldest-first,
    so the newest is at COUNTA of the key column. No SORT — see rule 3."""
    n = f"COUNTA({q(tab)}!$A${DATA_ROW}:$A${MAX_ROWS})"
    return f"INDEX({q(tab)}!{col_letter}${DATA_ROW}:{col_letter}${MAX_ROWS}, {n}-{offset})"


def build_cover(ws) -> None:
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 70

    ws["B2"] = "Viet Dataverse — Dữ liệu kinh tế Việt Nam"
    ws["B2"].font = Font(name="Georgia", size=18, bold=True, color=INK)
    ws["B3"] = "Bảng tổng quan + chín bộ dữ liệu vĩ mô & thị trường, tự cập nhật."
    ws["B3"].font = Font(size=11, color=MUTED)

    ws["B5"] = "CHỈ CÓ MỘT BƯỚC"
    ws["B5"].font = Font(size=12, bold=True, color=BRAND)
    ws["B5"].fill = PatternFill("solid", fgColor="EEF2FF")

    edge = Side(style="medium", color=BRAND)
    inputs = [("B6", "Dán API key của bạn vào ô bên phải  →", None),
              ("B7", "Làm mới ngay (tăng số này)", 1),
              ("B8", "Khoảng thời gian", DEFAULT_PERIOD)]
    for label_cell, label, value in inputs:
        row = label_cell[1:]
        ws[label_cell] = label
        ws[label_cell].font = Font(size=12, bold=True, color=INK)
        cell = ws[f"C{row}"]
        # C6 stays EMPTY in the build. The live template is shared
        # "anyone with link", so a key there is published to every copier and
        # spends its owner's quota — found twice (2026-09-29, 2026-10-03).
        if value is not None:
            cell.value = value
        cell.fill = PatternFill("solid", fgColor=INPUT_FILL)
        cell.border = Border(left=edge, right=edge, top=edge, bottom=edge)
        cell.font = Font(size=12, bold=True, color=INK)
    period_dv = DataValidation(type="list", formula1='"' + ",".join(PERIODS) + '"', allow_blank=False)
    ws.add_data_validation(period_dv)
    period_dv.add("C8")

    rows = [
        ("Xong.", f"Mở tab \"{DASH}\" để xem bảng tổng quan; chín tab sau là dữ liệu chi tiết, biểu đồ nằm ở tab Tổng quan."),
        ("Thấy thanh vàng?", "Sheets hỏi \"Allow access\" / \"Cho phép truy cập\" ở đầu trang: "
                             "bấm cho phép, nếu không file không lấy được dữ liệu."),
        ("Chưa có key?", "Lấy miễn phí tại https://vietdataverse.online/pages/developer.html"),
        ("Làm mới", "Tăng số ở ô C7 (1 → 2 → 3…). Tải lại trang KHÔNG làm mới — Google giữ cache ~1 giờ."),
        ("Khoảng thời gian", "Chọn ở ô C8: 1m (1 tháng), 1y (1 năm), all (toàn bộ lịch sử)."),
        ("Hạn mức", "Cả file chỉ tốn 1 lượt API mỗi lần làm mới (không phải 9). "
                    "Miễn phí 20 lượt/tháng; gói trả phí 1.000 lượt/tháng."),
        ("Bảo mật", "Key nằm trong ô C6 của bản copy của bạn. Đừng chia sẻ file này cho người lạ."),
    ]
    for offset, (label, text) in enumerate(rows):
        row = 10 + offset
        ws[f"B{row}"] = label
        ws[f"B{row}"].font = Font(size=11, bold=True, color=INK)
        # Top-aligned like the text beside it: bottom-aligned labels sat level
        # with the NEXT row's text, so each note read as the label above it.
        ws[f"B{row}"].alignment = Alignment(vertical="top")
        ws[f"C{row}"] = text
        ws[f"C{row}"].font = Font(size=11, color=MUTED)
        ws[f"C{row}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 32


def build_raw(ws) -> None:
    """The one tab that talks to the API. Hidden: it is plumbing, not product."""
    ws["A1"] = raw_formula()
    ws.sheet_state = "hidden"


def build_dataset_tab(ws, spec: dict) -> None:
    ws.sheet_view.showGridLines = False
    ws["A1"] = spec["title"]
    ws["A1"].font = Font(name="Georgia", size=14, bold=True, color=INK)
    ws["A2"] = "Dữ liệu đến:"
    ws["A2"].font = Font(size=10, color=MUTED)
    ws["B2"] = (f'=IF({STATUS}<>"dataset", "—", '
                f'IFERROR(INDEX(A{DATA_ROW}:A{MAX_ROWS}, COUNTA(A{DATA_ROW}:A{MAX_ROWS})), "—"))')
    ws["B2"].font = Font(size=10, bold=True, color=BRAND)

    thin = Side(style="thin", color=LINE)
    for i, (header, col, kind, fmt) in enumerate(spec["cols"], start=1):
        letter = get_column_letter(i)
        cell = ws.cell(row=DATA_ROW - 1, column=i, value=header)
        cell.font = Font(size=10, bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[letter].width = max(13, len(header) + 4)
        ws.cell(row=DATA_ROW, column=i).value = (
            key_formula(spec["id"], col, kind) if i == 1 else column_formula(spec["id"], col, kind))
        if fmt:
            # Cosmetic only (thousand separators), set once per column: a
            # per-cell format over 2.5k rows made the file ~6x larger, and
            # correctness no longer depends on any format — see rule 1.
            ws.column_dimensions[letter].number_format = fmt
            # The formula cell in DATA_ROW carries its own style, which beats
            # the column default — without this the first data row alone
            # showed 135800000 while every row below showed 136.600.000.
            ws.cell(row=DATA_ROW, column=i).number_format = fmt
        ws.cell(row=DATA_ROW - 1, column=i).border = Border(bottom=thin)
    ws.row_dimensions[DATA_ROW - 1].height = 30
    ws.freeze_panes = f"A{DATA_ROW}"
    # No per-tab chart: the dashboard carries one per dataset, and a duplicate
    # on every tab doubled the file for no new information.


def build_gdp_helper(ws) -> None:
    """GDP's stacked rows interleave sectors, so a chart straight through the
    tab draws nonsense. Two helper columns keep only the economy-wide total."""
    ws["H5"] = "Quý"
    ws["I5"] = "GDP toàn nền KT (%)"
    for c in ("H5", "I5"):
        ws[c].font = Font(size=10, bold=True, color="FFFFFF")
        ws[c].fill = PatternFill("solid", fgColor=BRAND)
    total = f'{_match("gdp")}, {_rows("D")}="total"'
    ws[f"H{DATA_ROW}"] = (f'=IFERROR(ARRAYFORMULA(FILTER({_rows("B")}&"-Q"&{_rows("C")}, {total})), "")')
    ws[f"I{DATA_ROW}"] = f'=IFERROR(FILTER({_rows("F")}, {total}), "")'
    ws.column_dimensions["H"].width = 11
    ws.column_dimensions["I"].width = 20
    # Sector names ("Nông-lâm-thủy sản", "Công nghiệp-xây dựng") were cut off
    # at the header-derived width.
    ws.column_dimensions["C"].width = 24
    # "Dữ liệu đến" on this tab read just "2026": column A is the year. The
    # last quarter label in H is the honest cutoff.
    ws["B2"] = (f'=IF({STATUS}<>"dataset", "—", '
                f'IFERROR(INDEX(H{DATA_ROW}:H{MAX_ROWS}, COUNTA(H{DATA_ROW}:H{MAX_ROWS})), "—"))')


def _col_of(spec: dict, header: str) -> str:
    for i, col in enumerate(spec["cols"], start=1):
        if col[0] == header:
            return get_column_letter(i)
    raise KeyError(header)


def build_dashboard(ws, tabs: dict) -> None:
    ws.sheet_view.showGridLines = False
    for col in range(1, 18):
        ws.column_dimensions[get_column_letter(col)].width = 2.5 if col % 4 == 1 else 13
    ws["B2"] = "Bảng tổng quan kinh tế Việt Nam"
    ws["B2"].font = Font(name="Georgia", size=20, bold=True, color=INK)
    ws["B3"] = (f'=IF({STATUS}<>"dataset", {STATUS}, '
                f'"Vàng SJC cập nhật đến " & {q("Vàng SJC")}!B2 & " · dữ liệu Viet Dataverse · '
                f'thay đổi so với kỳ trước")')
    ws["B3"].font = Font(size=10, color=MUTED)

    card_fill = PatternFill("solid", fgColor=CARD)
    for k, (label, ds, header, scale, vfmt, change, unit) in enumerate(KPIS):
        spec = BY_ID[ds]
        tab, col = spec["tab"], _col_of(spec, header)
        top = 5 + (k // 4) * 7
        left = 2 + (k % 4) * 4             # columns B, F, J, N; each card 3 wide
        cols = [get_column_letter(left + i) for i in range(3)]
        for r in range(top, top + 6):
            for i, c in enumerate(cols):
                ws[f"{c}{r}"].fill = card_fill
            ws.merge_cells(f"{cols[0]}{r}:{cols[2]}{r}")
        latest, prev = last_formula(tab, col), last_formula(tab, col, 1)
        a = cols[0]
        ws[f"{a}{top}"] = label
        ws[f"{a}{top}"].font = Font(size=10, bold=True, color=MUTED)
        div = f"/{int(scale)}" if scale != 1 else ""
        ws[f"{a}{top + 1}"] = f'=IFERROR({latest}{div}, "—")'
        ws[f"{a}{top + 1}"].font = Font(name="Georgia", size=22, bold=True, color=INK)
        ws[f"{a}{top + 1}"].number_format = vfmt
        ws[f"{a}{top + 1}"].alignment = Alignment(horizontal="left")
        ws.row_dimensions[top + 1].height = 32
        ws[f"{a}{top + 2}"] = unit
        ws[f"{a}{top + 2}"].font = Font(size=9, color=MUTED)
        delta = f"{latest}/{prev}-1" if change == "pct" else f"{latest}-{prev}"
        ws[f"{a}{top + 3}"] = f'=IFERROR({delta}, "")'
        ws[f"{a}{top + 3}"].number_format = PCT_FMT if change == "pct" else PP_FMT
        ws[f"{a}{top + 3}"].font = Font(size=11, bold=True)
        ws[f"{a}{top + 3}"].alignment = Alignment(horizontal="left")
        n = f"COUNTA({q(tab)}!$A${DATA_ROW}:$A${MAX_ROWS})"
        window = f"OFFSET({q(tab)}!{col}{DATA_ROW}, MAX(0, {n}-90), 0, MIN(90, {n}), 1)"
        ws[f"{a}{top + 4}"] = (f'=IFERROR(SPARKLINE({window}, '
                               f'{{"charttype","line";"color","#{BRAND}";"linewidth",2}}), "")')
        ws.row_dimensions[top + 4].height = 34
        ws[f"{a}{top + 5}"] = f'=IFERROR("Kỳ " & {last_formula(tab, "A")}, "")'
        ws[f"{a}{top + 5}"].font = Font(size=9, color=MUTED)

    # Charts: SPARKLINE blocks, two per row under the cards. Not native charts:
    # chart parts tripled the .xlsx, past the size the Drive upload could take
    # (README "Publishing"). Each block: title, the line/columns, and the
    # first / lowest / highest / newest values so the reader gets the scale a
    # sparkline has no axis for.
    for i, (ds, header, title, kind, color, vfmt) in enumerate(CHARTS):
        tab = BY_ID[ds]["tab"] if ds != "gdp_total" else "GDP"
        col = _col_of(BY_ID[ds], header) if ds != "gdp_total" else "I"
        top = 20 + (i // 2) * 13
        left = 2 if i % 2 == 0 else 10
        first, last = get_column_letter(left), get_column_letter(left + 6)
        rng = f"{q(tab)}!{col}{DATA_ROW}:{col}{MAX_ROWS}"
        vals = f'FILTER({rng}, {rng}<>"")'
        ws.merge_cells(f"{first}{top}:{last}{top}")
        ws[f"{first}{top}"] = title
        ws[f"{first}{top}"].font = Font(name="Georgia", size=13, bold=True, color=INK)
        ws.merge_cells(f"{first}{top + 1}:{last}{top + 8}")
        opts = (f'{{"charttype","{kind}";"color","#{color}";"negcolor","#EF5350";"linewidth",2}}'
                if kind == "column" else f'{{"charttype","line";"color","#{color}";"linewidth",2}}')
        ws[f"{first}{top + 1}"] = f'=IFERROR(SPARKLINE({vals}, {opts}), "")'
        for r in range(top + 1, top + 9):
            ws.row_dimensions[r].height = 18
        stats = [("Đầu kỳ", f"INDEX({vals}, 1)"), ("Thấp nhất", f"MIN({rng})"),
                 ("Cao nhất", f"MAX({rng})"), ("Mới nhất", f"INDEX({vals}, COUNT({rng}))")]
        for j, (lab, expr) in enumerate(stats):
            c = get_column_letter(left + j * 2)
            ws[f"{c}{top + 9}"] = lab
            ws[f"{c}{top + 9}"].font = Font(size=9, color=MUTED)
            ws[f"{c}{top + 10}"] = f'=IFERROR({expr}, "—")'
            ws[f"{c}{top + 10}"].number_format = vfmt
            ws[f"{c}{top + 10}"].font = Font(size=11, bold=True, color=INK)
            ws[f"{c}{top + 10}"].alignment = Alignment(horizontal="left")


def build_workbook() -> Workbook:
    wb = Workbook()
    cover = wb.active
    cover.title = COVER
    build_cover(cover)
    dash = wb.create_sheet(DASH)
    tabs = {}
    for spec in DATASETS:
        ws = wb.create_sheet(spec["tab"])
        build_dataset_tab(ws, spec)
        tabs[spec["id"]] = ws
    build_gdp_helper(tabs["gdp"])
    build_dashboard(dash, tabs)
    # Last, so it sits at the end of the tab strip — and hidden anyway.
    build_raw(wb.create_sheet(RAW))
    for name, ref in raw_names().items():
        wb.defined_names[name] = DefinedName(name, attr_text=ref)
    wb.active = 0
    return wb


def main() -> Path:
    out = Path(__file__).resolve().parent / "Viet-Dataverse-Google-Sheets-Template.xlsx"
    build_workbook().save(out)
    return out


if __name__ == "__main__":
    print(main())
