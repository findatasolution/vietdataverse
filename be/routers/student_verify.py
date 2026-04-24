"""
Student email verification — giảm 50% cho sinh viên.

Flow:
  POST /api/v1/student/send-otp    — gửi OTP đến email .edu.vn
  POST /api/v1/student/confirm-otp — xác nhận OTP → student_verified = TRUE
  GET  /api/v1/student/status      — trạng thái xác minh của account

Chính sách:
  - Chỉ chấp nhận email domain kết thúc bằng .edu.vn
  - OTP 6 chữ số, hết hạn sau 10 phút
  - Tối đa 3 lần gửi OTP / email / giờ (chống spam)
  - Mỗi account chỉ cần verify 1 lần
  - Chỉ áp dụng cho tài khoản đã đăng nhập (không hỗ trợ guest)
"""

import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from core.engines import get_engine_user
from core.email import send_otp_email
from middleware import authenticate_user

router = APIRouter(prefix="/api/v1/student", tags=["student"])

STUDENT_DOMAIN_SUFFIX = ".edu.vn"


def _session():
    return sessionmaker(bind=get_engine_user())()


def _ensure_student_tables(conn):
    """Idempotent DDL for student verification."""
    # Add columns to users if missing
    for col, defn in [
        ("student_verified",    "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("student_email",       "VARCHAR(255)"),
        ("student_verified_at", "TIMESTAMP"),
    ]:
        try:
            conn.execute(text(
                f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {defn}"
            ))
        except Exception:
            pass

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS email_otps (
            id         SERIAL      PRIMARY KEY,
            user_id    INT         NOT NULL,
            email      VARCHAR(255) NOT NULL,
            otp_code   VARCHAR(8)  NOT NULL,
            purpose    VARCHAR(30) NOT NULL,
            expires_at TIMESTAMP   NOT NULL,
            used       BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP   NOT NULL DEFAULT NOW()
        )
    """))
    try:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_email_otps_email_purpose ON email_otps(email, purpose, created_at)"
        ))
    except Exception:
        pass
    conn.commit()


class SendOtpRequest(BaseModel):
    email: str


class ConfirmOtpRequest(BaseModel):
    email: str
    otp_code: str


@router.post("/send-otp")
async def send_otp(body: SendOtpRequest, request: Request):
    await authenticate_user(request)
    user     = request.state.user
    auth0_id = user.get("auth0_id")

    email = body.email.strip().lower()

    if not email.endswith(STUDENT_DOMAIN_SUFFIX):
        raise HTTPException(
            status_code=400,
            detail="Chỉ chấp nhận email có đuôi .edu.vn (email trường đại học / cao đẳng Việt Nam).",
        )

    session = _session()
    try:
        with get_engine_user().connect() as conn:
            _ensure_student_tables(conn)

        row = session.execute(
            text("SELECT user_id, student_verified FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")
        user_id, already_verified = row

        if already_verified:
            raise HTTPException(
                status_code=400,
                detail="Tài khoản đã được xác minh sinh viên rồi. Không cần xác minh lại.",
            )

        # Rate limit: max 3 OTP / email / hour
        count = session.execute(text("""
            SELECT COUNT(*) FROM email_otps
            WHERE email = :email AND purpose = 'student_verify'
              AND created_at > NOW() - INTERVAL '1 hour'
        """), {"email": email}).scalar()
        if count >= 3:
            raise HTTPException(
                status_code=429,
                detail="Quá nhiều yêu cầu. Chờ 1 giờ trước khi thử lại.",
            )

        # Generate 6-digit OTP
        otp = "".join(random.choices(string.digits, k=6))
        expires_at = datetime.now() + timedelta(minutes=10)

        session.execute(text("""
            INSERT INTO email_otps (user_id, email, otp_code, purpose, expires_at)
            VALUES (:uid, :email, :otp, 'student_verify', :exp)
        """), {"uid": user_id, "email": email, "otp": otp, "exp": expires_at})
        session.commit()

        try:
            send_otp_email(email, otp)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Không thể gửi email: {e}")

        return {"success": True, "message": f"Mã OTP đã gửi đến {email}. Kiểm tra hộp thư (kể cả Spam)."}
    finally:
        session.close()


@router.post("/confirm-otp")
async def confirm_otp(body: ConfirmOtpRequest, request: Request):
    await authenticate_user(request)
    user     = request.state.user
    auth0_id = user.get("auth0_id")

    email    = body.email.strip().lower()
    otp_code = body.otp_code.strip()

    session = _session()
    try:
        row = session.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")
        user_id = row[0]

        otp_row = session.execute(text("""
            SELECT id, expires_at, used
            FROM email_otps
            WHERE user_id = :uid AND email = :email
              AND otp_code = :otp AND purpose = 'student_verify'
            ORDER BY created_at DESC
            LIMIT 1
        """), {"uid": user_id, "email": email, "otp": otp_code}).fetchone()

        if not otp_row:
            raise HTTPException(status_code=400, detail="Mã OTP không đúng.")

        otp_id, expires_at, used = otp_row

        if used:
            raise HTTPException(status_code=400, detail="Mã OTP này đã được sử dụng rồi.")
        if datetime.now() > expires_at:
            raise HTTPException(status_code=400, detail="Mã OTP đã hết hạn. Vui lòng yêu cầu mã mới.")

        # Consume OTP
        session.execute(
            text("UPDATE email_otps SET used = TRUE WHERE id = :id"),
            {"id": otp_id},
        )

        # Mark user student-verified
        session.execute(text("""
            UPDATE users
            SET student_verified    = TRUE,
                student_email       = :email,
                student_verified_at = NOW()
            WHERE user_id = :uid
        """), {"email": email, "uid": user_id})

        session.commit()
        return {
            "success": True,
            "message": "Xác minh sinh viên thành công! Bạn được giảm 50% khi mua gói Pro Data.",
        }
    finally:
        session.close()


@router.get("/status")
async def student_status(request: Request):
    """Trả trạng thái student_verified của account đang đăng nhập."""
    await authenticate_user(request)
    user     = request.state.user
    auth0_id = user.get("auth0_id")

    session = _session()
    try:
        row = session.execute(text("""
            SELECT student_verified, student_email, student_verified_at
            FROM users WHERE auth0_id = :aid
        """), {"aid": auth0_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")

        verified, student_email, verified_at = row
        return {
            "student_verified": bool(verified),
            "student_email":    student_email,
            "verified_at":      verified_at.isoformat() if verified_at else None,
            "discount_pct":     50 if verified else 0,
        }
    finally:
        session.close()
