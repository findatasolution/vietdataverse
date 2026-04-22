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
from quota import read_usage

router = APIRouter(prefix="/api/v1/developer", tags=["developer"])


def _session():
    return sessionmaker(bind=get_engine_user())()


def _get_user_row(session, auth0_id: str):
    return session.execute(
        text("""
            SELECT user_id, current_plan, premium_expiry, is_admin
            FROM users WHERE auth0_id = :aid
        """),
        {"aid": auth0_id},
    ).fetchone()


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
        row = _get_user_row(session, auth0_id)
        if not row:
            raise HTTPException(status_code=404, detail="User không tìm thấy")

        user_id, current_plan, premium_expiry, is_admin = row

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

        with get_engine_user().connect() as conn:
            quota_info = read_usage(conn, user_id, "premium_developer", current_plan)

        return {
            "api_key": new_key,
            "note": "Lưu key này ngay — sẽ không hiển thị lại sau khi rời trang.",
            "quota_info": quota_info,
            "subscription": {
                "plan": current_plan,
                "premium_expiry": premium_expiry.isoformat() if premium_expiry else None,
            },
        }
    finally:
        session.close()


@router.get("/key-info")
async def key_info(request: Request):
    """Xem thông tin API key hiện tại (masked) + usage quota tháng này."""
    await authenticate_user(request)
    user = request.state.user

    if user.get("user_level") != "premium_developer":
        raise HTTPException(status_code=403, detail="Chỉ Premium Developer")

    auth0_id = user.get("auth0_id")
    session = _session()
    try:
        urow = _get_user_row(session, auth0_id)
        if not urow:
            raise HTTPException(status_code=404, detail="User không tìm thấy")
        user_id, current_plan, premium_expiry, is_admin = urow

        krow = session.execute(text("""
            SELECT ak.key_value, ak.key_id, ak.created_at, ak.last_used_at, ak.is_active
            FROM api_keys ak
            WHERE ak.user_id = :uid
            ORDER BY ak.created_at DESC
            LIMIT 1
        """), {"uid": user_id}).fetchone()

        with get_engine_user().connect() as conn:
            quota_info = read_usage(conn, user_id, "premium_developer", current_plan)

        if not krow:
            return {
                "has_key": False, "key_preview": None,
                "created_at": None, "last_used_at": None,
                "is_active": False,
                "quota_info": quota_info,
                "subscription": {
                    "plan": current_plan,
                    "premium_expiry": premium_expiry.isoformat() if premium_expiry else None,
                },
            }

        key_val, key_id, created_at, last_used_at, is_active = krow
        masked = key_val[:8] + "..." + key_val[-4:]
        return {
            "has_key":      True,
            "key_preview":  masked,
            "created_at":   created_at.isoformat() if created_at else None,
            "last_used_at": last_used_at.isoformat() if last_used_at else None,
            "is_active":    bool(is_active),
            "quota_info":   quota_info,
            "subscription": {
                "plan": current_plan,
                "premium_expiry": premium_expiry.isoformat() if premium_expiry else None,
            },
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


@router.get("/endpoints")
async def list_endpoints():
    """
    Liệt kê tất cả data endpoints có thể gọi qua API key.
    Không yêu cầu auth — dùng cho trang api-docs.html public.
    """
    return {
        "quota": {
            "dev_monthly": {"monthly_requests": 10_000,  "burst_per_sec": 10},
            "dev_yearly":  {"monthly_requests": 100_000, "burst_per_sec": 20},
            "auth_header": "X-API-Key",
            "error_codes": {
                "401": "Key không tồn tại hoặc đã bị thu hồi",
                "402": "Subscription hết hạn — gia hạn để tiếp tục",
                "403": "Tier không có quyền truy cập endpoint này",
                "429": "Vượt quota tháng hoặc burst rate-limit",
            },
        },
        "endpoints": [
            # ── Hàng hoá (Commodity) ─────────────────────────────────────
            {
                "path": "/api/v1/gold",
                "method": "GET",
                "access": "free",
                "description": "Giá vàng trong nước (mua/bán) theo ngày",
                "params": [
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                    {"name": "type",   "type": "string", "example": "DOJI HN", "description": "Loại vàng"},
                ],
            },
            {
                "path": "/api/v1/gold/types",
                "method": "GET",
                "access": "free",
                "description": "Danh sách loại vàng khả dụng",
                "params": [],
            },
            {
                "path": "/api/v1/silver",
                "method": "GET",
                "access": "free",
                "description": "Giá bạc trong nước (mua/bán) theo ngày",
                "params": [
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                ],
            },
            # ── Lãi suất & tỷ giá ────────────────────────────────────────
            {
                "path": "/api/v1/sbv-interbank",
                "method": "GET",
                "access": "free",
                "description": "Lãi suất liên ngân hàng NHNN (qua đêm, 1m, 3m, 6m, 9m, tái cấp vốn, tái chiết khấu)",
                "params": [
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                ],
            },
            {
                "path": "/api/v1/sbv-centralrate",
                "method": "GET",
                "access": "free",
                "description": "Tỷ giá ngoại tệ theo ngân hàng (mua/bán)",
                "params": [
                    {"name": "period",   "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                    {"name": "bank",     "type": "string", "example": "SBV"},
                    {"name": "currency", "type": "string", "example": "USD"},
                ],
            },
            {
                "path": "/api/v1/termdepo",
                "method": "GET",
                "access": "free",
                "description": "Lãi suất tiền gửi kỳ hạn theo ngân hàng (1m, 3m, 6m, 12m, 24m)",
                "params": [
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                    {"name": "bank",   "type": "string", "example": "ACB"},
                ],
            },
            {
                "path": "/api/v1/termdepo/banks",
                "method": "GET",
                "access": "free",
                "description": "Danh sách mã ngân hàng khả dụng cho termdepo",
                "params": [],
            },
            # ── Thị trường toàn cầu ──────────────────────────────────────
            {
                "path": "/api/v1/global-macro",
                "method": "GET",
                "access": "free",
                "description": "Giá vàng/bạc thế giới và NASDAQ theo ngày",
                "params": [
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y", "all"], "default": "1m"},
                ],
            },
            # ── Vĩ mô Việt Nam ───────────────────────────────────────────
            {
                "path": "/api/v1/macro/cpi",
                "method": "GET",
                "access": "free",
                "description": "CPI Việt Nam theo tháng/năm (nguồn: GSO/TCTK)",
                "params": [
                    {"name": "view",  "type": "string", "options": ["annual", "monthly"], "default": "annual"},
                    {"name": "years", "type": "int", "default": 20, "max": 30},
                ],
            },
            {
                "path": "/api/v1/macro/gdp",
                "method": "GET",
                "access": "free",
                "description": "GDP Việt Nam theo quý và ngành",
                "params": [],
            },
            {
                "path": "/api/v1/macro/trade",
                "method": "GET",
                "access": "free",
                "description": "Xuất nhập khẩu Việt Nam theo tháng",
                "params": [
                    {"name": "months", "type": "int", "default": 12, "max": 60},
                ],
            },
            # ── VN30 cổ phiếu ────────────────────────────────────────────
            {
                "path": "/api/v1/vn30/profile",
                "method": "GET",
                "access": "free",
                "description": "Danh sách 30 công ty VN30 và phân loại ngành ICB",
                "params": [],
            },
            {
                "path": "/api/v1/vn30/sector-summary",
                "method": "GET",
                "access": "free",
                "description": "Tổng hợp chỉ số tài chính theo ngành ICB",
                "params": [],
            },
            {
                "path": "/api/v1/vn30/prices/{ticker}",
                "method": "GET",
                "access": "premium_developer",
                "description": "Lịch sử giá OHLCV theo mã cổ phiếu",
                "params": [
                    {"name": "ticker", "type": "path", "example": "VNM"},
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y"], "default": "1m"},
                ],
            },
            {
                "path": "/api/v1/vn30/financials/{ticker}",
                "method": "GET",
                "access": "premium_developer",
                "description": "Báo cáo tài chính hàng quý (KQKD, CĐKT, LCTT)",
                "params": [
                    {"name": "ticker",   "type": "path", "example": "VNM"},
                    {"name": "quarters", "type": "int", "default": 8, "max": 20},
                ],
            },
            {
                "path": "/api/v1/vn30/ratios/{ticker}",
                "method": "GET",
                "access": "premium_developer",
                "description": "Lịch sử tỷ số tài chính (P/E, P/B, ROE, ROA, EPS...)",
                "params": [
                    {"name": "ticker", "type": "path", "example": "VNM"},
                    {"name": "period", "type": "string", "options": ["7d", "1m", "1y"], "default": "1m"},
                ],
            },
            # ── AI & Phân tích ───────────────────────────────────────────
            {
                "path": "/api/v1/vn30-scores",
                "method": "GET",
                "access": "premium_developer",
                "description": "Xếp hạng VN30 theo xác suất tăng giá (AI model). Dev: 30 mã đầy đủ",
                "params": [],
            },
            {
                "path": "/api/v1/vn30-scores/meta",
                "method": "GET",
                "access": "free",
                "description": "Metadata của batch dự đoán VN30 mới nhất",
                "params": [],
            },
            {
                "path": "/api/v1/vn30-scores/ticker/{ticker}",
                "method": "GET",
                "access": "premium_developer",
                "description": "Lịch sử điểm dự đoán hàng tuần cho một mã cổ phiếu",
                "params": [
                    {"name": "ticker", "type": "path", "example": "VNM"},
                    {"name": "limit",  "type": "int", "default": 8, "max": 52},
                ],
            },
            {
                "path": "/api/v1/gold-analysis",
                "method": "GET",
                "access": "free",
                "description": "Phân tích vàng mới nhất do AI tạo ra",
                "params": [],
            },
            {
                "path": "/api/v1/market-pulse",
                "method": "GET",
                "access": "premium_developer",
                "description": "Tin tức thị trường có điểm MRI (Market Risk Index). Dev: 50 bài",
                "params": [
                    {"name": "lang",  "type": "string", "options": ["vi", "en"], "default": "vi"},
                    {"name": "limit", "type": "int", "default": 10, "max": 50},
                ],
            },
        ],
    }
