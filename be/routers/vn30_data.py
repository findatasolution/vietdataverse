"""
VN30 Financial Data API Router
- /api/v1/vn30/profile         — Free: company list + sector classification
- /api/v1/vn30/sector-summary  — Free: aggregate metrics by ICB sector
- /api/v1/vn30/prices/{ticker} — Premium: OHLCV price history
- /api/v1/vn30/financials/{ticker} — Premium: quarterly BCTC
- /api/v1/vn30/ratios/{ticker} — Premium: financial ratios history
- /api/v1/macro/cpi            — Free: CPI monthly
- /api/v1/macro/gdp            — Free: GDP quarterly
- /api/v1/macro/trade          — Free: Import/export monthly
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_crawl, get_engine_corp
from middleware import authenticate_user_optional

router = APIRouter()

PREMIUM_LEVELS = ("premium", "premium_developer", "admin")


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _is_premium(request: Request) -> bool:
    user = getattr(request.state, "user", None)
    user_level = (user or {}).get("user_level", "free")
    return user_level in PREMIUM_LEVELS


# ─────────────────────────────────────────────────────────────
# VN30 COMPANY PROFILE (Free)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/profile")
async def get_vn30_profile(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 company list with sector classification — free access."""
    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT ticker, company_name, company_name_en, exchange,
                       icb_sector, icb_industry, icb_supersector, icb_code,
                       market_cap_billion, updated_at
                FROM vn30_company_profile
                ORDER BY market_cap_billion DESC NULLS LAST
            """)).fetchall()

        data = [{
            "ticker": r[0],
            "company_name": r[1],
            "company_name_en": r[2],
            "exchange": r[3],
            "icb_sector": r[4],
            "icb_industry": r[5],
            "icb_supersector": r[6],
            "icb_code": r[7],
            "market_cap_billion": r[8],
            "updated_at": str(r[9]) if r[9] else None,
        } for r in rows]

        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch VN30 profile: {e}")


# ─────────────────────────────────────────────────────────────
# SECTOR SUMMARY (Free)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/sector-summary")
async def get_sector_summary(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """Aggregate financial metrics by ICB sector — free access."""
    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    p.icb_sector,
                    COUNT(DISTINCT p.ticker) AS num_companies,
                    ROUND(AVG(r.pe)::numeric, 2) AS avg_pe,
                    ROUND(AVG(r.pb)::numeric, 2) AS avg_pb,
                    ROUND(AVG(r.roe)::numeric, 2) AS avg_roe,
                    ROUND(SUM(p.market_cap_billion)::numeric, 0) AS total_market_cap
                FROM vn30_company_profile p
                LEFT JOIN (
                    SELECT DISTINCT ON (ticker) ticker, pe, pb, roe
                    FROM vn30_ratio_daily
                    ORDER BY ticker, date DESC
                ) r ON r.ticker = p.ticker
                WHERE p.icb_sector IS NOT NULL AND p.icb_sector != ''
                GROUP BY p.icb_sector
                ORDER BY total_market_cap DESC NULLS LAST
            """)).fetchall()

        data = [{
            "icb_sector": r[0],
            "num_companies": r[1],
            "avg_pe": float(r[2]) if r[2] is not None else None,
            "avg_pb": float(r[3]) if r[3] is not None else None,
            "avg_roe": float(r[4]) if r[4] is not None else None,
            "total_market_cap_billion": float(r[5]) if r[5] is not None else None,
        } for r in rows]

        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sector summary: {e}")


# ─────────────────────────────────────────────────────────────
# VN30 OHLCV PRICES (Premium)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/prices/{ticker}")
async def get_vn30_prices(
    ticker: str,
    request: Request,
    period: str = Query(default="1m", description="1m, 7d, 1y"),
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 OHLCV price history — premium only."""
    if not _is_premium(request):
        raise HTTPException(status_code=403,
                            detail="Chỉ tài khoản Premium mới xem được dữ liệu giá. Vui lòng nâng cấp.")

    period_days = {"7d": 7, "1m": 30, "1y": 365}.get(period, 30)

    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT date, open, high, low, close, volume, value
                FROM vn30_ohlcv_daily
                WHERE ticker = :ticker
                  AND date >= CURRENT_DATE - INTERVAL ':days days'
                ORDER BY date ASC
            """.replace(':days', str(period_days))), {"ticker": ticker.upper()}).fetchall()

        data = [{
            "date": str(r[0]),
            "open": r[1], "high": r[2], "low": r[3], "close": r[4],
            "volume": r[5], "value": r[6],
        } for r in rows]

        return _json_response({
            "success": True,
            "ticker": ticker.upper(),
            "period": period,
            "count": len(data),
            "data": data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch prices for {ticker}: {e}")


# ─────────────────────────────────────────────────────────────
# VN30 FINANCIAL STATEMENTS (Premium)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/financials/{ticker}")
async def get_vn30_financials(
    ticker: str,
    request: Request,
    quarters: int = Query(default=8, ge=1, le=20),
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 quarterly financial statements — premium only."""
    if not _is_premium(request):
        raise HTTPException(status_code=403,
                            detail="Chỉ tài khoản Premium mới xem được BCTC. Vui lòng nâng cấp.")

    ticker = ticker.upper()
    try:
        with get_engine_crawl().connect() as conn:
            income = conn.execute(text("""
                SELECT year, quarter, revenue, gross_profit, ebit, net_income, eps
                FROM vn30_income_stmt_quarterly WHERE ticker = :ticker
                ORDER BY year DESC, quarter DESC LIMIT :q
            """), {"ticker": ticker, "q": quarters}).fetchall()

            bs = conn.execute(text("""
                SELECT year, quarter, total_assets, total_liabilities, equity, cash
                FROM vn30_balance_sheet_quarterly WHERE ticker = :ticker
                ORDER BY year DESC, quarter DESC LIMIT :q
            """), {"ticker": ticker, "q": quarters}).fetchall()

            cf = conn.execute(text("""
                SELECT year, quarter, cfo, cfi, cff, free_cashflow
                FROM vn30_cashflow_quarterly WHERE ticker = :ticker
                ORDER BY year DESC, quarter DESC LIMIT :q
            """), {"ticker": ticker, "q": quarters}).fetchall()

        return _json_response({
            "success": True,
            "ticker": ticker,
            "income_statement": [
                {"year": r[0], "quarter": r[1], "revenue": r[2], "gross_profit": r[3],
                 "ebit": r[4], "net_income": r[5], "eps": r[6]} for r in income
            ],
            "balance_sheet": [
                {"year": r[0], "quarter": r[1], "total_assets": r[2],
                 "total_liabilities": r[3], "equity": r[4], "cash": r[5]} for r in bs
            ],
            "cash_flow": [
                {"year": r[0], "quarter": r[1], "cfo": r[2], "cfi": r[3],
                 "cff": r[4], "free_cashflow": r[5]} for r in cf
            ],
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch financials for {ticker}: {e}")


# ─────────────────────────────────────────────────────────────
# VN30 FINANCIAL RATIOS (Premium)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/ratios/{ticker}")
async def get_vn30_ratios(
    ticker: str,
    request: Request,
    period: str = Query(default="1m", description="7d, 1m, 1y"),
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 financial ratios history — premium only."""
    if not _is_premium(request):
        raise HTTPException(status_code=403,
                            detail="Chỉ tài khoản Premium mới xem được tỷ số tài chính. Vui lòng nâng cấp.")

    period_days = {"7d": 7, "1m": 30, "1y": 365}.get(period, 30)

    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT date, pe, pb, ps, roe, roa, eps, dividend_yield, market_cap_billion
                FROM vn30_ratio_daily
                WHERE ticker = :ticker
                  AND date >= CURRENT_DATE - INTERVAL ':days days'
                ORDER BY date ASC
            """.replace(':days', str(period_days))), {"ticker": ticker.upper()}).fetchall()

        data = [{
            "date": str(r[0]), "pe": r[1], "pb": r[2], "ps": r[3],
            "roe": r[4], "roa": r[5], "eps": r[6],
            "dividend_yield": r[7], "market_cap_billion": r[8],
        } for r in rows]

        return _json_response({
            "success": True,
            "ticker": ticker.upper(),
            "period": period,
            "count": len(data),
            "data": data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ratios for {ticker}: {e}")


# ─────────────────────────────────────────────────────────────
# MACRO: CPI (Free)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/macro/cpi")
async def get_macro_cpi(
    request: Request,
    view: str = Query(default="annual", description="'annual' = 1 point/year | 'monthly' = 1 point/month"),
    years: int = Query(default=20, ge=1, le=30),
    _auth: None = Depends(authenticate_user_optional),
):
    """Vietnam CPI data from GSO (vn_gso_cpi_monthly). Source: nso.gov.vn"""
    try:
        with get_engine_crawl().connect() as conn:
            if view == "monthly":
                # Last N months — for 1-year chart (monthly points)
                rows = conn.execute(text("""
                    SELECT period, cpi_mom_pct, cpi_yoy_pct
                    FROM vn_gso_cpi_monthly
                    WHERE cpi_yoy_pct IS NOT NULL
                    ORDER BY period DESC
                    LIMIT :limit
                """), {"limit": years * 12}).fetchall()
                data = [{"period": r[0], "mom_pct": r[1], "yoy_pct": r[2]}
                        for r in reversed(rows)]
            else:
                # Annual aggregate — avg yoy per year, for 20-year bar chart
                rows = conn.execute(text("""
                    SELECT LEFT(period, 4)            AS yr,
                           ROUND(AVG(cpi_yoy_pct)::numeric, 2) AS avg_yoy,
                           COUNT(*)                   AS months
                    FROM vn_gso_cpi_monthly
                    WHERE cpi_yoy_pct IS NOT NULL
                      AND LEFT(period, 4) >= :from_yr
                    GROUP BY LEFT(period, 4)
                    ORDER BY yr
                """), {"from_yr": str(2026 - years)}).fetchall()
                data = [{"period": r[0], "yoy_pct": float(r[1]), "months": r[2]}
                        for r in rows]

        return _json_response({
            "success": True, "view": view, "source": "GSO/NSO vn_gso_cpi_monthly",
            "count": len(data), "data": data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch CPI: {e}")


# ─────────────────────────────────────────────────────────────
# MACRO: GDP (Free)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/macro/gdp")
async def get_macro_gdp(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """Vietnam GDP quarterly data — free access."""
    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT year, quarter, sector, gdp_billion_vnd, growth_yoy_pct
                FROM vn_gso_gdp_quarterly
                ORDER BY year DESC, quarter DESC, sector
                LIMIT 40
            """)).fetchall()

        data = [{
            "year": r[0], "quarter": r[1], "sector": r[2],
            "gdp_billion_vnd": r[3], "growth_yoy_pct": r[4],
        } for r in rows]

        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch GDP: {e}")


# ─────────────────────────────────────────────────────────────
# MACRO: TRADE (Free)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/macro/trade")
async def get_macro_trade(
    request: Request,
    months: int = Query(default=12, ge=1, le=60),
    _auth: None = Depends(authenticate_user_optional),
):
    """Vietnam monthly import/export data — free access."""
    try:
        with get_engine_crawl().connect() as conn:
            rows = conn.execute(text("""
                SELECT period, export_billion_usd, import_billion_usd,
                       trade_balance, yoy_export_pct, yoy_import_pct
                FROM vn_gso_trade_monthly
                ORDER BY period DESC
                LIMIT :months
            """), {"months": months}).fetchall()

        data = [{
            "period": r[0],
            "export_billion_usd": r[1],
            "import_billion_usd": r[2],
            "trade_balance": r[3],
            "yoy_export_pct": r[4],
            "yoy_import_pct": r[5],
        } for r in reversed(rows)]

        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trade data: {e}")


# ─────────────────────────────────────────────────────────────
# BULK DOWNLOAD ENDPOINTS (for Download tab CSV export)
# ─────────────────────────────────────────────────────────────

@router.get("/api/v1/vn30/download/profile")
async def download_vn30_profile(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 company profile — free, full table."""
    try:
        with get_engine_corp().connect() as conn:
            rows = conn.execute(text("""
                SELECT ticker, company_name, exchange, icb_sector, icb_industry,
                       market_cap_billion, listed_date
                FROM vn30_company_profile
                ORDER BY ticker ASC
            """)).fetchall()
        data = [{"ticker": r[0], "company_name": r[1], "exchange": r[2],
                 "icb_sector": r[3], "icb_industry": r[4],
                 "market_cap_billion": r[5], "listed_date": str(r[6]) if r[6] else None}
                for r in rows]
        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {e}")


@router.get("/api/v1/vn30/download/prices")
async def download_vn30_prices(
    request: Request,
    period: str = Query(default="1y", description="7d, 1m, 1y, all"),
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 OHLCV prices all tickers — premium."""
    if not _is_premium(request):
        raise HTTPException(status_code=403, detail="Premium required")
    days_map = {"7d": 7, "1m": 30, "1y": 365}
    date_filter = f"CURRENT_DATE - INTERVAL '{days_map.get(period, 365)} days'" if period != "all" else "'2000-01-01'::date"
    try:
        with get_engine_corp().connect() as conn:
            rows = conn.execute(text(f"""
                SELECT ticker, date, open, high, low, close, volume, value
                FROM vn30_ohlcv_daily
                WHERE date >= {date_filter}
                ORDER BY ticker ASC, date ASC
            """)).fetchall()
        data = [{"ticker": r[0], "date": str(r[1]), "open": r[2], "high": r[3],
                 "low": r[4], "close": r[5], "volume": r[6], "value": r[7]}
                for r in rows]
        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {e}")


@router.get("/api/v1/vn30/download/financials")
async def download_vn30_financials(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 quarterly income statement all tickers — premium."""
    if not _is_premium(request):
        raise HTTPException(status_code=403, detail="Premium required")
    try:
        with get_engine_corp().connect() as conn:
            rows = conn.execute(text("""
                SELECT ticker, year, quarter, revenue, gross_profit,
                       ebit, net_income, eps
                FROM vn30_income_stmt_quarterly
                ORDER BY ticker ASC, year DESC, quarter DESC
            """)).fetchall()
        data = [{"ticker": r[0], "year": r[1], "quarter": r[2], "revenue": r[3],
                 "gross_profit": r[4], "ebit": r[5], "net_income": r[6], "eps": r[7]}
                for r in rows]
        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {e}")


@router.get("/api/v1/vn30/download/ratios")
async def download_vn30_ratios(
    request: Request,
    period: str = Query(default="1y", description="1m, 1y, all"),
    _auth: None = Depends(authenticate_user_optional),
):
    """VN30 daily financial ratios all tickers — premium."""
    if not _is_premium(request):
        raise HTTPException(status_code=403, detail="Premium required")
    days_map = {"1m": 30, "1y": 365}
    date_filter = f"CURRENT_DATE - INTERVAL '{days_map.get(period, 365)} days'" if period != "all" else "'2000-01-01'::date"
    try:
        with get_engine_corp().connect() as conn:
            rows = conn.execute(text(f"""
                SELECT ticker, date, pe, pb, ps, roe, roa, eps,
                       dividend_yield, market_cap_billion
                FROM vn30_ratio_daily
                WHERE date >= {date_filter}
                ORDER BY ticker ASC, date ASC
            """)).fetchall()
        data = [{"ticker": r[0], "date": str(r[1]), "pe": r[2], "pb": r[3],
                 "ps": r[4], "roe": r[5], "roa": r[6], "eps": r[7],
                 "dividend_yield": r[8], "market_cap_billion": r[9]}
                for r in rows]
        return _json_response({"success": True, "count": len(data), "data": data})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {e}")
