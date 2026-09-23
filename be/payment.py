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
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from middleware import authenticate_user
from core.engines import get_engine_user
from quota import get_quota

router = APIRouter(prefix="/api/v1/payment", tags=["payment"])

# ============================================================
# Config
# ============================================================
PAYOS_CLIENT_ID    = os.getenv("PAYOS_CLIENT_ID", "")
PAYOS_API_KEY      = os.getenv("PAYOS_API_KEY", "")
PAYOS_CHECKSUM_KEY = os.getenv("PAYOS_CHECKSUM_KEY", "")
PAYOS_BASE_URL     = "https://api-merchant.payos.vn"

FRONTEND_URL       = os.getenv("FRONTEND_URL", "https://vietdataverse.online")

# ĐÚNG 2 gói bán, cộng với free (free không nằm ở đây vì không có gì để thanh
# toán — nó là mặc định của mọi tài khoản; /plans ghép nó vào từ quota.py).
#
# Rút gọn 2026-09-23 theo quyết định sản phẩm: 4 gói legacy
# (premium_monthly/premium_yearly/dev_monthly/dev_yearly) đã bị XOÁ HẲN, không
# phải "giữ để replay webhook" như trước. Kiểm tra trước khi xoá: 0 user đang ở
# các gói đó (users.current_plan chỉ có 1 hàng 'dev_monthly' và đó là tài khoản
# admin, vốn unlimited theo level). Các đơn payment_orders cũ trỏ tới gói legacy
# đều đang 'pending' và giờ sẽ bị từ chối bằng 409 "Loại đơn hàng không được hỗ
# trợ" nếu ai đó reverify — đúng ý: gói không còn tồn tại thì không được kích
# hoạt lại. Đơn 'paid' duy nhất mang plan 'monthly', một key chưa bao giờ có
# trong dict này, nên không có gì thay đổi với nó.
#
# Giá 45k/tháng từ 2026-09-16 (trước là 99k). Gói năm giữ dạng "trả 10 tháng
# dùng 12": 45_000 x 10. Tier sinh viên KHÔNG phải một gói riêng —
# create_payment() chia đôi số tiền của gói đang chọn, nên 45k/450k thành
# 22.5k/225k cho tài khoản .edu.vn đã xác minh.
#
# Hạn mức gọi API của hai gói này nằm ở be/quota.py (level premium_developer),
# không nằm ở đây.
SUBSCRIPTION_PLANS = {
    "pro_monthly": {"amount": 45_000,  "days": 30,  "level": "premium_developer", "name": "API Supper Lite Monthly"},
    "pro_yearly":  {"amount": 450_000, "days": 365, "level": "premium_developer", "name": "API Supper Lite Yearly"},
}


@router.get("/plans")
async def public_plans():
    """Public purchase facts from the same configuration used by billing/quota."""
    plans = [{"key": "free", "amount": 0, "days": None,
              **get_quota("free", None)}]
    for key in ("pro_monthly", "pro_yearly"):
        plan = SUBSCRIPTION_PLANS[key]
        plans.append({"key": key, "amount": plan["amount"], "days": plan["days"],
                      **get_quota(plan["level"], key)})
    return {"success": True, "source": "billing_config", "count": len(plans),
            "data": plans, "auto_renew": False}


def checkout_return_url(**params):
    """Always return to the page that verifies the payment, not the SPA root."""
    parsed = urlsplit(FRONTEND_URL)
    path = parsed.path if parsed.path.endswith("/pricing.html") else "/pages/pricing.html"
    return urlunsplit((parsed.scheme, parsed.netloc, path, urlencode(params), ""))

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
    PayOS sends { code, desc, success, data: {...}, signature: "..." }
    Signature ở TOP LEVEL (không phải trong data). Được tính là HMAC-SHA256 của
    chuỗi "k=v&k=v..." từ data đã sort theo key. null → "", array → JSON stringify.
    """
    data = body.get("data", {}) or {}
    received_sig = body.get("signature") or data.get("signature", "")
    if not isinstance(received_sig, str) or not received_sig:
        return False

    def _fmt(v):
        if v is None:
            return ""
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (list, tuple)):
            return json.dumps(list(v), separators=(",", ":"), ensure_ascii=False)
        return str(v)

    sorted_pairs = "&".join(
        f"{k}={_fmt(v)}"
        for k, v in sorted(data.items())
        if k != "signature"
    )
    expected = _hmac.new(
        PAYOS_CHECKSUM_KEY.encode("utf-8"),
        sorted_pairs.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
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
        ("student_verified",    "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("student_email",       "VARCHAR(255)"),
        ("referral_code",       "VARCHAR(16)"),
        ("wallet_balance",      "BIGINT NOT NULL DEFAULT 0"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}"
            ))
        except Exception:
            pass

    for col, defn in [
        ("ref_code",          "VARCHAR(16)"),
        ("referral_credited", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("student_discount",  "BOOLEAN NOT NULL DEFAULT FALSE"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS {col} {defn}"
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
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id           SERIAL      PRIMARY KEY,
            user_id      INT         NOT NULL,
            amount       BIGINT      NOT NULL,
            type         VARCHAR(30) NOT NULL,
            reference_id VARCHAR(50),
            note         TEXT,
            created_at   TIMESTAMP   NOT NULL DEFAULT NOW()
        )
    """))
    conn.commit()


def _activate_premium(session, user_id: int, plan: str):
    """Extend premium_expiry for a user. Stacks on top of existing subscription.

    Side effects:
      - Set users.current_plan = plan (cho quota lookup trong middleware).
      - Reactivate mọi api_keys của user (để renew không bắt gen key mới).
    """
    # Không có fallback. Trước đây dòng này là
    #     SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["premium_monthly"])
    # — một plan lạ sẽ âm thầm được kích hoạt như gói legacy premium_monthly.
    # Với catalog chỉ còn 2 gói thì fallback đó vừa là KeyError lúc import-time
    # chờ sẵn, vừa là hành vi sai: gói không tồn tại thì phải báo lỗi, không
    # được cấp quyền. Caller duy nhất (webhook) đã chặn bằng
    # `plan in SUBSCRIPTION_PLANS` rồi, nên nhánh này chỉ bắt lỗi lập trình.
    plan_info = SUBSCRIPTION_PLANS.get(plan)
    if plan_info is None:
        raise ValueError(f"Không kích hoạt được gói không tồn tại: {plan!r}")
    new_level = plan_info["level"]  # hiện chỉ còn "premium_developer"

    row = session.execute(
        text("SELECT premium_expiry FROM users WHERE user_id = :uid FOR UPDATE"),
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
    resp.raise_for_status()
    return resp.json()


def _settle_paid_order(order_code: int, amount: int, payos_ref: str = "") -> dict:
    """Settle once across webhook/return-page races; never infer the product."""
    session = _session()
    try:
        order = session.execute(text("""
            SELECT user_id, plan, status, order_type, credit_amount, amount, payos_ref
            FROM payment_orders WHERE order_code = :oc FOR UPDATE
        """), {"oc": order_code}).fetchone()
        if not order:
            return {"success": True, "unknown_order": True}
        user_id, plan, status, order_type, credits, expected, saved_ref = order
        if type(amount) is not int or amount != expected:
            raise HTTPException(status_code=409, detail="Số tiền thanh toán không khớp đơn hàng")
        if saved_ref and payos_ref and saved_ref != payos_ref:
            raise HTTPException(status_code=409, detail="Mã thanh toán không khớp đơn hàng")
        kind = order_type or "subscription"
        result = {"success": True, "activated": False, "already_paid": status == "paid",
                  "status": "paid", "order_type": kind, "plan": plan, "amount": expected}
        if status == "paid":
            return result
        if kind == "credit_topup":
            if not credits or credits <= 0:
                raise HTTPException(status_code=409, detail="Đơn nạp credits không hợp lệ")
            from services.credit import credit_topup
            # The wallet DB has its own transaction. Its idempotency key also
            # makes a retry safe if this payment transaction fails to commit.
            credit_topup(user_id=user_id, credits=credits,
                         idem_key=f"payos:{order_code}", note=f"PayOS topup order={order_code}")
        elif kind == "subscription" and plan in SUBSCRIPTION_PLANS:
            expiry = _activate_premium(session, user_id, plan)
            result.update(activated=True, premium_expiry=expiry.isoformat())
        else:
            raise HTTPException(status_code=409, detail="Loại đơn hàng không được hỗ trợ")
        session.execute(text("""
            UPDATE payment_orders SET status = 'paid', updated_at = NOW(),
                payos_ref = COALESCE(payos_ref, :ref) WHERE order_code = :oc
        """), {"oc": order_code, "ref": payos_ref or None})
        session.commit()
        return result
    finally:
        session.close()


# ============================================================
# Schemas
# ============================================================

class CreateOrderRequest(BaseModel):
    plan: str
    ref_code: str | None = None  # optional referral code


class GuestOrderRequest(BaseModel):
    email: str
    plan: str
    ref_code: str | None = None


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
            text("SELECT user_id, student_verified FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()

        if not row:
            email = user.get("email", "")
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
                user_db_id, student_verified = existing[0], False
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
                user_db_id, student_verified = result.fetchone()[0], False
        else:
            user_db_id, student_verified = row[0], bool(row[1])
    finally:
        session.close()

    # Apply student discount (50%)
    base_amount = plan_info["amount"]
    final_amount = base_amount // 2 if student_verified else base_amount
    has_student_discount = student_verified

    # Validate ref_code (prevent self-referral)
    ref_code = (body.ref_code or "").strip().lower() or None
    if ref_code:
        session = _session()
        try:
            ref_owner = session.execute(
                text("SELECT user_id FROM users WHERE referral_code = :code"),
                {"code": ref_code},
            ).fetchone()
            if not ref_owner or ref_owner[0] == user_db_id:
                ref_code = None  # invalid or self-referral → ignore silently
        finally:
            session.close()

    # Tạo order_code duy nhất
    order_code = user_db_id * 1_000_000 + (int(time.time()) % 1_000_000)

    session = _session()
    try:
        session.execute(text("""
            INSERT INTO payment_orders
                (order_code, user_id, plan, amount, gateway, ref_code, student_discount)
            VALUES (:oc, :uid, :plan, :amount, 'payos', :ref, :sd)
        """), {
            "oc":     order_code,
            "uid":    user_db_id,
            "plan":   body.plan,
            "amount": final_amount,
            "ref":    ref_code,
            "sd":     has_student_discount,
        })
        session.commit()
    finally:
        session.close()

    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY]):
        raise HTTPException(status_code=500, detail="PAYOS_* env vars chưa được cấu hình")

    return_url  = checkout_return_url(payment="success", order=order_code)
    cancel_url  = checkout_return_url(payment="cancelled")
    description = plan_info["name"][:25]

    payload = {
        "orderCode":   order_code,
        "amount":      final_amount,
        "description": description,
        "returnUrl":   return_url,
        "cancelUrl":   cancel_url,
        "signature":   _payos_checksum(
            final_amount, cancel_url, description, order_code, return_url
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
        "order_code":       order_code,
        "plan":             body.plan,
        "amount":           final_amount,
        "original_amount":  base_amount,
        "student_discount": has_student_discount,
        "checkout_url":     data["checkoutUrl"],
        "qr_code":          data.get("qrCode", ""),
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

    # Validate ref_code (guest can't self-refer since they're new, but check anyway)
    ref_code_guest = (body.ref_code or "").strip().lower() or None
    if ref_code_guest:
        session = _session()
        try:
            ref_owner = session.execute(
                text("SELECT user_id FROM users WHERE referral_code = :code"),
                {"code": ref_code_guest},
            ).fetchone()
            if not ref_owner or ref_owner[0] == user_db_id:
                ref_code_guest = None
        finally:
            session.close()

    session = _session()
    try:
        session.execute(text("""
            INSERT INTO payment_orders (order_code, user_id, plan, amount, gateway, ref_code)
            VALUES (:oc, :uid, :plan, :amount, 'payos', :ref)
        """), {
            "oc":     order_code,
            "uid":    user_db_id,
            "plan":   body.plan,
            "amount": plan_info["amount"],
            "ref":    ref_code_guest,
        })
        session.commit()
    finally:
        session.close()

    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY]):
        raise HTTPException(status_code=500, detail="PAYOS_* env vars chưa được cấu hình")

    return_url  = checkout_return_url(payment="success", order=order_code)
    cancel_url  = checkout_return_url(payment="cancelled")
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
    """Confirm through PayOS, then share the webhook's idempotent settlement."""
    if not all([PAYOS_CLIENT_ID, PAYOS_API_KEY]):
        raise HTTPException(status_code=503, detail="PayOS chưa được cấu hình")
    try:
        response = _query_payos_order(order_code)
    except Exception:
        raise HTTPException(status_code=502, detail="Chưa thể kết nối PayOS. Vui lòng thử lại.")
    data = response.get("data")
    if response.get("code") != "00" or not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Chưa xác minh được đơn hàng qua PayOS")
    if data.get("orderCode") != order_code:
        raise HTTPException(status_code=502, detail="PayOS trả về đơn hàng không khớp")
    if data.get("status") != "PAID":
        return {"success": True, "activated": False, "status": data.get("status")}
    if (type(data.get("amount")) is not int or type(data.get("amountPaid")) is not int
            or data["amountPaid"] < data["amount"]):
        raise HTTPException(status_code=409, detail="Chưa xác nhận đủ số tiền thanh toán")
    result = _settle_paid_order(order_code, data["amount"], data.get("id", ""))
    if result.get("unknown_order"):
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng")
    return result


@router.post("/payos-webhook")
async def payos_webhook(request: Request):
    """Accept signed payOS code=00 callbacks (which have no status field)."""
    if not PAYOS_CHECKSUM_KEY:
        raise HTTPException(status_code=503, detail="Chưa cấu hình xác minh PayOS")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body không hợp lệ")
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise HTTPException(status_code=400, detail="Body không hợp lệ")
    if not _verify_payos_webhook(body):
        raise HTTPException(status_code=400, detail="Chữ ký không hợp lệ")
    data = body["data"]
    # Only the signed nested code determines transaction success.
    if data.get("code") != "00":
        return {"success": True}
    order_code = data.get("orderCode")
    if type(order_code) is not int or order_code <= 0 or data.get("currency") != "VND":
        raise HTTPException(status_code=400, detail="Thông tin giao dịch không hợp lệ")
    _settle_paid_order(order_code, data.get("amount"), data.get("paymentLinkId", ""))
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

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[payment/status] ERROR for auth0_id={auth0_id}: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Subscription status error")
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
        raise HTTPException(status_code=403, detail="Yêu cầu gói Premium hoặc API Supper Lite trở lên")

    if row[1] and row[1] < datetime.now():
        raise HTTPException(status_code=403, detail="Gói Premium đã hết hạn")

    return request.state.user
