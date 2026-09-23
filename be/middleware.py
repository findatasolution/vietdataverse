import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy import text

from auth import verify_auth0_token, get_user_level, get_user_is_admin, NAMESPACE, AUTH0_DOMAIN
from quota import check_and_consume
from services.identity import resolve_identity

logger = logging.getLogger(__name__)


def _userinfo_fetcher(token: str):
    """Deferred Auth0 /userinfo call — only made for a subject not yet known to users."""
    def fetch() -> dict:
        import requests
        resp = requests.get(f"https://{AUTH0_DOMAIN}/userinfo",
                            headers={"Authorization": f"Bearer {token}"}, timeout=5)
        resp.raise_for_status()
        return resp.json()
    return fetch


async def _log_api_call(
    user_id: Optional[int],
    key_id: Optional[int],
    endpoint: str,
    status_code: int,
):
    """Fire-and-forget: insert into api_call_log for top-endpoint dashboard stats."""
    try:
        from core.engines import get_engine_user
        with get_engine_user().begin() as conn:
            conn.execute(text("""
                INSERT INTO api_call_log (user_id, api_key_id, endpoint, status_code)
                VALUES (:uid, :kid, :ep, :sc)
            """), {"uid": user_id, "kid": key_id, "ep": endpoint, "sc": status_code})
    except Exception:
        # A failed write must never break the request — but it must not be
        # invisible either. A bare `pass` here hid a NotNullViolation on
        # api_call_log.user_id for months (migration 019): every anonymous call
        # failed to log, so the admin dashboard's "Public anonymous" and
        # "Anonymous / lỗi" columns read 0 and looked like "nobody is calling"
        # instead of "nothing is being recorded". exc_info so the next such
        # failure names itself in the container log.
        logger.warning("api_call_log write failed for %s (status %s)",
                       endpoint, status_code, exc_info=True)


async def _auth_via_api_key(request: Request, api_key: str) -> bool:
    """
    Look up X-API-Key, enforce subscription expiry + tier-based quota.

    Flow:
      1. Join api_keys + users, require is_active=TRUE.
      2. Nếu premium_expiry < NOW() → set is_active=FALSE, raise 402.
      3. Gọi quota.check_and_consume:
         - no_access → 403
         - burst cạn → 429 (Retry-After: 1)
         - monthly cạn → 429 với reset_at = đầu tháng sau
         - OK → set request.state.user và return True.

    Rate-limit headers (X-RateLimit-*) được attach vào response trong
    authenticate_user() wrapper.
    """
    from core.engines import get_engine_user
    engine = get_engine_user()
    try:
        # 1. Lookup key + user — read-only
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT ak.key_id, u.user_id, u.email, u.auth0_id, u.user_level,
                       u.is_admin, u.premium_expiry, u.current_plan
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.user_id
                WHERE ak.key_value = :key AND ak.is_active = TRUE
                LIMIT 1
            """), {"key": api_key}).fetchone()

        if not row:
            return False

        (key_id, user_id, email, auth0_id, user_level, is_admin,
         premium_expiry, current_plan) = row

        # Set identity before quota enforcement so rejected requests from a
        # known key can still be attributed in api_call_log.
        request.state.user = {
            "auth0_id":    auth0_id,
            "email":       email,
            "user_level":  user_level,
            "is_admin":    bool(is_admin),
            "user_id":     user_id,
            "api_key_id":  key_id,
            "auth_method": "api_key",
        }

        # 2. Subscription hết hạn → KHÔNG khoá cứng. Hạ về free tier
        #    (1.000 req/tháng) thay vì 402, để user từng trả phí không bị
        #    thiệt hơn user free thuần. Key vẫn giữ active; user nâng cấp
        #    lại để lấy quota cao hơn (dev_monthly/dev_yearly).
        if not is_admin and premium_expiry is not None and premium_expiry < datetime.now():
            user_level   = "free"
            current_plan = None

        # 3. Quota + burst check + atomic increment — new txn
        with engine.begin() as conn:
            q = check_and_consume(
                conn,
                user_id=user_id,
                user_level=user_level,
                plan=current_plan,
            )

            if not q.allowed:
                reset_iso = q.reset_at.isoformat()
                if q.reason == "no_access":
                    raise HTTPException(
                        status_code=403,
                        detail="Tài khoản không có quyền truy cập API. Cần gói API Supper Lite trở lên.",
                    )
                if q.reason == "burst":
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit burst {q.burst_per_sec} req/s. Thử lại sau 1 giây.",
                        headers={
                            "Retry-After": "1",
                            "X-RateLimit-Limit":     str(q.monthly_limit or 0),
                            "X-RateLimit-Remaining": str(q.remaining if q.remaining is not None else ""),
                            "X-RateLimit-Reset":     reset_iso,
                        },
                    )
                # monthly cạn
                raise HTTPException(
                    status_code=429,
                    detail=(
                        f"Hết quota tháng ({q.monthly_limit} req). "
                        f"Reset vào {reset_iso} (giờ VN)."
                    ),
                    headers={
                        "X-RateLimit-Limit":     str(q.monthly_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset":     reset_iso,
                    },
                )

            # Happy path — tăng api_request_count (cumulative cho analytics)
            # và update last_used_at
            conn.execute(text("""
                UPDATE api_keys SET last_used_at = NOW()
                WHERE key_id = :kid
            """), {"kid": key_id})
            conn.execute(text("""
                UPDATE users SET api_request_count = api_request_count + 1
                WHERE user_id = :uid
            """), {"uid": user_id})

        # Stash quota info trên request.state cho response headers + logging
        request.state.quota = {
            "limit":     q.monthly_limit,
            "remaining": q.remaining,
            "reset":     q.reset_at.isoformat(),
        }

        # Fire-and-forget log (200 assumed; actual status logged at route level if needed)
        asyncio.ensure_future(_log_api_call(user_id, key_id, request.url.path, 200))
        return True
    except HTTPException:
        raise
    except Exception:
        return False


def _raise_quota_exceeded(q):
    """Map QuotaResult(allowed=False) → HTTPException — dùng chung cho cả 2 đường auth."""
    reset_iso = q.reset_at.isoformat()
    if q.reason == "no_access":
        raise HTTPException(status_code=403, detail="Tài khoản không có quyền truy cập API.")
    if q.reason == "burst":
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit burst {q.burst_per_sec} req/s. Thử lại sau 1 giây.",
            headers={"Retry-After": "1",
                     "X-RateLimit-Limit": str(q.monthly_limit or 0),
                     "X-RateLimit-Reset": reset_iso},
        )
    raise HTTPException(
        status_code=429,
        detail=f"Hết quota tháng ({q.monthly_limit} req). Reset vào {reset_iso} (giờ VN).",
        headers={"X-RateLimit-Limit": str(q.monthly_limit),
                 "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": reset_iso},
    )


async def _auth_via_bearer(request: Request, token: str) -> bool:
    """
    Meter một request mang Auth0 Bearer token (FE đã đăng nhập: download, chart
    cần dữ liệu live). Resolve user_id + tier từ DB rồi áp cùng quota/log như
    đường API key. Không có expiry-deactivation (đó là logic riêng của API key).
    Trả False nếu token không hợp lệ hoặc user chưa provision; raise khi cạn quota.
    """
    from core.engines import get_engine_user
    from auth import verify_auth0_token, NAMESPACE

    try:
        payload  = verify_auth0_token(token)
        auth0_id = payload.get("sub")
        email    = payload.get(f"{NAMESPACE}/email") or payload.get("email", "")
    except Exception:
        return False
    if not auth0_id:
        return False

    engine = get_engine_user()
    try:
        with engine.connect() as conn:
            resolved = resolve_identity(conn, auth0_id, _userinfo_fetcher(token))
        if not resolved:
            return False  # chưa có dòng user → /me sẽ tạo; tạm coi như chưa đo được

        user_id, user_level, current_plan = resolved.user_id, resolved.user_level, resolved.current_plan

        # Preserve the resolved identity even when quota enforcement rejects
        # the call, allowing the meter gate to log a known user instead of an
        # anonymous failure.
        request.state.user = {
            "auth0_id": resolved.auth0_id, "email": resolved.email or email,
            "user_level": user_level, "is_admin": resolved.is_admin,
            "user_id": user_id, "auth_method": "bearer",
        }

        with engine.begin() as conn:
            q = check_and_consume(conn, user_id=user_id,
                                  user_level=user_level, plan=current_plan)
            if not q.allowed:
                _raise_quota_exceeded(q)
            conn.execute(text("""
                UPDATE users SET api_request_count = api_request_count + 1
                WHERE user_id = :uid
            """), {"uid": user_id})

        request.state.quota = {
            "limit": q.monthly_limit, "remaining": q.remaining,
            "reset": q.reset_at.isoformat(),
        }
        asyncio.ensure_future(_log_api_call(user_id, None, request.url.path, 200))
        return True
    except HTTPException:
        raise
    except Exception:
        return False


async def authenticate_user(request: Request):
    """
    Authenticate via X-API-Key header (Dev API key) or Auth0 Bearer token.
    Skips public endpoints.
    """
    public_endpoints = [
        "/docs", "/openapi.json", "/redoc",
        "/api/v1/gold", "/api/v1/silver", "/api/v1/sbv-interbank",
        "/api/v1/termdepo", "/api/v1/global-macro", "/api/v1/gold/types",
        "/api/v1/termdepo/banks", "/api/v1/gold-analysis",
    ]

    if request.url.path in public_endpoints:
        return None

    # ── X-API-Key ────────────────────────────────────────────────────
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if await _auth_via_api_key(request, api_key):
            return request.state.user
        raise HTTPException(status_code=401, detail="API key không hợp lệ hoặc đã bị thu hồi")

    # ── Bearer token (Auth0) ─────────────────────────────────────────
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.split(" ")[1]
    try:
        payload  = verify_auth0_token(token)
        auth0_id = payload.get("sub")
        email    = payload.get(f"{NAMESPACE}/email") or payload.get("email", "")

        # Read user_level from DB (JWT custom claims require Auth0 Action to be set up;
        # DB is always authoritative). Never trust the token's email claim to pick
        # the row: it is not proof of ownership (see services/identity.py).
        from core.engines import get_engine_user
        with get_engine_user().connect() as conn:
            resolved = resolve_identity(conn, auth0_id, _userinfo_fetcher(token))

        request.state.user = {
            "auth0_id":   resolved.auth0_id if resolved else auth0_id,
            "email":      email,
            "user_level": resolved.user_level if resolved else "free",
            "is_admin":   resolved.is_admin if resolved else False,
            "user_id":    resolved.user_id if resolved else None,
            "auth_method": "bearer",
        }
        return payload
    except JWTError as jwt_err:
        print(f"[authenticate_user] JWT verify failed: {type(jwt_err).__name__}: {jwt_err}")
        # Print token info (first/last 20 chars only) for debugging
        if token:
            print(f"  Token prefix: {token[:20]}...{token[-20:] if len(token) > 40 else ''}")
            print(f"  Token length: {len(token)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[authenticate_user] JWT path error: {type(e).__name__}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Authentication error")


async def authenticate_user_optional(request: Request):
    """
    Like authenticate_user but never raises 401.
    If no/invalid auth header → request.state.user stays unset (anonymous).
    Reads user_level from DB (not from JWT claims) for accuracy.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None  # anonymous — no error

    token = auth_header.split(" ")[1]
    try:
        from auth import verify_auth0_token, NAMESPACE
        payload = verify_auth0_token(token)
        auth0_id = payload.get("sub")
        email    = payload.get(f"{NAMESPACE}/email") or payload.get("email", "")

        from core.engines import get_engine_user
        with get_engine_user().connect() as conn:
            resolved = resolve_identity(conn, auth0_id, _userinfo_fetcher(token))

        request.state.user = {
            "auth0_id":   resolved.auth0_id if resolved else auth0_id,
            "email":      email,
            "user_level": resolved.user_level if resolved else "free",
            "is_admin":   resolved.is_admin if resolved else False,
            "user_id":    resolved.user_id if resolved else None,
        }
    except Exception:
        pass  # invalid token → treat as anonymous

    return None


def get_current_user(request: Request):
    """Helper to get current user from request state"""
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user
