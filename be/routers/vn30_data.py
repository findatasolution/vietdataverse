"""
Macro Data API Router
- /api/v1/macro/cpi            — Free: CPI monthly
- /api/v1/macro/gdp            — Free: GDP quarterly
- /api/v1/macro/trade          — Free: Import/export monthly

VN30 (profile/prices/financials/ratios) and VN-Index endpoints REMOVED 2026-09-10
(REV-01) — every one of them read from a `vn30_*` / `vn_macro_vnindex_daily` table
sourced via the `vnstock3` crawlers, which wraps SSI/TCBS's internal endpoints
under a license that prohibits any commercial use, direct or indirect, with no
free-tier exception (see CLAUDE.md "VN30 data source (`vnstock3`)..."). The
restriction travels with the data's chain of custody, not with which field or
endpoint serves it, so this covers company profile/sector data and VN-Index
alongside price/ratio data — not just the 5 explicitly price-derived fields.

The `crawl_vn30_*.py` crawlers keep running unchanged (internal-only, for
cross-checking BCTC-derived ROE/ROA/EPS once that pipeline is reliable — see
docs/research/2026-09-08-financial-statements-subscription-plan.md) — only this
public-facing router is gone. `vn30_company_profile`, `vn30_ohlcv_daily`,
`vn30_ratio_daily`, `vn30_income_stmt_quarterly`, `vn30_balance_sheet_quarterly`,
`vn30_cashflow_quarterly`, `vn_macro_vnindex_daily` still fill up in
`CRAWLING_CORP_DB` as before; nothing reads them anymore.

VN-Index has no clean replacement source yet (Yahoo Finance doesn't carry it;
SSI's iBoard is the same kind of broker-platform-ToS problem as vnstock3) — see
BACKLOG.md for the follow-up research item. The BCTC-derived VN30 financials
this router used to serve are being rebuilt from clean IR/disclosure-portal
sources in `listed_company_financials` (see `financial_statement_extraction`
skill) — once that's automated and covers enough tickers, a new router can read
from it instead of vn30_income_stmt_quarterly etc.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_crawl
from middleware import authenticate_user_optional

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


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
                """), {"from_yr": str(2026 - years) if years > 0 else "0000"}).fetchall()
                data = [{"period": r[0], "yoy_pct": float(r[1]), "months": r[2]}
                        for r in rows]

        return _json_response({
            "success": True, "view": view, "source": "www.nso.gov.vn",
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
    """Vietnam GDP quarterly data — free access. Source: nso.gov.vn."""
    try:
        with get_engine_crawl().connect() as conn:
            # LIMIT 200: up to 4 sector rows/quarter, so this covers ~50
            # quarters of history — the full backfilled range (2020-current)
            # plus headroom, not just the last ~10 quarters (40).
            rows = conn.execute(text("""
                SELECT year, quarter, sector, gdp_billion_vnd, growth_yoy_pct
                FROM vn_gso_gdp_quarterly
                ORDER BY year, quarter, sector
                LIMIT 200
            """)).fetchall()

        data = [{
            "year": r[0], "quarter": r[1], "sector": r[2],
            "gdp_billion_vnd": r[3], "growth_yoy_pct": r[4],
        } for r in rows]

        return _json_response({
            "success": True, "source": "www.nso.gov.vn",
            "count": len(data), "data": data,
        })
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
    """Vietnam monthly import/export data — free access. Source: nso.gov.vn."""
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

        return _json_response({
            "success": True, "source": "www.nso.gov.vn",
            "count": len(data), "data": data,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trade data: {e}")
