"""
Subscription router — platform product catalog, subscribe/cancel, billing history.

Endpoints:
  GET  /api/v1/subscriptions/plans      (public)
  GET  /api/v1/subscriptions/me         (auth)
  POST /api/v1/subscriptions/subscribe  (auth) body: {"product_code": str}
  POST /api/v1/subscriptions/cancel     (auth) body: {"product_code": str}
  GET  /api/v1/subscriptions/history?limit&offset (auth)
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_user, get_engine_knowledge
from middleware import authenticate_user
from services.credit import InsufficientCredits
from services.subscription import (
    subscribe as _subscribe,
    cancel_subscription as _cancel_subscription,
    get_subscription,
    list_subscription_history,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _require_auth(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _resolve_user_id(auth0_id: str) -> int:
    with get_engine_user().connect() as conn:
        row = conn.execute(text(
            "SELECT user_id FROM users WHERE auth0_id = :aid"
        ), {"aid": auth0_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row[0]


class ProductCodeBody(BaseModel):
    product_code: str


@router.get("/plans")
async def list_plans():
    with get_engine_knowledge().connect() as conn:
        rows = conn.execute(text("""
            SELECT code, name, price_credits, list_price_credits, billing_period_days
            FROM platform_products WHERE active = true
        """)).fetchall()
    data = [{
        "code": r[0], "name": r[1], "price_credits": r[2],
        "list_price_credits": r[3], "billing_period_days": r[4],
    } for r in rows]
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})


@router.get("/me")
async def my_subscriptions(request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    with get_engine_knowledge().connect() as conn:
        codes = [r[0] for r in conn.execute(text(
            "SELECT code FROM platform_products WHERE active = true"
        )).fetchall()]
    data = [s for s in (get_subscription(user_id, c) for c in codes) if s]
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})


@router.post("/subscribe")
async def do_subscribe(body: ProductCodeBody, request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    try:
        result = _subscribe(user_id, body.product_code)
    except InsufficientCredits as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _json_response({"success": True, "source": "subscriptions", "count": 1, "data": result})


@router.post("/cancel")
async def do_cancel(body: ProductCodeBody, request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    try:
        result = _cancel_subscription(user_id, body.product_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return _json_response({"success": True, "source": "subscriptions", "count": 1, "data": result})


@router.get("/history")
async def history(request: Request, limit: int = 50, offset: int = 0):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    data = list_subscription_history(user_id, limit=limit, offset=offset)
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})
