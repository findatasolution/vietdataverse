"""Cross-platform Excel export and in-workbook refresh payload.

The generated file is a normal ``.xlsx``. Refresh is handled by the existing
Office.js add-in, which runs on Excel for Mac, Windows and the web; no VBA or
locally-authored Power Query ``DataMashup`` binary is required.

Both routes are covered by the normal API-key middleware. Calling the existing
dataset handlers in-process keeps their SQL and null handling as the source of
truth. The outer Excel request is metered once, rather than charging nine calls
for one refresh.
"""
import csv
import io
import zipfile
from datetime import date, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from routers import market_data, vn30_data

router = APIRouter()

BRAND = "2F5FDE"
INK = "141413"
MUTED = "5E5D59"
ADDIN_ID = "A3F7C2D1-4E8B-4A9C-B1D5-2F3E4A5B6C7D"
ADDIN_VERSION = "1.0.0.0"


def _datasets(period: str):
    """Dataset configuration shared by workbook generation and refresh."""
    return [
        ("gold", "Vàng SJC", "VDVGold", market_data.get_gold_data,
         {"period": period, "type": "SJC", "page": None, "limit": 30},
         "Giá vàng SJC mua vào / bán ra theo ngày", "gold"),
        ("silver", "Bạc", "VDVSilver", market_data.get_silver_data,
         {"period": period, "page": None, "limit": 30},
         "Giá bạc Phú Quý theo ngày", "silver"),
        ("interbank", "Lãi suất LNH", "VDVInterbank", market_data.get_sbv_interbank_data,
         {"period": period},
         "Lãi suất liên ngân hàng + lãi suất điều hành SBV", "sbv-interbank"),
        ("fx", "Tỷ giá", "VDVFx", market_data.get_sbv_central_rate,
         {"period": period, "bank": "SBV", "currency": "USD", "page": None, "limit": 30},
         "Tỷ giá trung tâm USD/VND", "sbv-rate"),
        ("deposit", "Tiền gửi ACB", "VDVDeposit", market_data.get_term_deposit_data,
         {"period": period, "bank": "ACB", "page": None, "limit": 30},
         "Lãi suất tiền gửi theo kỳ hạn", "termdepo"),
        ("global", "Thế giới", "VDVGlobal", market_data.get_global_macro_data,
         {"period": period, "symbol": None, "page": None, "limit": 30},
         "Vàng, bạc, NASDAQ thế giới", "global-macro"),
        ("cpi", "CPI", "VDVCpi", vn30_data.get_macro_cpi,
         {"view": "monthly", "years": 5, "_auth": None},
         "Chỉ số giá tiêu dùng theo tháng", "macro/cpi"),
        ("gdp", "GDP", "VDVGdp", vn30_data.get_macro_gdp,
         {"_auth": None},
         "GDP theo quý và khu vực", "macro/gdp"),
        ("trade", "Xuất nhập khẩu", "VDVTrade", vn30_data.get_macro_trade,
         {"months": 24, "_auth": None},
         "Kim ngạch xuất nhập khẩu theo tháng", "macro/trade"),
    ]


def _coerce(value: str):
    """Turn CSV text into useful Excel/JSON scalar values."""
    if value is None or value == "":
        return None
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        return int(value) if value.lstrip("-").isdigit() else float(value)
    except ValueError:
        return value


async def _collect_datasets(request: Request, period: str) -> list[dict]:
    collected = []
    for dataset_id, title, table_name, fn, kwargs, description, endpoint in _datasets(period):
        item = {
            "id": dataset_id,
            "sheet": title,
            "table": table_name,
            "description": description,
            "endpoint": f"/api/v1/{endpoint}",
            "headers": [],
            "rows": [],
            "error": None,
        }
        try:
            response = await fn(request, format="csv", **kwargs)
            text = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
            parsed = list(csv.reader(io.StringIO(text)))
            if parsed:
                item["headers"] = parsed[0]
                item["rows"] = [[_coerce(value) for value in row] for row in parsed[1:]]
        except Exception:
            # One unavailable source must not discard the other eight. Keep
            # operational details out of the customer-facing response.
            item["error"] = "Dữ liệu tạm thời chưa tải được. Hãy thử refresh lại sau."
        collected.append(item)
    return collected


def _write_dataset_sheet(wb: Workbook, item: dict, base_url: str) -> int:
    ws = wb.create_sheet(item["sheet"])
    ws.sheet_view.showGridLines = False
    ws["A1"] = item["description"]
    ws["A1"].font = Font(size=9, italic=True, color=MUTED)
    ws["A2"] = f"{base_url}{item['endpoint']}"
    ws["A2"].font = Font(size=9, color=MUTED)

    headers = item["headers"]
    rows = item["rows"]
    if not headers:
        ws["A4"] = item["error"] or "Không có dữ liệu trong kỳ này."
        ws["A4"].font = Font(color=MUTED)
        return 0

    for column, heading in enumerate(headers, start=1):
        ws.cell(row=4, column=column, value=heading)
        ws.column_dimensions[get_column_letter(column)].width = max(12, len(heading) + 3)
    for row_index, row in enumerate(rows, start=5):
        for column, value in enumerate(row, start=1):
            cell = ws.cell(row=row_index, column=column, value=value)
            if isinstance(value, date):
                cell.number_format = "dd/mm/yyyy"

    # A table gives the add-in a stable refresh target. Keep one blank row for
    # a dataset with headers but no current observations.
    last_row = max(5, 4 + len(rows))
    last_column = get_column_letter(len(headers))
    table = Table(displayName=item["table"], ref=f"A4:{last_column}{last_row}")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2", showFirstColumn=False,
        showLastColumn=False, showRowStripes=True, showColumnStripes=False,
    )
    ws.add_table(table)
    ws.freeze_panes = "A5"
    return len(rows)


def _cover(wb: Workbook, period: str, summary: list[tuple]) -> None:
    ws = wb.active
    ws.title = "Bắt đầu"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 27
    ws.column_dimensions["C"].width = 68
    ws.column_dimensions["D"].width = 14

    ws["B2"] = "Viet Dataverse — Dữ liệu kinh tế Việt Nam"
    ws["B2"].font = Font(size=16, bold=True, color=INK)
    ws["B3"] = "Workbook có thể refresh trực tiếp bằng Viet Dataverse Excel Add-in."
    ws["B3"].font = Font(size=11, color=MUTED)

    ws["B5"] = "REFRESH TRONG EXCEL"
    ws["B5"].font = Font(size=13, bold=True, color=BRAND)
    ws["C5"] = ("Cài add-in một lần, rồi mở Home → Viet Dataverse → "
                 "Refresh toàn bộ workbook. Chạy trên Excel Mac, Windows và web.")
    ws["C5"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[5].height = 34

    ws["B7"] = "Khoảng thời gian"
    ws["C7"] = period
    ws["B8"] = "Cập nhật gần nhất"
    ws["C8"] = datetime.now()
    ws["C8"].number_format = "dd/mm/yyyy hh:mm"

    ws["B10"] = "CÀI VIET DATAVERSE ADD-IN"
    ws["B10"].hyperlink = "https://api.vietdataverse.online/excel-addin/manifest.xml"
    ws["B10"].font = Font(bold=True, color="0563C1", underline="single")
    ws["C10"] = "Chỉ cần cài một lần. API key được lưu trong add-in, không nằm trong file này."
    ws["C10"].font = Font(size=10, color=MUTED)

    ws["B12"] = "Bộ dữ liệu trong file"
    ws["B12"].font = Font(size=13, bold=True, color=INK)
    for column, heading in enumerate(["Sheet", "Nội dung", "Số dòng"], start=2):
        cell = ws.cell(row=13, column=column, value=heading)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BRAND)
    for index, (name, description, count) in enumerate(summary, start=14):
        ws.cell(row=index, column=2, value=name)
        ws.cell(row=index, column=3, value=description)
        ws.cell(row=index, column=4, value=count)

    from openpyxl.workbook.defined_name import DefinedName
    wb.defined_names.add(DefinedName("VDV_WORKBOOK_VERSION", attr_text='"1"'))
    wb.defined_names.add(DefinedName("VDV_PERIOD", attr_text="'Bắt đầu'!$C$7"))
    wb.defined_names.add(DefinedName("VDV_LAST_REFRESH", attr_text="'Bắt đầu'!$C$8"))


def _embed_addin(workbook_bytes: bytes) -> bytes:
    """Embed the Office Add-in reference using standard Open XML parts."""
    source = io.BytesIO(workbook_bytes)
    output = io.BytesIO()
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "[Content_Types].xml":
                text = data.decode("utf-8").replace(
                    "</Types>",
                    '<Override PartName="/xl/webextensions/taskpanes.xml" '
                    'ContentType="application/vnd.ms-office.webextensiontaskpanes+xml"/>'
                    '<Override PartName="/xl/webextensions/webextension1.xml" '
                    'ContentType="application/vnd.ms-office.webextension+xml"/>'
                    "</Types>",
                )
                data = text.encode("utf-8")
            elif info.filename == "xl/_rels/workbook.xml.rels":
                text = data.decode("utf-8").replace(
                    "</Relationships>",
                    '<Relationship Id="rIdVDVTaskpanes" '
                    'Type="http://schemas.microsoft.com/office/2011/relationships/webextensiontaskpanes" '
                    'Target="webextensions/taskpanes.xml"/></Relationships>',
                )
                data = text.encode("utf-8")
            dst.writestr(info, data)

        dst.writestr(
            "xl/webextensions/taskpanes.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<wetp:taskpanes xmlns:wetp="http://schemas.microsoft.com/office/webextensions/taskpanes/2010/11">'
            '<wetp:taskpane dockstate="right" visibility="0" width="350" row="4">'
            '<wetp:webextensionref xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            'r:id="rId1"/></wetp:taskpane></wetp:taskpanes>',
        )
        dst.writestr(
            "xl/webextensions/_rels/taskpanes.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.microsoft.com/office/2011/relationships/webextension" '
            'Target="webextension1.xml"/></Relationships>',
        )
        dst.writestr(
            "xl/webextensions/webextension1.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<we:webextension xmlns:we="http://schemas.microsoft.com/office/webextensions/webextension/2010/11" '
            f'id="{{{ADDIN_ID}}}"><we:reference id="{ADDIN_ID}" version="{ADDIN_VERSION}" '
            'store="developer" storeType="Registry"/><we:alternateReferences/><we:properties>'
            '<we:property name="Office.AutoShowTaskpaneWithDocument" value="true"/>'
            '</we:properties><we:bindings/><we:snapshot '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
            '</we:webextension>',
        )
    return output.getvalue()


@router.get("/api/v1/excel/refresh-data")
async def excel_refresh_data(
    request: Request,
    period: str = Query("1y", pattern="^(7d|1m|1y|all)$"),
):
    """Return every workbook dataset in one metered refresh call."""
    datasets = await _collect_datasets(request, period)
    return {
        "success": all(item["error"] is None for item in datasets),
        "source": "Viet Dataverse",
        "period": period,
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(datasets),
        "data": datasets,
    }


@router.get("/api/v1/excel/workbook")
async def excel_workbook(
    request: Request,
    period: str = Query("1y", pattern="^(7d|1m|1y|all)$",
                        description="Khoảng thời gian cho các bộ theo ngày"),
):
    """Return a populated workbook wired for Office.js refresh."""
    datasets = await _collect_datasets(request, period)
    wb = Workbook()
    base_url = str(request.base_url).rstrip("/")
    summary = []
    for item in datasets:
        count = _write_dataset_sheet(wb, item, base_url)
        summary.append((item["sheet"], item["description"], count))
    _cover(wb, period, summary)
    wb.move_sheet("Bắt đầu", offset=-len(summary))

    buffer = io.BytesIO()
    wb.save(buffer)
    raw = _embed_addin(buffer.getvalue())
    stamp = datetime.now().strftime("%Y%m%d")
    return Response(
        content=raw,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="VietDataverse-{period}-{stamp}.xlsx"',
            "Content-Length": str(len(raw)),
        },
    )
