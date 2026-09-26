"""
Subscription router — platform product catalog, subscribe/cancel, billing history.

Endpoints:
  GET  /api/v1/subscriptions/plans      (public)
  GET  /api/v1/subscriptions/me         (auth)
  POST /api/v1/subscriptions/subscribe  (auth) body: {"product_code": str}
  POST /api/v1/subscriptions/cancel     (auth) body: {"product_code": str}
  GET  /api/v1/subscriptions/history?limit&offset (auth)
  GET  /api/v1/subscriptions/trial-eligibility?product_code= (auth)
  POST /api/v1/subscriptions/trial      (auth) body: {"product_code", "consented", "consent_text"}

Cancellation takes effect at the end of the paid period, so both /me and
/cancel carry `cancel_at_period_end` + `current_period_end` — the FE needs
them together to say "still usable until <date>". /me gets them from
get_subscription(); /cancel from cancel_subscription()'s return value. POST
/subscribe doubles as the undo ("keep my subscription") action: it returns
`charged: false` when it only cleared a scheduled cancellation.
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_user, get_engine_knowledge
from middleware import authenticate_user
from services.credit import InsufficientCredits, VND_PER_CREDIT, get_wallet_state
from services.subscription import (
    subscribe as _subscribe,
    cancel_subscription as _cancel_subscription,
    get_subscription,
    list_subscription_history,
    start_trial as _start_trial,
    ConsentRequired,
    TrialAlreadyUsed,
    TRIAL_DAYS,
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


class TrialBody(BaseModel):
    product_code: str
    consented: bool = False
    consent_text: str = ""


def _trial_offer(conn, user_id: int, product_code: str) -> dict:
    """Everything the UI needs to render the trial box, in VND.

    Credits are an internal unit; the customer is told money. The shortfall is
    computed here rather than in JS so the number the user reads and the number
    the server enforces cannot drift.
    """
    row = conn.execute(text("""
        SELECT price_credits, billing_period_days, active
        FROM platform_products WHERE code = :c
    """), {"c": product_code}).first()
    if not row or not row[2]:
        raise HTTPException(status_code=404, detail="Gói không tồn tại hoặc chưa mở bán")
    price_credits, period_days = int(row[0]), int(row[1])
    wallet = get_wallet_state(user_id)
    required_vnd = price_credits * VND_PER_CREDIT
    available_vnd = wallet["available"] * VND_PER_CREDIT
    shortfall_vnd = max(0, required_vnd - available_vnd)
    return {
        "product_code": product_code,
        "trial_days": TRIAL_DAYS,
        "required_credits": price_credits,
        "required_vnd": required_vnd,
        "available_vnd": available_vnd,
        "shortfall_vnd": shortfall_vnd,
        "billing_period_days": period_days,
        "wallet": wallet,
    }


@router.get("/trial-eligibility")
async def trial_eligibility(request: Request, product_code: str):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    with get_engine_knowledge().connect() as conn:
        offer = _trial_offer(conn, user_id, product_code)
        used = conn.execute(text("""
            SELECT 1 FROM trial_consents
            WHERE user_id = :u AND product_code = :p AND consented LIMIT 1
        """), {"u": user_id, "p": product_code}).first()
        live = conn.execute(text("""
            SELECT status FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p
        """), {"u": user_id, "p": product_code}).first()

    if used:
        offer.update(eligible=False, reason="already_used")
    elif live and live[0] in ("trialing", "active"):
        offer.update(eligible=False, reason="already_subscribed")
    elif offer["shortfall_vnd"] > 0:
        offer.update(eligible=False, reason="insufficient_balance")
    else:
        offer.update(eligible=True, reason=None)

    return _json_response({"success": True, "source": "subscriptions",
                           "count": 1, "data": offer})


@router.post("/trial")
async def do_start_trial(body: TrialBody, request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    try:
        result = _start_trial(
            user_id, body.product_code,
            consented=body.consented,
            consent_text=body.consent_text,
            user_agent=request.headers.get("User-Agent"),
        )
    except ConsentRequired as e:
        raise HTTPException(status_code=400, detail=str(e))
    except TrialAlreadyUsed as e:
        raise HTTPException(status_code=409, detail=str(e))
    except InsufficientCredits:
        # 402 carries the gap in VND, because "insufficient credits" is not
        # something a customer can act on — "nạp thêm 25.000đ" is.
        with get_engine_knowledge().connect() as conn:
            offer = _trial_offer(conn, user_id, body.product_code)
        raise HTTPException(status_code=402, detail={
            "message": (f"Ví cần tối thiểu {offer['required_vnd']:,}đ để bắt đầu dùng thử. "
                        f"Hiện có {offer['available_vnd']:,}đ khả dụng."
                        .replace(",", ".")),
            **offer,
        })

    return _json_response({"success": True, "source": "subscriptions",
                           "count": 1, "data": result})


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
