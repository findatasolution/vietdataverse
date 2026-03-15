"""
Developer API Key management.
Chỉ dành cho user_level = premium_developer.
"""

import secrets

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from middleware import authenticate_user
from core.engines import get_engine_user

router = APIRouter(prefix="/api/v1/developer", tags=["developer"])


def _session():
    return sessionmaker(bind=get_engine_user())()


@router.post("/generate-key")
async def generate_key(request: Request):
    """
    Tạo API key mới cho premium_developer.
    Key cũ (nếu có) bị thu hồi tự động.
    """
    await authenticate_user(request)
    user = request.state.user

    if user.get("user_level") != "premium_developer":
        raise HTTPException(
            status_code=403,
            detail="Chỉ tài khoản Premium Developer mới có thể tạo API key",
        )

    auth0_id = user.get("auth0_id")
    session = _session()
    try:
        row = session.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")

        user_id = row[0]

        # Thu hồi các key cũ
        session.execute(
            text("UPDATE api_keys SET is_active = FALSE WHERE user_id = :uid"),
            {"uid": user_id},
        )

        new_key = secrets.token_urlsafe(32)
        session.execute(
            text("INSERT INTO api_keys (user_id, key_value) VALUES (:uid, :key)"),
            {"uid": user_id, "key": new_key},
        )
        session.commit()

        return {
            "api_key": new_key,
            "note": "Lưu key này ngay — sẽ không hiển thị lại sau khi rời trang.",
        }
    finally:
        session.close()


@router.get("/key-info")
async def key_info(request: Request):
    """Xem thông tin API key hiện tại (masked)."""
    await authenticate_user(request)
    user = request.state.user

    if user.get("user_level") != "premium_developer":
        raise HTTPException(status_code=403, detail="Chỉ Premium Developer")

    auth0_id = user.get("auth0_id")
    session = _session()
    try:
        row = session.execute(text("""
            SELECT ak.key_value, ak.created_at, ak.last_used_at
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.user_id
            WHERE u.auth0_id = :aid AND ak.is_active = TRUE
            ORDER BY ak.created_at DESC
            LIMIT 1
        """), {"aid": auth0_id}).fetchone()

        if not row:
            return {"has_key": False, "key_preview": None, "created_at": None, "last_used_at": None}

        key_val = row[0]
        masked = key_val[:8] + "..." + key_val[-4:]
        return {
            "has_key":      True,
            "key_preview":  masked,
            "created_at":   row[1].isoformat() if row[1] else None,
            "last_used_at": row[2].isoformat() if row[2] else None,
        }
    finally:
        session.close()


@router.delete("/revoke-key")
async def revoke_key(request: Request):
    """Thu hồi API key hiện tại."""
    await authenticate_user(request)
    user = request.state.user

    if user.get("user_level") != "premium_developer":
        raise HTTPException(status_code=403, detail="Chỉ Premium Developer")

    auth0_id = user.get("auth0_id")
    session = _session()
    try:
        session.execute(text("""
            UPDATE api_keys ak
            SET is_active = FALSE
            FROM users u
            WHERE ak.user_id = u.user_id
              AND u.auth0_id = :aid
              AND ak.is_active = TRUE
        """), {"aid": auth0_id})
        session.commit()
        return {"success": True, "message": "API key đã bị thu hồi"}
    finally:
        session.close()
