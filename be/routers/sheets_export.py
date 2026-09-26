"""Datasets for the Google Sheets connector, in one metered request.

The bound Apps Script in `integrations/google-sheets/Code.gs` calls
``/api/v1/excel/refresh-data`` once per refresh and writes the nine datasets
into the customer's spreadsheet.

**The route keeps the word "excel" for a reason: do not rename it.** That path
is compiled into every copy of the Google Sheets template already in customers'
Drives, and those copies are not ours to update. It also anchors the
``/api/v1/excel`` entry in ``METERED_PREFIXES`` (``be/main.py``), which is what
gates and meters this data.

Calling the existing dataset handlers in-process keeps their SQL and null
handling as the single source of truth, and meters one outer request rather
than charging nine.

History: this module also generated a downloadable .xlsx wired to an Office.js
add-in. Both were removed on 2026-09-25 when the product narrowed to two
delivery flows — the raw API and Google Sheets.
"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Query, Request

from routers import market_data, vn30_data

router = APIRouter()


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

