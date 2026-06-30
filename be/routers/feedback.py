"""Experience feedback — anonymous (no login). Auto-saved on dismiss; all fields optional."""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from core.engines import get_engine_user

router = APIRouter()

_CREATE_FEEDBACK_TABLE = """
    CREATE TABLE IF NOT EXISTS experience_feedback (
        id           SERIAL PRIMARY KEY,
        rating       SMALLINT,
        user_group   VARCHAR(32),
        looking_for  TEXT,
        improvement  TEXT,
        page_url     VARCHAR(512),
        user_agent   VARCHAR(512),
        language     VARCHAR(16),
        created_at   TIMESTAMP DEFAULT NOW()
    )
"""
# Backfill column on pre-existing tables (idempotent).
_ENSURE_USER_GROUP = "ALTER TABLE experience_feedback ADD COLUMN IF NOT EXISTS user_group VARCHAR(32)"


class FeedbackRequest(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    user_group: Optional[str] = Field(default=None, max_length=32)
    looking_for: Optional[str] = Field(default=None, max_length=2000)
    improvement: Optional[str] = Field(default=None, max_length=2000)
    page_url: Optional[str] = Field(default=None, max_length=512)
    user_agent: Optional[str] = Field(default=None, max_length=512)
    language: Optional[str] = Field(default=None, max_length=16)


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _clean(s):
    return (s.strip() or None) if isinstance(s, str) and s.strip() else None


@router.post("/api/v1/feedback")
async def submit_feedback(request: Request, data: FeedbackRequest):
    # Ignore empty submissions (auto-save may fire with nothing filled in).
    if not data.rating and not _clean(data.user_group) and not _clean(data.looking_for) and not _clean(data.improvement):
        return _json_response({"success": True, "skipped": True})
    try:
        engine_user = get_engine_user()
        with engine_user.connect() as conn:
            conn.execute(text(_CREATE_FEEDBACK_TABLE))
            try:
                conn.execute(text(_ENSURE_USER_GROUP))
            except Exception:
                pass
            conn.commit()
            conn.execute(text("""
                INSERT INTO experience_feedback
                    (rating, user_group, looking_for, improvement, page_url, user_agent, language)
                VALUES (:rating, :user_group, :looking_for, :improvement, :page_url, :ua, :lang)
            """), {
                "rating":      data.rating,
                "user_group":  _clean(data.user_group),
                "looking_for": _clean(data.looking_for),
                "improvement": _clean(data.improvement),
                "page_url":    (data.page_url[:512] if data.page_url else None),
                "ua":          (data.user_agent[:512] if data.user_agent else None),
                "lang":        data.language,
            })
            conn.commit()
        return _json_response({"success": True})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {e}")
