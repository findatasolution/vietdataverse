"""Build the downloadable Viet Dataverse Excel workbook.

    python be/excel/build_workbook.py

Writes `fe/downloads/VietDataverse-Data.xlsx`. If `be/excel/vbaProject.bin`
exists it also writes the macro-enabled `VietDataverse-Data.xlsm`, which is the
file customers actually download — the one with the REFRESH button.

Why there is a manual step
--------------------------
A clickable button in Excel requires VBA, and VBA lives in `vbaProject.bin`, an
OLE compound-file binary that only Excel itself can author. No Python library
generates one (xlsxwriter can *embed* an existing one; it cannot create it).
So the one-time path is:

    1. Run this script → VietDataverse-Data.xlsx
    2. Open it in Excel, Alt+F11, import be/excel/RefreshData.bas
    3. Draw a button on "Bắt đầu", assign the macro RefreshData
    4. Save As → .xlsm, then extract its vbaProject.bin (a .xlsm is a zip:
       `unzip -j file.xlsm xl/vbaProject.bin -d be/excel/`)
    5. Commit that .bin

After step 5 this script rebuilds the .xlsm on its own, forever — adding a
dataset never needs Excel again, because the dataset list is DATA (the "Cấu
hình" sheet), not code.

Design decisions worth keeping
------------------------------
* **The dataset list is a sheet, not VBA.** The macro loops the rows of "Cấu
  hình". Adding an endpoint is editing a cell; the macro never changes, so the
  vbaProject.bin never needs regenerating.
* **CSV, not JSON.** VBA has no JSON parser, and every workaround (ScriptControl,
  a 200-line parser) is either 32-bit-only or a liability. `format=csv` was
  added to all nine datasets for exactly this reason.
* **The key lives in one named cell, `API_KEY`.** Nothing is stored in the
  macro, so sharing the file never leaks a key, and swapping customers is
  retyping one cell.
* **Gating is entirely server-side.** The workbook sends the key and reports
  what comes back: 401 = expired/invalid, 429 = out of monthly quota. It makes
  no access decision of its own, so it cannot disagree with the API.
"""
import shutil
import zipfile
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "fe" / "downloads"
XLSX = OUT_DIR / "VietDataverse-Data.xlsx"
XLSM = OUT_DIR / "VietDataverse-Data.xlsm"
VBA_BIN = Path(__file__).resolve().parent / "vbaProject.bin"

API_BASE = "https://api.vietdataverse.online"

# (sheet name, endpoint path, query string, description)
#
# Only endpoints that actually serve `format=csv` belong here. `gold-analysis`
# and `market-pulse` are public but JSON-only, so they are deliberately absent:
# a row that always fails is worse than no row.
DATASETS = [
    ("Vàng SJC",        "api/v1/gold",           "period=1y&type=SJC",            "Giá vàng SJC mua/bán theo ngày"),
    ("Bạc",             "api/v1/silver",         "period=1y",                     "Giá bạc Phú Quý theo ngày"),
    ("Lãi suất LNH",    "api/v1/sbv-interbank",  "period=1y",                     "Lãi suất liên ngân hàng + lãi suất điều hành"),
    ("Tỷ giá",          "api/v1/sbv-rate",       "period=1y&bank=SBV&currency=USD", "Tỷ giá trung tâm USD/VND"),
    ("Tiền gửi ACB",    "api/v1/termdepo",       "period=1y&bank=ACB",            "Lãi suất tiền gửi theo kỳ hạn"),
    ("Thế giới",        "api/v1/global-macro",   "period=1y",                     "Vàng, bạc, NASDAQ thế giới"),
    ("CPI",             "api/v1/macro/cpi",      "view=monthly&years=5",          "Chỉ số giá tiêu dùng theo tháng"),
    ("GDP",             "api/v1/macro/gdp",      "",                              "GDP theo quý và khu vực"),
    ("Xuất nhập khẩu",  "api/v1/macro/trade",    "",                              "Kim ngạch XNK theo tháng"),
]

BRAND = "2F5FDE"      # brand blue, matches the site
INK = "141413"
MUTED = "5E5D59"
PAPER = "FAF9F5"


def _title(cell, text, size=16):
    cell.value = text
    cell.font = Font(name="Calibri", size=size, bold=True, color=INK)


def _muted(cell, text, size=11):
    cell.value = text
    cell.font = Font(name="Calibri", size=size, color=MUTED)
    cell.alignment = Alignment(wrap_text=True, vertical="top")


def build_start_sheet(wb):
    ws = wb.active
    ws.title = "Bắt đầu"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 78

    _title(ws["B2"], "Viet Dataverse — Dữ liệu kinh tế Việt Nam")
    _muted(ws["B3"], "Dán API key vào ô bên phải, rồi bấm nút CẬP NHẬT DỮ LIỆU. "
                     "Mỗi sheet là một bộ dữ liệu, tự tải lại từ API mỗi lần bấm.")

    ws["B5"].value = "API KEY"
    ws["B5"].font = Font(bold=True, color=INK)
    key_cell = ws["C5"]
    key_cell.value = ""
    key_cell.fill = PatternFill("solid", fgColor="FFF6DA")
    key_cell.font = Font(name="Consolas", size=12)
    key_cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[5].height = 26
    # Named so the macro never hardcodes a cell address, and so a user who
    # inserts a row above does not silently break the lookup.
    wb.defined_names.add(DefinedName("API_KEY", attr_text="'Bắt đầu'!$C$5"))

    ws["B6"].value = "Trạng thái"
    ws["B6"].font = Font(bold=True, color=INK)
    _muted(ws["C6"], "Chưa chạy lần nào.")
    wb.defined_names.add(DefinedName("STATUS", attr_text="'Bắt đầu'!$C$6"))

    _title(ws["B8"], "Cách dùng", size=13)
    steps = [
        "1. Lấy API key tại vietdataverse.online/pages/developer.html (đăng nhập → Tạo API key).",
        "2. Dán key vào ô vàng ở trên.",
        "3. Bấm nút CẬP NHẬT DỮ LIỆU. Lần đầu Excel có thể hỏi cho phép macro — chọn Enable.",
        "4. Mỗi sheet sẽ được ghi đè bằng dữ liệu mới nhất.",
    ]
    for i, line in enumerate(steps):
        _muted(ws.cell(row=9 + i, column=3), line)

    _title(ws["B14"], "Nếu nút không chạy", size=13)
    warn = [
        "Windows chặn macro trong file tải từ internet. Đóng Excel, chuột phải vào file → "
        "Properties → tick Unblock → OK, rồi mở lại. Đây là bước bắt buộc một lần duy nhất.",
        "Nếu báo lỗi 401: key sai, đã bị thu hồi, hoặc gói đã hết hạn.",
        "Nếu báo lỗi 429: đã hết lượt gọi trong tháng. Gói miễn phí chỉ 2 lượt/tháng.",
        "Trên macOS, nút này không chạy (Excel cho Mac không có thư viện HTTP mà macro dùng). "
        "Dùng add-in Viet Dataverse hoặc Power Query thay thế.",
    ]
    for i, line in enumerate(warn):
        _muted(ws.cell(row=15 + i, column=3), line)
        ws.row_dimensions[15 + i].height = 30

    _muted(ws["C20"], "Dữ liệu thuộc Viet Dataverse. Nguồn gốc từng bộ ghi trong sheet Cấu hình.")
    return ws


def build_config_sheet(wb):
    """The macro's input. Datasets are DATA, not code — see module docstring."""
    ws = wb.create_sheet("Cấu hình")
    ws.sheet_view.showGridLines = False
    headers = ["Sheet", "Endpoint", "Tham số", "Mô tả"]
    widths = [20, 26, 34, 46]
    for col, (head, width) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=1, column=col, value=head)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
        ws.column_dimensions[get_column_letter(col)].width = width
    for r, (sheet, path, query, desc) in enumerate(DATASETS, start=2):
        ws.cell(row=r, column=1, value=sheet)
        ws.cell(row=r, column=2, value=path)
        ws.cell(row=r, column=3, value=query)
        ws.cell(row=r, column=4, value=desc)

    note_row = len(DATASETS) + 3
    _muted(ws.cell(row=note_row, column=1),
           "Sửa cột Tham số để đổi khoảng thời gian (period=7d/1m/1y/all), ngân hàng, loại vàng… "
           "Macro đọc bảng này nên thêm dòng là thêm bộ dữ liệu, không cần sửa macro.")
    ws.cell(row=note_row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=4)
    ws.row_dimensions[note_row].height = 34
    wb.defined_names.add(DefinedName("API_BASE", attr_text=f'"{API_BASE}"'))
    return ws


def build_data_sheets(wb):
    for sheet, path, query, desc in DATASETS:
        ws = wb.create_sheet(sheet)
        ws.sheet_view.showGridLines = False
        _muted(ws["A1"], f"{desc} — {API_BASE}/{path}?{query}" if query
               else f"{desc} — {API_BASE}/{path}")
        ws["A1"].font = Font(size=9, color=MUTED, italic=True)
        _muted(ws["A2"], "Bấm CẬP NHẬT DỮ LIỆU ở sheet \"Bắt đầu\" để nạp dữ liệu vào đây.")
        ws.column_dimensions["A"].width = 16
        for col in "BCDEFGH":
            ws.column_dimensions[col].width = 15


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    build_start_sheet(wb)
    build_config_sheet(wb)
    build_data_sheets(wb)
    wb.save(XLSX)
    print(f"  {XLSX.relative_to(ROOT)}  ({XLSX.stat().st_size:,} bytes, {len(wb.sheetnames)} sheets)")

    if not VBA_BIN.exists():
        print(f"  {VBA_BIN.relative_to(ROOT)} chưa có → chưa dựng được .xlsm (nút bấm).")
        print("  Xem hướng dẫn một lần duy nhất ở đầu file này.")
        return

    # openpyxl cannot write .xlsm with VBA, so the macro part is injected into
    # a copy of the zip directly. This is exactly what Excel stores: the binary
    # at xl/vbaProject.bin plus a content-type override for it.
    shutil.copy(XLSX, XLSM)
    with zipfile.ZipFile(XLSM, "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(VBA_BIN, "xl/vbaProject.bin")
    _patch_content_types(XLSM)
    print(f"  {XLSM.relative_to(ROOT)}  ({XLSM.stat().st_size:,} bytes) — bản có nút bấm")


def _patch_content_types(path: Path):
    """Register the VBA part and switch the workbook to the macro-enabled type.

    A .xlsm that keeps the .xlsx content type opens with the macros silently
    stripped — Excel gives no warning, the button simply is not there.
    """
    tmp = path.with_suffix(".tmp.zip")
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text = data.decode("utf-8")
                if "vbaProject" not in text:
                    text = text.replace(
                        "</Types>",
                        '<Default Extension="bin" ContentType="application/vnd.ms-office.vbaProject"/>'
                        "</Types>")
                text = text.replace(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                    "application/vnd.ms-excel.sheet.macroEnabled.main+xml")
                data = text.encode("utf-8")
            elif item.filename == "xl/_rels/workbook.xml.rels":
                text = data.decode("utf-8")
                if "vbaProject" not in text:
                    text = text.replace(
                        "</Relationships>",
                        '<Relationship Id="rIdVBA" '
                        'Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" '
                        'Target="vbaProject.bin"/></Relationships>')
                data = text.encode("utf-8")
            dst.writestr(item, data)
    tmp.replace(path)


if __name__ == "__main__":
    print("Dựng workbook Viet Dataverse…")
    build()
