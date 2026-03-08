"""
Payment module: PayOS & SePay subscription webhook handling.

Luồng PayOS:
  1. Frontend gọi POST /api/v1/payment/create-order (kèm Bearer token)
  2. Backend tạo payment link PayOS → trả về { checkout_url, qr_code }
  3. User thanh toán qua VietQR / banking app
  4. PayOS gọi webhook POST /api/v1/payment/payos-webhook
  5. Backend xác minh chữ ký → cập nhật is_premium + premium_expiry cho user

Luồng SePay (thay thế đơn giản hơn):
  1. User chuyển khoản với nội dung "VIP{user_id}M" (monthly) hoặc "VIP{user_id}Y" (yearly)
  2. SePay gọi webhook POST /api/v1/payment/sepay-webhook
  3. Backend đọc content → lấy user_id + plan → cập nhật DB

Env vars cần thiết:
  PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY  (PayOS)
  SEPAY_API_KEY                                         (SePay)
  FRONTEND_URL                                          (return/cancel URL sau thanh toán)
  USER_DB hoặc ARGUS_FINTEL_DB                          (Neon DB)
"""

import hashlib
import hmac as _hmac
import json
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from middleware import authenticate_user

router = APIRouter(prefix="/api/v1/payment", tags=["payment"])

# ============================================================
# Config
# ============================================================
PAYOS_CLIENT_ID    = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY      = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
PAYOS_BASE_URL     = "https://api-merchant.payos.vn"

SEPAY_API_KEY      = os.getenv("SEPAY_API_KEY", "")

FRONTEND_URL       = os.getenv("FRONTEND_URL", "https://vietdataverse.online")

SUBSCRIPTION_PLANS = {
    "monthly": {"amount": 99_000,  "days": 30,  "name": "VIP 1 Thang"},
    "yearly":  {"amount": 990_000, "days": 365, "name": "VIP 1 Nam"},
}

# ============================================================
# DB helpers (mirrors main.py — avoids circular import)
# ============================================================
_engine_user = None


def _get_engine():
    global _engine_user
    if _engine_user is None:
        db_url = os.getenv("USER_DB") or os.getenv("ARGUS_FINTEL_DB")
        if not db_url:
            raise RuntimeError("USER_DB not configured")
        _engine_user = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=5,
            pool_recycle=300,
        )
    return _engine_user


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
            order_code  BIGINT      PRIMARY KEY,
            user_id     INT         NOT NULL,
            plan        VARCHAR(50) NOT NULL,
            amount      INT         NOT NULL,
            status      VARCHAR(20) NOT NULL DEFAULT 'pending',
            gateway     VARCHAR(20) NOT NULL DEFAULT 'payos',
            created_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMP            DEFAULT NOW()
        )
    """))
    for col, defn in [
        ("is_premium",     "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("premium_expiry", "TIMESTAMP"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}"
            ))
        except Exception:
            pass
    conn.commit()


def _activate_premium(session, user_id: int, plan: str):
    """Extend premium_expiry for a user. Stacks on top of existing subscription."""
    plan_info = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["monthly"])
    row = session.execute(
        text("SELECT premium_expiry FROM users WHERE user_id = :uid"),
        {"uid": user_id},
    ).fetchone()

    now = datetime.now()
    base = max(row[0], now) if row and row[0] and row[0] > now else now
    new_expiry = base + timedelta(days=plan_info["days"])

    session.execute(text("""
        UPDATE users
        SET is_premium = TRUE, premium_expiry = :expiry, updated_at = NOW()
        WHERE user_id = :uid
    """), {"expiry": new_expiry, "uid": user_id})
    return new_expiry


# ============================================================
# Schemas
# ============================================================

class CreateOrderRequest(BaseModel):
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

    # Lấy user_id từ DB
    session = _session()
    try:
        with _get_engine().connect() as conn:
            _ensure_tables(conn)

        row = session.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User không tồn tại trong DB")
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

    data = resp_data["data"]
    return {
        "order_code":   order_code,
        "plan":         body.plan,
        "amount":       plan_info["amount"],
        "checkout_url": data["checkoutUrl"],
        "qr_code":      data.get("qrCode", ""),
    }


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


@router.post("/sepay-webhook")
async def sepay_webhook(request: Request):
    """
    Nhận webhook từ SePay khi phát hiện chuyển khoản vào tài khoản ngân hàng.

    User cần chuyển khoản với nội dung (content) có chứa mã dạng:
      VIP{user_id}M   → gói monthly (99.000đ)
      VIP{user_id}Y   → gói yearly  (990.000đ)
    Ví dụ: "VIP42M" hoặc "THANH TOAN VIP42Y"

    SePay gọi với header: Authorization: apikey {SEPAY_API_KEY}
    """
    # Xác thực API key SePay
    if SEPAY_API_KEY:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"apikey {SEPAY_API_KEY}":
            raise HTTPException(status_code=401, detail="API key không hợp lệ")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body không hợp lệ")

    content        = body.get("content", "") or ""
    transfer_type  = body.get("transferType", "")
    transfer_amount = body.get("transferAmount", 0)

    # Chỉ xử lý tiền vào
    if transfer_type != "in":
        return {"success": True}

    # Parse mã từ nội dung chuyển khoản
    match = re.search(r"VIP(\d+)([MY])", content.upper())
    if not match:
        print(f"[sepay-webhook] Không tìm thấy mã VIP trong: '{content}'")
        return {"success": True}

    user_id   = int(match.group(1))
    plan_code = match.group(2)
    plan      = "monthly" if plan_code == "M" else "yearly"
    expected_amount = SUBSCRIPTION_PLANS[plan]["amount"]

    if transfer_amount < expected_amount:
        print(f"[sepay-webhook] Số tiền {transfer_amount} < {expected_amount} cho plan={plan}")
        return {"success": True}

    session = _session()
    try:
        # Kiểm tra user tồn tại
        exists = session.execute(
            text("SELECT 1 FROM users WHERE user_id = :uid"),
            {"uid": user_id},
        ).fetchone()
        if not exists:
            print(f"[sepay-webhook] user_id={user_id} không tồn tại")
            return {"success": True}

        # Tạo order record (SePay không có orderCode → dùng timestamp)
        order_code = user_id * 1_000_000 + (int(time.time()) % 1_000_000)
        session.execute(text("""
            INSERT INTO payment_orders (order_code, user_id, plan, amount, status, gateway)
            VALUES (:oc, :uid, :plan, :amount, 'paid', 'sepay')
        """), {
            "oc":     order_code,
            "uid":    user_id,
            "plan":   plan,
            "amount": transfer_amount,
        })

        new_expiry = _activate_premium(session, user_id, plan)
        session.commit()
        print(f"[sepay-webhook] ✅ Premium user_id={user_id} đến {new_expiry} (SePay)")

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
            text("SELECT is_premium, premium_expiry FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()

        if not row:
            return _status_response(False, None)

        is_premium, premium_expiry = row

        # Auto-expire nếu đã quá hạn
        if is_premium and premium_expiry and premium_expiry < datetime.now():
            session.execute(text("""
                UPDATE users SET is_premium = FALSE, updated_at = NOW()
                WHERE auth0_id = :aid
            """), {"aid": auth0_id})
            session.commit()
            is_premium = False

        return _status_response(is_premium, premium_expiry)

    finally:
        session.close()


def _status_response(is_premium: bool, premium_expiry: Optional[datetime]) -> dict:
    days_remaining = 0
    if is_premium and premium_expiry:
        days_remaining = max(0, (premium_expiry - datetime.now()).days)
    return {
        "is_premium":     is_premium,
        "premium_expiry": premium_expiry.isoformat() if premium_expiry else None,
        "days_remaining": days_remaining,
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
        raise HTTPException(status_code=403, detail="Yêu cầu gói Premium")

    if row[1] and row[1] < datetime.now():
        raise HTTPException(status_code=403, detail="Gói Premium đã hết hạn")

    return request.state.user
