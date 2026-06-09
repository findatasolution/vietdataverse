"""
Webhook subscriptions — API-04.

User routes (Bearer JWT, premium_developer only):
  GET    /api/v1/webhooks           — list webhooks
  POST   /api/v1/webhooks           — register webhook
  DELETE /api/v1/webhooks/{id}      — delete webhook
  POST   /api/v1/webhooks/{id}/test — send test ping

Internal trigger (X-Internal-Secret header):
  POST   /api/v1/internal/webhooks/trigger  — fire event to all subscribers

Supported events: gold, silver, sbv_rate, termdepo, cpi, global, vn30
"""

import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, HttpUrl
from sqlalchemy import text

from core.engines import get_engine_user
from middleware import authenticate_user

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_EVENTS = frozenset(["gold", "silver", "sbv_rate", "termdepo", "cpi", "global", "vn30"])
_INTERNAL_SECRET = os.getenv("WEBHOOK_INTERNAL_SECRET", "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json(data: dict) -> Response:
    return Response(json.dumps(data, default=str), media_type="application/json")


def _require_developer(request: Request):
    user = getattr(request.state, "user", {})
    if user.get("user_level") != "premium_developer":
        raise HTTPException(status_code=403, detail="Webhook chỉ dành cho gói API Developer")


def _get_user_id(conn, auth0_id: str) -> int:
    row = conn.execute(
        text("SELECT user_id FROM users WHERE auth0_id = :aid"),
        {"aid": auth0_id}
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User không tìm thấy")
    return row[0]


def _sign(secret: str, payload: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()  # type: ignore[attr-defined]


# ── Request bodies ────────────────────────────────────────────────────────────

class WebhookCreate(BaseModel):
    url: str
    events: list[str]


# ── User endpoints ────────────────────────────────────────────────────────────

@router.get("/api/v1/webhooks")
async def list_webhooks(request: Request):
    """List all webhooks for the authenticated developer."""
    await authenticate_user(request)
    _require_developer(request)
    auth0_id = request.state.user["auth0_id"]

    with get_engine_user().connect() as conn:
        user_id = _get_user_id(conn, auth0_id)
        rows = conn.execute(text("""
            SELECT id, url, events, is_active, created_at,
                   last_triggered_at, last_status_code, failure_count
            FROM webhook_subscriptions
            WHERE user_id = :uid
            ORDER BY created_at DESC
        """), {"uid": user_id}).fetchall()

    return _json({"success": True, "data": [{
        "id":                r[0],
        "url":               r[1],
        "events":            r[2],
        "is_active":         r[3],
        "created_at":        r[4].isoformat() if r[4] else None,
        "last_triggered_at": r[5].isoformat() if r[5] else None,
        "last_status_code":  r[6],
        "failure_count":     r[7],
    } for r in rows]})


@router.post("/api/v1/webhooks")
async def create_webhook(request: Request, body: WebhookCreate):
    """Register a new webhook endpoint."""
    await authenticate_user(request)
    _require_developer(request)
    auth0_id = request.state.user["auth0_id"]

    # Validate events
    invalid = [e for e in body.events if e not in VALID_EVENTS]
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"Sự kiện không hợp lệ: {invalid}. Hợp lệ: {sorted(VALID_EVENTS)}"
        )
    if not body.events:
        raise HTTPException(status_code=422, detail="Phải chọn ít nhất 1 sự kiện")
    if not body.url.startswith("https://"):
        raise HTTPException(status_code=422, detail="URL phải dùng HTTPS")

    secret = secrets.token_hex(32)

    with get_engine_user().begin() as conn:
        user_id = _get_user_id(conn, auth0_id)

        # Limit: 5 webhooks per user
        count = conn.execute(
            text("SELECT COUNT(*) FROM webhook_subscriptions WHERE user_id = :uid"),
            {"uid": user_id}
        ).scalar()
        if count >= 5:
            raise HTTPException(status_code=429, detail="Tối đa 5 webhook mỗi tài khoản")

        try:
            row = conn.execute(text("""
                INSERT INTO webhook_subscriptions (user_id, url, events, secret)
                VALUES (:uid, :url, :events, :secret)
                RETURNING id, created_at
            """), {
                "uid":    user_id,
                "url":    body.url,
                "events": body.events,
                "secret": secret,
            }).fetchone()
        except Exception:
            raise HTTPException(status_code=409, detail="URL này đã được đăng ký")

    return _json({"success": True, "data": {
        "id":         row[0],
        "url":        body.url,
        "events":     body.events,
        "secret":     secret,  # shown only once
        "created_at": row[1].isoformat() if row[1] else None,
        "note":       "Lưu secret này ngay — sẽ không hiển thị lại.",
    }})


@router.delete("/api/v1/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, request: Request):
    """Delete a webhook by ID (must belong to the authenticated user)."""
    await authenticate_user(request)
    _require_developer(request)
    auth0_id = request.state.user["auth0_id"]

    with get_engine_user().begin() as conn:
        user_id = _get_user_id(conn, auth0_id)
        deleted = conn.execute(text("""
            DELETE FROM webhook_subscriptions
            WHERE id = :wid AND user_id = :uid
            RETURNING id
        """), {"wid": webhook_id, "uid": user_id}).fetchone()

    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook không tồn tại hoặc không thuộc tài khoản này")

    return _json({"success": True, "message": "Webhook đã xóa"})


@router.post("/api/v1/webhooks/{webhook_id}/test")
async def test_webhook(webhook_id: int, request: Request, bg: BackgroundTasks):
    """Send a test ping to a webhook URL."""
    await authenticate_user(request)
    _require_developer(request)
    auth0_id = request.state.user["auth0_id"]

    with get_engine_user().connect() as conn:
        user_id = _get_user_id(conn, auth0_id)
        row = conn.execute(text("""
            SELECT id, url, secret FROM webhook_subscriptions
            WHERE id = :wid AND user_id = :uid
        """), {"wid": webhook_id, "uid": user_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Webhook không tìm thấy")

    _, url, secret = row
    payload = {
        "event":     "ping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data":      {"message": "Test ping from Viet Dataverse"},
    }
    bg.add_task(_deliver, url, secret, "ping", payload, webhook_id)
    return _json({"success": True, "message": f"Test ping đang gửi tới {url}"})


# ── Internal trigger endpoint ─────────────────────────────────────────────────

class TriggerBody(BaseModel):
    event: str
    data: list[dict]


@router.post("/api/v1/internal/webhooks/trigger")
async def trigger_event(request: Request, body: TriggerBody, bg: BackgroundTasks):
    """Internal endpoint called by crawl scripts to fan-out data to subscribers."""
    secret_header = request.headers.get("X-Internal-Secret", "")
    if not _INTERNAL_SECRET or secret_header != _INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.event not in VALID_EVENTS:
        raise HTTPException(status_code=422, detail=f"Unknown event: {body.event}")

    with get_engine_user().connect() as conn:
        rows = conn.execute(text("""
            SELECT id, url, secret FROM webhook_subscriptions
            WHERE is_active = TRUE AND :event = ANY(events)
        """), {"event": body.event}).fetchall()

    if not rows:
        return _json({"success": True, "sent": 0})

    payload = {
        "event":     body.event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data":      body.data,
    }
    for wid, url, wh_secret in rows:
        bg.add_task(_deliver, url, wh_secret, body.event, payload, wid)

    logger.info("Webhook trigger: event=%s subscribers=%d", body.event, len(rows))
    return _json({"success": True, "sent": len(rows)})


# ── Delivery helper ───────────────────────────────────────────────────────────

async def _deliver(url: str, secret: str, event: str, payload: dict, webhook_id: int):
    """Fire-and-forget POST to webhook URL, update DB with result."""
    body_bytes = json.dumps(payload, default=str).encode()
    signature  = _sign(secret, body_bytes)
    status_code = 0
    success = False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url,
                content=body_bytes,
                headers={
                    "Content-Type":        "application/json",
                    "X-VD-Event":          event,
                    "X-VD-Signature":      signature,
                    "X-VD-Delivery-Time":  datetime.now(timezone.utc).isoformat(),
                },
            )
            status_code = resp.status_code
            success = 200 <= status_code < 300
    except Exception as exc:
        logger.warning("Webhook delivery failed: id=%d url=%s error=%s", webhook_id, url, exc)

    with get_engine_user().begin() as conn:
        if success:
            conn.execute(text("""
                UPDATE webhook_subscriptions
                SET last_triggered_at = NOW(),
                    last_status_code  = :sc,
                    failure_count     = 0
                WHERE id = :wid
            """), {"sc": status_code, "wid": webhook_id})
        else:
            conn.execute(text("""
                UPDATE webhook_subscriptions
                SET last_triggered_at = NOW(),
                    last_status_code  = :sc,
                    failure_count     = failure_count + 1,
                    is_active         = CASE WHEN failure_count + 1 >= 10 THEN FALSE ELSE is_active END
                WHERE id = :wid
            """), {"sc": status_code or 0, "wid": webhook_id})
