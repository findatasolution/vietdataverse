import json
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_finstock, get_engine_user
from middleware import authenticate_user_optional

router = APIRouter()

FREE_LIMIT = 3
PREMIUM_LEVELS = ("premium", "premium_developer", "admin")


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _signal(score: float) -> str:
    if score >= 60:
        return "MUA"
    if score >= 40:
        return "TRUNG TÍNH"
    return "BÁN"


def _get_latest_quarter(conn):
    """Return (year, quarter) of the most recent prediction batch."""
    row = conn.execute(text("""
        SELECT year, quarter
        FROM weekly_predictions
        ORDER BY year DESC, quarter DESC
        LIMIT 1
    """)).fetchone()
    return (row[0], row[1]) if row else (None, None)


@router.get("/api/v1/vn30-scores/meta")
async def get_vn30_scores_meta():
    """Public metadata — no auth required."""
    try:
        with get_engine_finstock().connect() as conn:
            row = conn.execute(text("""
                SELECT year, quarter, MAX(report_date) as latest_date,
                       COUNT(DISTINCT ticker) as total_tickers,
                       MAX(model_version) as model_version
                FROM weekly_predictions
                GROUP BY year, quarter
                ORDER BY year DESC, quarter DESC
                LIMIT 1
            """)).fetchone()

        if not row or row[0] is None:
            return _json_response({"success": True, "data": None,
                                   "message": "Chưa có dữ liệu"})

        return _json_response({
            "success": True,
            "data": {
                "year": row[0],
                "quarter": row[1],
                "latest_report_date": str(row[2]) if row[2] else None,
                "total_tickers": row[3],
                "model_version": row[4],
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch VN30 meta: {e}")


@router.get("/api/v1/vn30-scores")
async def get_vn30_scores(
    request: Request,
    _auth: None = Depends(authenticate_user_optional),
):
    """
    VN30 leaderboard — ranked by gain probability.
    Free/anonymous: top 3 rows, is_gated=True.
    Premium: all 30 rows, is_gated=False.
    """
    # Determine premium status from request.state (set by authenticate_user_optional)
    user = getattr(request.state, "user", None)
    user_level = (user or {}).get("user_level", "free")
    is_premium = user_level in PREMIUM_LEVELS
    effective_limit = 30 if is_premium else FREE_LIMIT

    try:
        with get_engine_finstock().connect() as conn:
            year, quarter = _get_latest_quarter(conn)
            if year is None:
                return _json_response({
                    "success": True,
                    "is_gated": not is_premium,
                    "year": None,
                    "quarter": None,
                    "updated_at": None,
                    "data": [],
                    "count": 0,
                    "free_limit": FREE_LIMIT,
                })

            rows = conn.execute(text("""
                SELECT ticker, report_date, year, quarter,
                       prediction_proba, model_version, created_at
                FROM weekly_predictions
                WHERE year = :year AND quarter = :quarter
                ORDER BY prediction_proba DESC
                LIMIT :limit
            """), {"year": year, "quarter": quarter, "limit": effective_limit}).fetchall()

            # Latest updated_at
            updated_at_row = conn.execute(text("""
                SELECT MAX(created_at) FROM weekly_predictions
                WHERE year = :year AND quarter = :quarter
            """), {"year": year, "quarter": quarter}).fetchone()
            updated_at = updated_at_row[0].isoformat() if updated_at_row and updated_at_row[0] else None

        data = []
        for i, r in enumerate(rows):
            score = round(float(r[4]) * 100, 1)
            data.append({
                "rank": i + 1,
                "ticker": str(r[0]),
                "score": score,
                "signal": _signal(score),
                "report_date": str(r[1]) if r[1] else None,
                "model_version": str(r[5]) if r[5] else None,
            })

        return _json_response({
            "success": True,
            "is_gated": not is_premium,
            "year": year,
            "quarter": quarter,
            "updated_at": updated_at,
            "data": data,
            "count": len(data),
            "free_limit": FREE_LIMIT,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch VN30 scores: {e}")


@router.get("/api/v1/vn30-scores/ticker/{ticker}")
async def get_vn30_ticker_history(
    ticker: str,
    request: Request,
    limit: int = 8,
    _auth: None = Depends(authenticate_user_optional),
):
    """Historical weekly scores for a single ticker — premium only."""
    user = getattr(request.state, "user", None)
    user_level = (user or {}).get("user_level", "free")
    if user_level not in PREMIUM_LEVELS:
        raise HTTPException(
            status_code=403,
            detail="Chỉ tài khoản Premium mới xem được lịch sử điểm số. Vui lòng nâng cấp."
        )

    try:
        with get_engine_finstock().connect() as conn:
            rows = conn.execute(text("""
                SELECT report_date, year, quarter, prediction_proba, model_version
                FROM weekly_predictions
                WHERE ticker = :ticker
                ORDER BY report_date DESC
                LIMIT :limit
            """), {"ticker": ticker.upper(), "limit": max(1, min(limit, 52))}).fetchall()

        if not rows:
            return _json_response({
                "success": True,
                "ticker": ticker.upper(),
                "data": [],
                "count": 0,
            })

        data = []
        for r in rows:
            score = round(float(r[3]) * 100, 1)
            data.append({
                "report_date": str(r[0]) if r[0] else None,
                "year": r[1],
                "quarter": r[2],
                "score": score,
                "signal": _signal(score),
                "model_version": str(r[4]) if r[4] else None,
            })

        return _json_response({
            "success": True,
            "ticker": ticker.upper(),
            "data": data,
            "count": len(data),
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ticker history: {e}")
