"""
Referral system — link giới thiệu cho tài khoản API Supper Lite.

- GET  /api/v1/referral/my-code  — lấy/tạo mã giới thiệu + stats
- Referral code được nhúng vào URL: /pages/pricing.html?ref=CODE
- Khi người mới thanh toán qua link → referrer nhận 10% giá trị vào wallet
  (xử lý trong payment.py khi webhook PAID)
"""

import os
import random
import string

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from core.engines import get_engine_user
from middleware import authenticate_user

router = APIRouter(prefix="/api/v1/referral", tags=["referral"])

FRONTEND_URL     = os.getenv("FRONTEND_URL", "https://vietdataverse.online")
ELIGIBLE_LEVELS  = {"premium_developer", "admin"}
REFERRAL_CODE_LEN = 8


def _session():
    return sessionmaker(bind=get_engine_user())()


def _ensure_referral_schema(conn):
    """Add referral columns idempotently."""
    try:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(16) UNIQUE"
        ))
    except Exception:
        pass
    for col, defn in [
        ("ref_code",           "VARCHAR(16)"),
        ("referral_credited",  "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("student_discount",   "BOOLEAN NOT NULL DEFAULT FALSE"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE payment_orders ADD COLUMN IF NOT EXISTS {col} {defn}"
            ))
        except Exception:
            pass
    # wallet_balance on users
    try:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS wallet_balance BIGINT NOT NULL DEFAULT 0"
        ))
    except Exception:
        pass
    # wallet_transactions table
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
    try:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_wallet_tx_user ON wallet_transactions(user_id, created_at)"
        ))
    except Exception:
        pass
    conn.commit()


def _gen_code() -> str:
    chars = string.ascii_lowercase + string.digits
    return "".join(random.choices(chars, k=REFERRAL_CODE_LEN))


@router.get("/my-code")
async def get_my_referral_code(request: Request):
    """
    Trả về referral code và URL cho tài khoản API Supper Lite.
    Nếu chưa có code thì tạo mới.
    """
    await authenticate_user(request)
    user     = request.state.user
    auth0_id = user.get("auth0_id")

    if user.get("user_level") not in ELIGIBLE_LEVELS:
        raise HTTPException(
            status_code=403,
            detail="Chỉ tài khoản API Supper Lite mới có thể tạo link giới thiệu.",
        )

    session = _session()
    try:
        with get_engine_user().connect() as conn:
            _ensure_referral_schema(conn)

        row = session.execute(text("""
            SELECT user_id, referral_code, wallet_balance
            FROM users WHERE auth0_id = :aid
        """), {"aid": auth0_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")

        user_id, ref_code, wallet_balance = row

        # Generate code if not exists
        if not ref_code:
            for _ in range(10):
                code = _gen_code()
                try:
                    session.execute(text("""
                        UPDATE users SET referral_code = :code WHERE user_id = :uid
                    """), {"code": code, "uid": user_id})
                    session.commit()
                    ref_code = code
                    break
                except Exception:
                    session.rollback()
            else:
                raise HTTPException(status_code=500, detail="Không thể tạo referral code. Thử lại.")

        # Stats: orders that used this code and were paid + credited
        stats = session.execute(text("""
            SELECT
                COUNT(*) AS referral_count,
                COALESCE(SUM(po.amount * 0.1), 0) AS total_earned
            FROM payment_orders po
            WHERE po.ref_code = :code
              AND po.status = 'paid'
              AND po.referral_credited = TRUE
        """), {"code": ref_code}).fetchone()

        referral_count = int(stats[0]) if stats else 0
        total_earned   = int(stats[1]) if stats else 0
        ref_url        = f"{FRONTEND_URL}/pages/pricing.html?ref={ref_code}"

        return {
            "referral_code":   ref_code,
            "referral_url":    ref_url,
            "referral_count":  referral_count,
            "total_earned_vnd": total_earned,
            "wallet_balance":  wallet_balance or 0,
            "reward_pct":      10,
        }
    finally:
        session.close()
