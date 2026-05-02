import json
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from core.engines import get_engine_user

router = APIRouter()

_CREATE_INTEREST_TABLE = """
    CREATE TABLE IF NOT EXISTS user_interest (
        id            SERIAL PRIMARY KEY,
        fingerprint   VARCHAR(64)  NOT NULL,
        interest_type VARCHAR(64)  NOT NULL,
        source        VARCHAR(32),
        user_agent    VARCHAR(512),
        language      VARCHAR(16),
        created_at    TIMESTAMP DEFAULT NOW()
    )
"""


class InterestRequest(BaseModel):
    fingerprint: str = Field(..., min_length=8, max_length=64)
    source: str = Field(default="web", max_length=32)
    timestamp: Optional[str] = None
    user_agent: Optional[str] = Field(default=None, max_length=512)
    language: Optional[str] = Field(default=None, max_length=16)


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


@router.post("/api/v1/interest/{interest_type}")
async def save_user_interest(request: Request, interest_type: str, data: InterestRequest):
    if not re.match(r"^[a-zA-Z0-9-]+$", interest_type) or len(interest_type) > 64:
        raise HTTPException(status_code=400, detail="Invalid interest_type")

    try:
        engine_user = get_engine_user()
        with engine_user.connect() as conn:
            conn.execute(text(_CREATE_INTEREST_TABLE))
            conn.commit()

            existing = conn.execute(text("""
                SELECT id FROM user_interest
                WHERE fingerprint = :fp AND interest_type = :itype
            """), {"fp": data.fingerprint, "itype": interest_type}).fetchone()

            if existing:
                response_data = {
                    "success": True, "message": "Interest already recorded",
                    "interest_type": interest_type, "duplicate": True,
                }
            else:
                conn.execute(text("""
                    INSERT INTO user_interest (fingerprint, interest_type, source, user_agent, language)
                    VALUES (:fp, :itype, :source, :ua, :lang)
                """), {
                    "fp":     data.fingerprint,
                    "itype":  interest_type,
                    "source": data.source,
                    "ua":     data.user_agent[:512] if data.user_agent else None,
                    "lang":   data.language,
                })
                conn.commit()
                response_data = {
                    "success": True, "message": "Interest saved successfully",
                    "interest_type": interest_type, "duplicate": False,
                }

        return _json_response(response_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save interest: {e}")


@router.get("/api/v1/interest/stats")
async def get_interest_stats(request: Request):
    try:
        with get_engine_user().connect() as conn:
            rows = conn.execute(text("""
                SELECT interest_type, COUNT(DISTINCT fingerprint) AS unique_users, COUNT(*) AS total
                FROM user_interest
                GROUP BY interest_type
                ORDER BY unique_users DESC
            """)).fetchall()

        stats = {r[0]: {"unique_users": r[1], "total_records": r[2]} for r in rows}
        return _json_response({"success": True, "data": stats})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.get("/api/v1/interest/details")
async def get_interest_details(
    request: Request,
    interest_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    try:
        with get_engine_user().connect() as conn:
            if interest_type:
                rows = conn.execute(text("""
                    SELECT id, fingerprint, interest_type, source, user_agent, language, created_at
                    FROM user_interest WHERE interest_type = :itype
                    ORDER BY created_at DESC LIMIT :limit OFFSET :offset
                """), {"itype": interest_type, "limit": limit, "offset": offset}).fetchall()
                total = conn.execute(text(
                    "SELECT COUNT(*) FROM user_interest WHERE interest_type = :itype"
                ), {"itype": interest_type}).fetchone()[0]
            else:
                rows = conn.execute(text("""
                    SELECT id, fingerprint, interest_type, source, user_agent, language, created_at
                    FROM user_interest
                    ORDER BY created_at DESC LIMIT :limit OFFSET :offset
                """), {"limit": limit, "offset": offset}).fetchall()
                total = conn.execute(text("SELECT COUNT(*) FROM user_interest")).fetchone()[0]

        records = [{
            "id":            r[0],
            "fingerprint":   r[1][:8] + "..." if r[1] else None,
            "interest_type": r[2],
            "source":        r[3],
            "user_agent":    r[4][:100] + "..." if r[4] and len(r[4]) > 100 else r[4],
            "language":      r[5],
            "created_at":    r[6].isoformat() if r[6] else None,
        } for r in rows]

        return _json_response({
            "success": True, "data": records,
            "total": total, "limit": limit, "offset": offset,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get details: {e}")
