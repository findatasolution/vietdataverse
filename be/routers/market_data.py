import json
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_crawl, get_engine_global
from core.config import ALLOWED_BANKS, ALLOWED_CURRENCIES
from core.utils import get_date_filter

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


@router.get("/api/v1/gold")
async def get_gold_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
    type: str = Query("DOJI HN", description="Gold type"),
):
    try:
        date_filter = get_date_filter(period)
        query = text("""
            SELECT date, buy_price, sell_price
            FROM (
                SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
                FROM vn_macro_gold_daily
                WHERE date >= :date_filter AND type = :gold_type
                ORDER BY date, crawl_time DESC
            ) s ORDER BY date DESC
        """)
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(query, {"date_filter": date_filter, "gold_type": type}).fetchall()

        dates = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        buy   = [float(r[1]) if r[1] else 0 for r in rows]
        sell  = [float(r[2]) if r[2] else 0 for r in rows]

        return _json_response({
            "success": True,
            "data": {"dates": dates[::-1], "buy_prices": buy[::-1], "sell_prices": sell[::-1]},
            "type": type, "period": period, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold data: {e}")


@router.get("/api/v1/gold/types")
async def get_gold_types(request: Request):
    try:
        # Loại silver (BẠC) bị crawl nhầm vào bảng gold — filter tại query layer
        # cho đến khi data cleanup + crawler fix xong.
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT DISTINCT type FROM vn_macro_gold_daily
                WHERE type IS NOT NULL
                  AND type NOT ILIKE '%BẠC%'
                  AND type NOT ILIKE '%BAC %'
                ORDER BY type
            """)).fetchall()
        return _json_response({"success": True, "types": [r[0] for r in rows if r[0]]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold types: {e}")


@router.get("/api/v1/silver")
async def get_silver_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
):
    try:
        date_filter = get_date_filter(period)
        query = text("""
            SELECT date, buy_price, sell_price
            FROM (
                SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
                FROM vn_macro_silver_daily
                WHERE date >= :date_filter
                ORDER BY date, crawl_time DESC
            ) s ORDER BY date DESC
        """)
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(query, {"date_filter": date_filter}).fetchall()

        dates = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        buy   = [float(r[1]) if r[1] else 0 for r in rows]
        sell  = [float(r[2]) if r[2] else 0 for r in rows]

        return _json_response({
            "success": True,
            "data": {"dates": dates[::-1], "buy_prices": buy[::-1], "sell_prices": sell[::-1]},
            "period": period, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch silver data: {e}")


@router.get("/api/v1/sbv-interbank")
async def get_sbv_interbank_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
):
    try:
        date_filter = get_date_filter(period)
        query = text("""
            SELECT date, ls_quadem, ls_1m, ls_3m, ls_6m, ls_9m,
                   rediscount_rate, refinancing_rate
            FROM (
                SELECT DISTINCT ON (date) date, ls_quadem, ls_1m, ls_3m, ls_6m, ls_9m,
                       rediscount_rate, refinancing_rate, crawl_time
                FROM vn_macro_sbv_rate_daily
                WHERE date >= :date_filter
                ORDER BY date, crawl_time DESC
            ) s ORDER BY date DESC
        """)
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(query, {"date_filter": date_filter}).fetchall()

        dates       = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        overnight   = [float(r[1]) if r[1] else None for r in rows]
        month_1     = [float(r[2]) if r[2] else None for r in rows]
        month_3     = [float(r[3]) if r[3] else None for r in rows]
        month_6     = [float(r[4]) if r[4] else None for r in rows]
        month_9     = [float(r[5]) if r[5] else None for r in rows]
        rediscount  = [float(r[6]) if r[6] else None for r in rows]
        refinancing = [float(r[7]) if r[7] else None for r in rows]

        return _json_response({
            "success": True,
            "data": {
                "dates": dates[::-1],
                "overnight": overnight[::-1], "month_1": month_1[::-1],
                "month_3": month_3[::-1],     "month_6": month_6[::-1],
                "month_9": month_9[::-1],
                "rediscount": rediscount[::-1], "refinancing": refinancing[::-1],
            },
            "period": period, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch SBV data: {e}")


@router.get("/api/v1/sbv-centralrate")
async def get_sbv_central_rate(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
    bank: str = Query("SBV", description="Bank code"),
    currency: str = Query("USD", description="Currency code"),
):
    try:
        bank_upper     = bank.upper()
        currency_upper = currency.upper()

        if bank_upper not in ALLOWED_BANKS:
            raise HTTPException(status_code=400, detail=f"Bank không hợp lệ. Cho phép: {sorted(ALLOWED_BANKS)}")
        if currency_upper not in ALLOWED_CURRENCIES:
            raise HTTPException(status_code=400, detail=f"Currency không hợp lệ. Cho phép: {sorted(ALLOWED_CURRENCIES)}")

        # rate_col is a column name validated against allowlist — safe to interpolate
        rate_col    = "usd_vnd_rate" if bank_upper == "SBV" else "buy_transfer"
        date_filter = get_date_filter(period)

        query = text(f"""
            SELECT date, {rate_col}, buy_cash, sell_rate
            FROM (
                SELECT DISTINCT ON (date) date, {rate_col}, buy_cash, sell_rate, crawl_time
                FROM vn_macro_fxrate_daily
                WHERE date >= :date_filter AND type = :currency AND bank = :bank
                  AND {rate_col} IS NOT NULL
                ORDER BY date, crawl_time DESC
            ) s ORDER BY date DESC
        """)

        with get_engine_crawl().connect() as conn:
            rows = conn.execute(query, {
                "date_filter": date_filter, "currency": currency_upper, "bank": bank_upper
            }).fetchall()

        dates     = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        rates     = [float(r[1]) if r[1] else 0    for r in rows]
        buy_cash  = [float(r[2]) if r[2] else None for r in rows]
        sell      = [float(r[3]) if r[3] else None for r in rows]

        return _json_response({
            "success": True,
            "data": {
                "dates": dates[::-1], "usd_vnd_rate": rates[::-1],
                "buy_cash": buy_cash[::-1], "sell_rate": sell[::-1],
            },
            "period": period, "bank": bank_upper, "currency": currency_upper, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch exchange rate: {e}")


@router.get("/api/v1/termdepo")
async def get_term_deposit_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
    bank: str = Query("ACB", description="Bank code"),
):
    try:
        date_filter = get_date_filter(period)
        query = text("""
            SELECT date, term_1m, term_3m, term_6m, term_12m, term_24m
            FROM (
                SELECT DISTINCT ON (date_trunc('month', date))
                       date, term_1m, term_3m, term_6m, term_12m, term_24m, crawl_time
                FROM vn_macro_termdepo_daily
                WHERE date >= :date_filter AND bank_code = :bank_code
                ORDER BY date_trunc('month', date), date DESC, crawl_time DESC
            ) s ORDER BY date DESC
        """)
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(query, {"date_filter": date_filter, "bank_code": bank}).fetchall()

        dates    = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        term_1m  = [float(r[1]) if r[1] else 0 for r in rows]
        term_3m  = [float(r[2]) if r[2] else 0 for r in rows]
        term_6m  = [float(r[3]) if r[3] else 0 for r in rows]
        term_12m = [float(r[4]) if r[4] else 0 for r in rows]
        term_24m = [float(r[5]) if r[5] else 0 for r in rows]

        return _json_response({
            "success": True,
            "data": {
                "dates": dates[::-1], "term_1m": term_1m[::-1], "term_3m": term_3m[::-1],
                "term_6m": term_6m[::-1], "term_12m": term_12m[::-1], "term_24m": term_24m[::-1],
            },
            "bank": bank, "period": period, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch term deposit data: {e}")


@router.get("/api/v1/termdepo/banks")
async def get_bank_types(request: Request):
    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text(
                "SELECT DISTINCT bank_code FROM vn_macro_termdepo_daily WHERE bank_code IS NOT NULL ORDER BY bank_code"
            )).fetchall()
        return _json_response({"success": True, "banks": [r[0] for r in rows if r[0]]})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bank types: {e}")


@router.get("/api/v1/global-macro")
async def get_global_macro_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
):
    try:
        date_filter = get_date_filter(period)
        query = text("""
            SELECT date, gold_price, silver_price, nasdaq_price
            FROM (
                SELECT DISTINCT ON (date) date, gold_price, silver_price, nasdaq_price, crawl_time
                FROM global_macro
                WHERE date >= :date_filter
                ORDER BY date, crawl_time DESC
            ) s ORDER BY date DESC
        """)
        with get_engine_global().connect() as conn:
            rows = conn.execute(query, {"date_filter": date_filter}).fetchall()

        dates   = [r[0].strftime("%Y-%m-%d") if hasattr(r[0], "strftime") else str(r[0]) for r in rows]
        gold    = [float(r[1]) if r[1] else 0 for r in rows]
        silver  = [float(r[2]) if r[2] else 0 for r in rows]
        nasdaq  = [float(r[3]) if r[3] else 0 for r in rows]

        return _json_response({
            "success": True,
            "data": {
                "dates": dates[::-1], "gold_prices": gold[::-1],
                "silver_prices": silver[::-1], "nasdaq_prices": nasdaq[::-1],
            },
            "period": period, "count": len(dates),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch global macro data: {e}")
