from fastapi import Request, HTTPException
from jose import JWTError
from sqlalchemy import text

from auth import verify_auth0_token, get_user_level, get_user_is_admin, NAMESPACE

FREE_API_LIMIT = 5  # lifetime requests for free accounts using API key


async def _auth_via_api_key(request: Request, api_key: str) -> bool:
    """
    Look up X-API-Key in api_keys table.
    Sets request.state.user and enforces free-tier quota.
    Returns True if key is valid, raises HTTPException on quota exceeded.
    """
    try:
        from core.engines import get_engine_user
        with get_engine_user().connect() as conn:
            row = conn.execute(text("""
                SELECT u.user_id, u.email, u.auth0_id, u.user_level,
                       u.is_admin, u.api_request_count
                FROM api_keys ak
                JOIN users u ON ak.user_id = u.user_id
                WHERE ak.key_value = :key AND ak.is_active = TRUE
                LIMIT 1
            """), {"key": api_key}).fetchone()

            if not row:
                return False

            user_id, email, auth0_id, user_level, is_admin, req_count = row

            # Free-tier quota check
            if user_level == "free":
                if req_count >= FREE_API_LIMIT:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Đã đạt giới hạn {FREE_API_LIMIT} request/account. "
                               "Nâng cấp lên Premium Developer để tiếp tục.",
                    )
                conn.execute(text("""
                    UPDATE users SET api_request_count = api_request_count + 1
                    WHERE user_id = :uid
                """), {"uid": user_id})

            # Update last_used_at
            conn.execute(text("""
                UPDATE api_keys SET last_used_at = NOW()
                WHERE key_value = :key
            """), {"key": api_key})
            conn.commit()

        request.state.user = {
            "auth0_id":   auth0_id,
            "email":      email,
            "user_level": user_level,
            "is_admin":   bool(is_admin),
            "user_id":    user_id,
            "auth_method": "api_key",
        }
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
    except Exception:
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
