"""Resolve an Auth0 token subject to its canonical users row.

One person can reach Auth0 through several identities (email/password
`auth0|...`, Google `google-oauth2|...`) with the same email, but users.email
and users.auth0_id are both unique, so only one identity can sit on the row.
Every router looks users up by `auth0_id`, so the middleware resolves the
token's subject here and hands routers the row's own auth0_id.

Resolution order:
  1. users.auth0_id == sub
  2. user_identities.auth0_sub == sub (extra identities of an existing account)
  3. an account with no identity yet (e.g. created by guest checkout) whose
     email Auth0 reports as *verified* for this identity -> claim it.

Nothing ever merges into an account that already has an identity: whoever
registered that email first may not have proven they own it (account
pre-hijacking). Those links are made by an admin inserting into user_identities.
"""
import time
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import text

NEGATIVE_CACHE_SECONDS = 300
_unresolvable_until: dict[str, float] = {}

_USER_COLUMNS = "u.user_id, u.auth0_id, u.email, u.user_level, u.is_admin, u.current_plan"


@dataclass(frozen=True)
class ResolvedUser:
    user_id: int
    auth0_id: str
    email: str
    user_level: str
    is_admin: bool
    current_plan: Optional[str]


def reset_negative_cache() -> None:
    _unresolvable_until.clear()


def _row_to_user(row) -> ResolvedUser:
    return ResolvedUser(row[0], row[1], row[2], row[3], bool(row[4]), row[5])


def resolve_identity(conn, sub: str, fetch_userinfo: Callable[[], dict],
                     now: Callable[[], float] = time.monotonic) -> Optional[ResolvedUser]:
    if not sub:
        return None

    row = conn.execute(text(f"SELECT {_USER_COLUMNS} FROM users u WHERE u.auth0_id = :sub"),
                       {"sub": sub}).fetchone()
    if row:
        return _row_to_user(row)

    row = conn.execute(text(f"""
        SELECT {_USER_COLUMNS} FROM user_identities i
        JOIN users u ON u.user_id = i.user_id
        WHERE i.auth0_sub = :sub
    """), {"sub": sub}).fetchone()
    if row:
        return _row_to_user(row)

    # Auth0 rate-limits /userinfo; a brand-new user who has no row yet would
    # otherwise trigger a call on every request until /auth/me creates one.
    if _unresolvable_until.get(sub, 0) > now():
        return None

    try:
        info = fetch_userinfo() or {}
    except Exception:
        info = {}
    email = (info.get("email") or "").strip()
    if info.get("sub") != sub or not email or info.get("email_verified") is not True:
        _unresolvable_until[sub] = now() + NEGATIVE_CACHE_SECONDS
        return None

    row = conn.execute(text(f"SELECT {_USER_COLUMNS} FROM users u WHERE u.email = :email AND u.auth0_id IS NULL"),
                       {"email": email}).fetchone()
    if not row:
        _unresolvable_until[sub] = now() + NEGATIVE_CACHE_SECONDS
        return None

    claimed = conn.execute(text("""
        UPDATE users SET auth0_id = :sub, email_verified = true
        WHERE user_id = :uid AND auth0_id IS NULL
    """), {"sub": sub, "uid": row[0]})
    conn.commit()
    if claimed.rowcount != 1:  # another request claimed it first
        return None
    user = _row_to_user(row)
    return ResolvedUser(user.user_id, sub, user.email, user.user_level, user.is_admin, user.current_plan)
