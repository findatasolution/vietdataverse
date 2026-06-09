"""
Wallet router — credit balance, transaction history, and PayOS top-up.

Endpoints (all require auth):
  GET  /api/v1/wallet/balance
  GET  /api/v1/wallet/transactions?limit=50&offset=0
  POST /api/v1/wallet/topup   body: {"amount_vnd": int}

Response format follows platform standard:
  {"success": true, "source": "wallet", "count": N, "data": ...}
"""

import hashlib
import hmac as _hmac
import json
import logging
import os
import time

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_user, get_engine_knowledge
from middleware import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])

PAYOS_CLIENT_ID    = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY      = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
PAYOS_BASE_URL     = "https://api-merchant.payos.vn"
FRONTEND_URL       = os.getenv("FRONTEND_URL", "https://vietdataverse.online")

MIN_TOPUP_VND = 50_000
VND_PER_CREDIT = 1_000


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(
        content=raw,
        media_type="application/json",
        headers={"Content-Length": str(len(raw))},
    )


def _require_auth(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _resolve_user_id(auth0_id: str) -> int:
    """Look up internal user_id from auth0_id. Raises 404 if not found."""
    with get_engine_user().connect() as conn:
        row = conn.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row[0]


def _payos_checksum(amount: int, cancel_url: str, description: str,
                    order_code: int, return_url: str) -> str:
    raw = (
        f"amount={amount}"
        f"&cancelUrl={cancel_url}"
        f"&description={description}"
        f"&orderCode={order_code}"
        f"&returnUrl={return_url}"
    )
    return _hmac.new(
        PAYOS_CHECKSUM_KEY.encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ── Schemas ───────────────────────────────────────────────────────────────────

class TopupRequest(BaseModel):
    amount_vnd: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/balance")
async def get_balance(request: Request):
    """Return current credit balance for the authenticated user."""
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id = _resolve_user_id(auth0_id)

    from services.credit import get_balance as _get_balance
    balance = _get_balance(user_id)

    return _json_response({
        "success": True,
        "source":  "wallet",
        "count":   1,
        "data":    {"balance": balance},
    })


@router.get("/transactions")
async def list_transactions(
    request: Request,
    limit:  int = 50,
    offset: int = 0,
):
    """
    Return paginated credit_ledger rows for the authenticated user.
    Ordered newest first.
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id = _resolve_user_id(auth0_id)

    if limit < 1:
        limit = 1
    if limit > 200:
        limit = 200
    if offset < 0:
        offset = 0

    try:
        with get_engine_knowledge().connect() as conn:
            rows = conn.execute(text("""
                SELECT id, amount, kind, ref_type, ref_id, idem_key, note, created_at
                FROM credit_ledger
                WHERE user_id = :uid
                ORDER BY created_at DESC
                LIMIT :lim OFFSET :off
            """), {"uid": user_id, "lim": limit, "off": offset}).fetchall()

            total = conn.execute(text("""
                SELECT COUNT(*) FROM credit_ledger WHERE user_id = :uid
            """), {"uid": user_id}).scalar()

        data = [{
            "id":         r[0],
            "amount":     r[1],
            "kind":       r[2],
            "ref_type":   r[3],
            "ref_id":     r[4],
            "idem_key":   r[5],
            "note":       r[6],
            "created_at": r[7].isoformat() if r[7] else None,
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "wallet",
            "count":   total,
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("wallet/transactions error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/topup")
async def topup_wallet(body: TopupRequest, request: Request):
    """
    Create a PayOS payment link to top up credits.

    amount_vnd must be >= 50,000.
    Credits added = amount_vnd // 1000.

    Returns: {"checkout_url", "qr_code", "order_code"}
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")

    if body.amount_vnd < MIN_TOPUP_VND:
        raise HTTPException(
            status_code=400,
            detail=f"amount_vnd must be >= {MIN_TOPUP_VND:,} VND",
        )

    user_id = _resolve_user_id(auth0_id)
    credits = body.amount_vnd // VND_PER_CREDIT

    # Create payment_orders row in USER_DB
    order_code = user_id * 1_000_000 + (int(time.time()) % 1_000_000)

    try:
        with get_engine_user().begin() as conn:
            # Ensure order_type and credit_amount columns exist (idempotent DDL)
            try:
                conn.execute(text(
                    "ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS order_type VARCHAR(30) NOT NULL DEFAULT 'subscription'"
                ))
            except Exception:
                pass
            try:
                conn.execute(text(
                    "ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS credit_amount INT"
                ))
            except Exception:
                pass

            conn.execute(text("""
                INSERT INTO payment_orders
                    (order_code, user_id, plan, amount, gateway, order_type, credit_amount)
                VALUES
                    (:oc, :uid, 'credit_topup', :amount, 'payos', 'credit_topup', :credits)
            """), {
                "oc":      order_code,
                "uid":     user_id,
                "amount":  body.amount_vnd,
                "credits": credits,
            })
    except Exception as exc:
        logger.exception("topup: payment_orders insert failed user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=f"Order creation failed: {exc}")

    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY]):
        raise HTTPException(status_code=500, detail="PayOS env vars not configured")

    return_url  = f"{FRONTEND_URL}?payment=success&order={order_code}&type=topup"
    cancel_url  = f"{FRONTEND_URL}?payment=cancelled"
    description = f"Nap {credits} credits"[:25]

    payload = {
        "orderCode":   order_code,
        "amount":      body.amount_vnd,
        "description": description,
        "returnUrl":   return_url,
        "cancelUrl":   cancel_url,
        "signature":   _payos_checksum(
            body.amount_vnd, cancel_url, description, order_code, return_url
        ),
    }
    headers = {
        "x-client-id":  PAYOS_CLIENT_ID,
        "x-api-key":    PAYOS_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp      = requests.post(
            f"{PAYOS_BASE_URL}/v2/payment-requests",
            json=payload, headers=headers, timeout=15,
        )
        resp_data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot connect to PayOS: {exc}")

    if resp_data.get("code") != "00":
        raise HTTPException(
            status_code=502,
            detail=f"PayOS error: {resp_data.get('desc', 'Unknown')}",
        )

    data      = resp_data["data"]
    payos_ref = data.get("paymentLinkId", "")

    # Store payos_ref for reconciliation
    try:
        with get_engine_user().begin() as conn:
            conn.execute(text(
                "UPDATE payment_orders SET payos_ref = :ref WHERE order_code = :oc"
            ), {"ref": payos_ref, "oc": order_code})
    except Exception:
        pass  # non-fatal

    return _json_response({
        "success": True,
        "source":  "wallet",
        "count":   1,
        "data": {
            "checkout_url": data["checkoutUrl"],
            "qr_code":      data.get("qrCode", ""),
            "order_code":   order_code,
            "credits":      credits,
            "amount_vnd":   body.amount_vnd,
        },
    })
