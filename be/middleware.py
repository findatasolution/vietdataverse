import asyncio
from datetime import datetime

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy import text

from auth import verify_auth0_token, get_user_level, get_user_is_admin, NAMESPACE
from quota import check_and_consume


async def _log_api_call(user_id: int, key_id: int, endpoint: str, status_code: int):
    """Fire-and-forget: insert into api_call_log for top-endpoint dashboard stats."""
    try:
        from core.engines import get_engine_user
        with get_engine_user().begin() as conn:
            conn.execute(text("""
                INSERT INTO api_call_log (user_id, api_key_id, endpoint, status_code)
                VALUES (:uid, :kid, :ep, :sc)
            """), {"uid": user_id, "kid": key_id, "ep": endpoint, "sc": status_code})
    except Exception:
        pass  # logging failure must never break the request


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

        # 2. Subscription expiry check — commit deactivation in its own txn
        #    then raise (raise cannot rollback a committed txn).
        if not is_admin and premium_expiry is not None and premium_expiry < datetime.now():
            with engine.begin() as conn:
                conn.execute(text(
                    "UPDATE api_keys SET is_active = FALSE WHERE user_id = :uid"
                ), {"uid": user_id})
            raise HTTPException(
                status_code=402,
                detail=(
                    "Subscription đã hết hạn. Vui lòng gia hạn tại "
                    "/pages/pricing.html — API key sẽ tự động active lại."
                ),
            )

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
                        detail="Tài khoản không có quyền truy cập API. Cần gói Premium Developer.",
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
        request.state.user = {
            "auth0_id":    auth0_id,
            "email":       email,
            "user_level":  user_level,
            "is_admin":    bool(is_admin),
            "user_id":     user_id,
            "api_key_id":  key_id,
            "auth_method": "api_key",
        }
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


async def authenticate_user(request: Request):
    """
    Authenticate via X-API-Key header (Dev API key) or Auth0 Bearer token.
    Skips public endpoints.
    """
    public_endpoints = [
        "/api/docs", "/api/openapi.json",
        "/api/v1/gold", "/api/v1/silver", "/api/v1/sbv-interbank",
        "/api/v1/termdepo", "/api/v1/global-macro", "/api/v1/gold/types",
        "/api/v1/termdepo/banks", "/api/v1/gold-analysis",
        "/api/v1/vn30-scores/meta",
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
        # DB is always authoritative)
        from core.engines import get_engine_user
        from sqlalchemy import text as _text
        user_level = "free"
        is_admin   = False
        with get_engine_user().connect() as conn:
            row = conn.execute(
                _text("SELECT user_level, is_admin FROM users WHERE auth0_id = :aid"),
                {"aid": auth0_id},
            ).fetchone()
            if row:
                user_level = row[0]
                is_admin   = bool(row[1])
            elif email:
                # Fallback: pre-existing anonymous user not yet linked
                row = conn.execute(
                    _text("SELECT user_level, is_admin FROM users WHERE email = :em"),
                    {"em": email},
                ).fetchone()
                if row:
                    user_level = row[0]
                    is_admin   = bool(row[1])

        request.state.user = {
            "auth0_id":   auth0_id,
            "email":      email,
            "user_level": user_level,
            "is_admin":   is_admin,
        }
        return payload
    except JWTError:
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

        # Look up user_level from DB — try auth0_id first, fall back to email
        from core.engines import get_engine_user
        from sqlalchemy import text as _text
        with get_engine_user().connect() as conn:
            row = conn.execute(
                _text("SELECT user_id, user_level, is_admin, auth0_id FROM users WHERE auth0_id = :aid"),
                {"aid": auth0_id},
            ).fetchone()

            if not row and email:
                # Pre-existing user (anonymous/internal) — link auth0_id on the fly
                row = conn.execute(
                    _text("SELECT user_id, user_level, is_admin, auth0_id FROM users WHERE email = :em"),
                    {"em": email},
                ).fetchone()
                if row and row[3] is None:
                    # auth0_id not yet set — link it now
                    conn.execute(
                        _text("UPDATE users SET auth0_id = :aid WHERE user_id = :uid"),
                        {"aid": auth0_id, "uid": row[0]},
                    )
                    conn.commit()

        user_level = row[1] if row else "free"
        is_admin   = bool(row[2]) if row else False

        request.state.user = {
            "auth0_id":   auth0_id,
            "email":      email,
            "user_level": user_level,
            "is_admin":   is_admin,
        }
    except Exception:
        pass  # invalid token → treat as anonymous

    return None


def get_current_user(request: Request):
    """Helper to get current user from request state"""
    if not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user
