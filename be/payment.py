"""
Payment module: PayOS subscription webhook handling.

Luồng PayOS:
  1. Frontend gọi POST /api/v1/payment/create-order (kèm Bearer token) hoặc
     POST /api/v1/payment/create-order-guest (không cần token, chỉ cần email)
  2. Backend tạo payment link PayOS → trả về { checkout_url, qr_code }
  3. User thanh toán qua VietQR / banking app
  4. PayOS gọi webhook POST /api/v1/payment/payos-webhook
  5. Backend xác minh chữ ký → cập nhật is_premium + premium_expiry + user_level='premium'

Env vars cần thiết:
  PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY
  FRONTEND_URL  (return/cancel URL sau thanh toán)
  USER_DB       (Neon DB connection string)
"""

import hashlib
import hmac as _hmac
import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from middleware import authenticate_user
from core.engines import get_engine_user

router = APIRouter(prefix="/api/v1/payment", tags=["payment"])

# ============================================================
# Config
# ============================================================
PAYOS_CLIENT_ID    = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY      = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
PAYOS_BASE_URL     = "https://api-merchant.payos.vn"

FRONTEND_URL       = os.getenv("FRONTEND_URL", "https://vietdataverse.online")

SUBSCRIPTION_PLANS = {
    "premium_monthly": {"amount": 99_000,    "days": 30,  "level": "premium",           "name": "Premium 1 Thang"},
    "premium_yearly":  {"amount": 990_000,   "days": 360, "level": "premium",           "name": "Premium 1 Nam"},
    "dev_monthly":     {"amount": 375_000,   "days": 30,  "level": "premium_developer", "name": "Dev Premium 1 Thang"},
    "dev_yearly":      {"amount": 4_500_000, "days": 360, "level": "premium_developer", "name": "Dev Premium 1 Nam"},
}

# ============================================================
# DB helpers
# ============================================================

def _get_engine():
    return get_engine_user()


def _session():
    Session = sessionmaker(bind=_get_engine())
    return Session()


# ============================================================
# PayOS crypto helpers
# ============================================================

def _payos_checksum(amount: int, cancel_url: str, description: str,
                    order_code: int, return_url: str) -> str:
    """HMAC-SHA256 checksum for PayOS payment-request creation."""
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


def _verify_payos_webhook(body: dict) -> bool:
    """
    Verify PayOS webhook signature.
    PayOS sends { code, desc, success, data: { ..., signature } }
    Signature = HMAC-SHA256 of sorted key=value pairs from data (excluding 'signature').
    """
    data = body.get("data", {})
    received_sig = data.pop("signature", "")

    sorted_pairs = "&".join(
        f"{k}={v}"
        for k, v in sorted(data.items())
        if v is not None
    )
    expected = _hmac.new(
        PAYOS_CHECKSUM_KEY.encode("utf-8"),
        sorted_pairs.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Restore signature so caller still has full body
    data["signature"] = received_sig
    return _hmac.compare_digest(expected.lower(), received_sig.lower())


# ============================================================
# DB helpers: ensure schema, update user
# ============================================================

def _ensure_tables(conn):
    """Idempotent DDL: create payment_orders + add premium columns to users."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS payment_orders (
            order_code  BIGINT       PRIMARY KEY,
            user_id     INT          NOT NULL,
            plan        VARCHAR(50)  NOT NULL,
            amount      INT          NOT NULL,
            status      VARCHAR(20)  NOT NULL DEFAULT 'pending',
            gateway     VARCHAR(20)  NOT NULL DEFAULT 'payos',
            payos_ref   VARCHAR(100),
            created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP             DEFAULT NOW()
        )
    """))
    try:
        conn.execute(text(
            "ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS payos_ref VARCHAR(100)"
        ))
    except Exception:
        pass
    for col, defn in [
        ("is_premium",          "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("premium_expiry",      "TIMESTAMP"),
        ("api_request_count",   "INT NOT NULL DEFAULT 0"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}"
            ))
        except Exception:
            pass

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id       SERIAL PRIMARY KEY,
            user_id      INT         NOT NULL,
            key_value    VARCHAR(64) UNIQUE NOT NULL,
            created_at   TIMESTAMP   NOT NULL DEFAULT NOW(),
            last_used_at TIMESTAMP,
            is_active    BOOLEAN     NOT NULL DEFAULT TRUE
        )
    """))
    conn.commit()


def _activate_premium(session, user_id: int, plan: str):
    """Extend premium_expiry for a user. Stacks on top of existing subscription.

    Side effects:
      - Set users.current_plan = plan (cho quota lookup trong middleware).
      - Reactivate mọi api_keys của user (để renew không bắt gen key mới).
    """
    plan_info = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["premium_monthly"])
    new_level  = plan_info["level"]  # "premium" | "premium_developer"

    row = session.execute(
        text("SELECT premium_expiry FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()

    now = datetime.now()
    base = max(row[0], now) if row and row[0] and row[0] > now else now
    new_expiry = base + timedelta(days=plan_info["days"])

    session.execute(text("""
        UPDATE users
        SET is_premium = TRUE, premium_expiry = :expiry,
            user_level = :lvl, current_plan = :plan, updated_at = NOW()
        WHERE user_id = :uid
    """), {"expiry": new_expiry, "lvl": new_level, "plan": plan, "uid": user_id})

    # Reactivate API keys đã bị middleware deactivate khi hết hạn.
    # Chỉ reactivate cho dev plans; premium plain không có API access nên bỏ qua.
    if new_level == "premium_developer":
        session.execute(text("""
            UPDATE api_keys SET is_active = TRUE
            WHERE user_id = :uid AND is_active = FALSE
        """), {"uid": user_id})

    return new_expiry


# ============================================================
# PayOS query helper
# ============================================================

def _query_payos_order(order_code: int) -> dict:
    """Call PayOS GET /v2/payment-requests/{orderCode} and return data dict."""
    headers = {
        "x-client-id": PAYOS_CLIENT_ID,
        "x-api-key":   PAYOS_API_KEY,
    }
    resp = requests.get(
        f"{PAYOS_BASE_URL}/v2/payment-requests/{order_code}",
        headers=headers,
        timeout=15,
    )
    return resp.json()


# ============================================================
# Schemas
# ============================================================

class CreateOrderRequest(BaseModel):
    plan: str  # "monthly" | "yearly"


class GuestOrderRequest(BaseModel):
    email: str
    plan: str  # "monthly" | "yearly"


# ============================================================
# Endpoints
# ============================================================

@router.post("/create-order")
async def create_payment_order(body: CreateOrderRequest, request: Request):
    """
    Tạo PayOS payment link cho subscription.
    Yêu cầu Bearer token (Auth0).
    """
    await authenticate_user(request)
    user      = request.state.user
    auth0_id  = user.get("auth0_id")

    if body.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plan không hợp lệ. Chọn: {list(SUBSCRIPTION_PLANS.keys())}",
        )

    plan_info = SUBSCRIPTION_PLANS[body.plan]

    # Lấy hoặc tạo user_id từ DB
    session = _session()
    try:
        with _get_engine().connect() as conn:
            _ensure_tables(conn)

        row = session.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()

        if not row:
            # Auto-create user từ token nếu chưa có trong DB
            email = user.get("email", "")
            # Thử link với anonymous account cùng email
            existing = session.execute(
                text("SELECT user_id FROM users WHERE email = :email"),
                {"email": email},
            ).fetchone()
            if existing:
                session.execute(text("""
                    UPDATE users SET auth0_id = :aid, registration_type = 'google', updated_at = NOW()
                    WHERE email = :email
                """), {"aid": auth0_id, "email": email})
                session.commit()
                user_db_id = existing[0]
            else:
                result = session.execute(text("""
                    INSERT INTO users (auth0_id, email, name, picture, email_verified, user_level, registration_type)
                    VALUES (:aid, :email, :name, :picture, :ev, 'free', 'google')
                    RETURNING user_id
                """), {
                    "aid":     auth0_id,
                    "email":   email,
                    "name":    user.get("name"),
                    "picture": user.get("picture"),
                    "ev":      user.get("email_verified", False),
                })
                session.commit()
                user_db_id = result.fetchone()[0]
        else:
            user_db_id = row[0]
    finally:
        session.close()

    # Tạo order_code duy nhất: user_id * 1_000_000 + epoch_mod
    order_code = user_db_id * 1_000_000 + (int(time.time()) % 1_000_000)

    # Lưu payment_orders
    session = _session()
    try:
        session.execute(text("""
            INSERT INTO payment_orders (order_code, user_id, plan, amount, gateway)
            VALUES (:oc, :uid, :plan, :amount, 'payos')
        """), {
            "oc":     order_code,
            "uid":    user_db_id,
            "plan":   body.plan,
            "amount": plan_info["amount"],
        })
        session.commit()
    finally:
        session.close()

    # Tạo PayOS payment link
    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY]):
        raise HTTPException(status_code=500, detail="PAYOS_* env vars chưa được cấu hình")

    return_url = f"{FRONTEND_URL}?payment=success&order={order_code}"
    cancel_url = f"{FRONTEND_URL}?payment=cancelled"
    description = plan_info["name"][:25]  # max 25 chars (nội dung chuyển khoản)

    payload = {
        "orderCode":   order_code,
        "amount":      plan_info["amount"],
        "description": description,
        "returnUrl":   return_url,
        "cancelUrl":   cancel_url,
        "signature":   _payos_checksum(
            plan_info["amount"], cancel_url, description, order_code, return_url
        ),
    }

    headers = {
        "x-client-id": PAYOS_CLIENT_ID,
        "x-api-key":   PAYOS_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{PAYOS_BASE_URL}/v2/payment-requests",
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp_data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối PayOS: {e}")

    if resp_data.get("code") != "00":
        raise HTTPException(
            status_code=502,
            detail=f"PayOS lỗi: {resp_data.get('desc', 'Unknown')}",
        )

    data      = resp_data["data"]
    payos_ref = data.get("paymentLinkId", "")

    session = _session()
    try:
        session.execute(
            text("UPDATE payment_orders SET payos_ref = :ref WHERE order_code = :oc"),
            {"ref": payos_ref, "oc": order_code},
        )
        session.commit()
    finally:
        session.close()

    return {
        "order_code":   order_code,
        "plan":         body.plan,
        "amount":       plan_info["amount"],
        "checkout_url": data["checkoutUrl"],
        "qr_code":      data.get("qrCode", ""),
    }


@router.post("/create-order-guest")
async def create_payment_order_guest(body: GuestOrderRequest):
    """
    Tạo PayOS payment link cho user chưa đăng nhập (guest checkout).
    Chỉ cần email + plan — không cần Bearer token.
    Hệ thống tự upsert anonymous user bằng email.
    """
    if body.plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Plan không hợp lệ. Chọn: {list(SUBSCRIPTION_PLANS.keys())}",
        )

    email     = body.email.strip().lower()
    plan_info = SUBSCRIPTION_PLANS[body.plan]

    with _get_engine().connect() as conn:
        _ensure_tables(conn)

    session = _session()
    try:
        # Upsert anonymous user by email
        existing = session.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email},
        ).fetchone()

        if existing:
            user_db_id = existing[0]
        else:
            result = session.execute(text("""
                INSERT INTO users (email, user_level, registration_type, email_verified)
                VALUES (:email, 'free', 'anonymous', FALSE)
                RETURNING user_id
            """), {"email": email})
            session.commit()
            user_db_id = result.fetchone()[0]
    finally:
        session.close()

    order_code = user_db_id * 1_000_000 + (int(time.time()) % 1_000_000)

    session = _session()
    try:
        session.execute(text("""
            INSERT INTO payment_orders (order_code, user_id, plan, amount, gateway)
            VALUES (:oc, :uid, :plan, :amount, 'payos')
        """), {
            "oc":     order_code,
            "uid":    user_db_id,
            "plan":   body.plan,
            "amount": plan_info["amount"],
        })
        session.commit()
    finally:
        session.close()

    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY]):
        raise HTTPException(status_code=500, detail="PAYOS_* env vars chưa được cấu hình")

    return_url  = f"{FRONTEND_URL}?payment=success&order={order_code}&email={email}"
    cancel_url  = f"{FRONTEND_URL}?payment=cancelled"
    description = plan_info["name"][:25]

    payload = {
        "orderCode":   order_code,
        "amount":      plan_info["amount"],
        "description": description,
        "returnUrl":   return_url,
        "cancelUrl":   cancel_url,
        "signature":   _payos_checksum(
            plan_info["amount"], cancel_url, description, order_code, return_url
        ),
    }
    headers = {
        "x-client-id":  PAYOS_CLIENT_ID,
        "x-api-key":    PAYOS_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp      = requests.post(f"{PAYOS_BASE_URL}/v2/payment-requests",
                                  json=payload, headers=headers, timeout=15)
        resp_data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối PayOS: {e}")

    if resp_data.get("code") != "00":
        raise HTTPException(
            status_code=502,
            detail=f"PayOS lỗi: {resp_data.get('desc', 'Unknown')}",
        )

    data      = resp_data["data"]
    payos_ref = data.get("paymentLinkId", "")

    session = _session()
    try:
        session.execute(
            text("UPDATE payment_orders SET payos_ref = :ref WHERE order_code = :oc"),
            {"ref": payos_ref, "oc": order_code},
        )
        session.commit()
    finally:
        session.close()

    return {
        "order_code":   order_code,
        "plan":         body.plan,
        "amount":       plan_info["amount"],
        "checkout_url": data["checkoutUrl"],
        "qr_code":      data.get("qrCode", ""),
        "note":         "Thanh toán xong, đăng nhập bằng email này để kích hoạt Premium.",
    }


@router.post("/verify-order/{order_code}")
async def verify_order(order_code: int):
    """
    Chủ động query PayOS API để kiểm tra trạng thái thanh toán và kích hoạt Premium.
    Gọi endpoint này sau khi user redirect về từ PayOS (không cần auth).
    """
    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY]):
        raise HTTPException(status_code=500, detail="PayOS chưa được cấu hình")

    try:
        resp_data = _query_payos_order(order_code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối PayOS: {e}")

    if resp_data.get("code") != "00":
        raise HTTPException(status_code=502, detail=f"PayOS lỗi: {resp_data.get('desc')}")

    payos_data = resp_data["data"]
    payos_status = payos_data.get("status")
    payos_ref    = payos_data.get("id", "")  # PayOS's own payment link ID

    session = _session()
    try:
        order = session.execute(
            text("SELECT user_id, plan, status FROM payment_orders WHERE order_code = :oc"),
            {"oc": order_code},
        ).fetchone()

        if not order:
            raise HTTPException(status_code=404, detail=f"Order {order_code} không tìm thấy trong DB")

        user_id, plan, current_status = order

        # Lưu payos_ref nếu chưa có
        if payos_ref:
            session.execute(
                text("UPDATE payment_orders SET payos_ref = :ref WHERE order_code = :oc AND payos_ref IS NULL"),
                {"ref": payos_ref, "oc": order_code},
            )

        if current_status == "paid":
            session.commit()
            return {"success": True, "activated": False, "already_paid": True, "status": "paid"}

        if payos_status == "PAID":
            new_expiry = _activate_premium(session, user_id, plan)
            session.execute(text("""
                UPDATE payment_orders SET status = 'paid', updated_at = NOW()
                WHERE order_code = :oc
            """), {"oc": order_code})
            session.commit()
            print(f"[verify-order] ✅ Premium activated user_id={user_id} đến {new_expiry}")
            return {
                "success":        True,
                "activated":      True,
                "premium_expiry": new_expiry.isoformat(),
                "status":         "paid",
            }

        # Chưa thanh toán hoặc bị huỷ
        session.commit()
        return {"success": True, "activated": False, "status": payos_status}

    finally:
        session.close()


@router.post("/payos-webhook")
async def payos_webhook(request: Request):
    """
    Nhận webhook từ PayOS sau khi user thanh toán thành công.
    PayOS gửi: { code, desc, success, data: { orderCode, amount, status, ..., signature } }
    Không yêu cầu Auth header — PayOS tự gọi.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body không hợp lệ")

    # Xác minh chữ ký HMAC
    if PAYOS_CHECKSUM_KEY and not _verify_payos_webhook(body):
        raise HTTPException(status_code=400, detail="Chữ ký không hợp lệ")

    data       = body.get("data", {})
    order_code = data.get("orderCode")
    status     = data.get("status")

    # Chỉ xử lý khi status là PAID
    if status != "PAID" or not order_code:
        return {"success": True}

    session = _session()
    try:
        order = session.execute(
            text("SELECT user_id, plan, status FROM payment_orders WHERE order_code = :oc"),
            {"oc": order_code},
        ).fetchone()

        if not order:
            print(f"[payos-webhook] order_code không tìm thấy: {order_code}")
            return {"success": True}

        user_id, plan, current_status = order

        if current_status == "paid":
            # Đã xử lý rồi — idempotency
            return {"success": True}

        new_expiry = _activate_premium(session, user_id, plan)

        session.execute(text("""
            UPDATE payment_orders
            SET status = 'paid', updated_at = NOW()
            WHERE order_code = :oc
        """), {"oc": order_code})

        session.commit()
        print(f"[payos-webhook] ✅ Premium user_id={user_id} đến {new_expiry}")

    finally:
        session.close()

    return {"success": True}



@router.get("/status")
async def subscription_status(request: Request):
    """
    Kiểm tra trạng thái subscription của user đang đăng nhập.
    Trả về: is_premium, premium_expiry, days_remaining, plans (giá các gói).
    """
    await authenticate_user(request)
    auth0_id = request.state.user.get("auth0_id")

    session = _session()
    try:
        with _get_engine().connect() as conn:
            _ensure_tables(conn)

        row = session.execute(
            text("SELECT is_premium, premium_expiry, user_level FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()

        if not row:
            return _status_response(False, None, "free")

        is_premium, premium_expiry, user_level = row

        # Auto-expire nếu đã quá hạn
        if is_premium and premium_expiry and premium_expiry < datetime.now():
            session.execute(text("""
                UPDATE users SET is_premium = FALSE, user_level = 'free', updated_at = NOW()
                WHERE auth0_id = :aid
            """), {"aid": auth0_id})
            session.commit()
            is_premium = False
            user_level  = "free"

        return _status_response(is_premium, premium_expiry, user_level)

    finally:
        session.close()


def _status_response(is_premium: bool, premium_expiry: Optional[datetime], user_level: str = "free") -> dict:
    days_remaining = 0
    if is_premium and premium_expiry:
        days_remaining = max(0, (premium_expiry - datetime.now()).days)
    return {
        "is_premium":     is_premium,
        "premium_expiry": premium_expiry.isoformat() if premium_expiry else None,
        "days_remaining": days_remaining,
        "user_level":     user_level,
        "plans": {
            k: {"amount": v["amount"], "days": v["days"], "name": v["name"]}
            for k, v in SUBSCRIPTION_PLANS.items()
        },
    }


# ============================================================
# FastAPI dependency: bảo vệ endpoint chỉ cho Premium user
# ============================================================

async def require_premium(request: Request):
    """
    FastAPI Depends() guard cho các endpoint chỉ dành cho Premium.

    Ví dụ sử dụng:
        @app.get("/api/v1/premium-data")
        async def premium_data(request: Request, _=Depends(require_premium)):
            ...
    """
    await authenticate_user(request)
    auth0_id = request.state.user.get("auth0_id")

    session = _session()
    try:
        row = session.execute(
            text("SELECT is_premium, premium_expiry FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
    finally:
        session.close()

    if not row or not row[0]:
        raise HTTPException(status_code=403, detail="Yêu cầu gói Premium hoặc Premium Developer")

    if row[1] and row[1] < datetime.now():
        raise HTTPException(status_code=403, detail="Gói Premium đã hết hạn")

    return request.state.user
