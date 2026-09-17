"""Identity resolution: token subject -> canonical users row.

In-memory SQLite stands in for USER_DB; the SQL is plain enough to run on both.
"""
import pytest
from sqlalchemy import create_engine, text

from be.services import identity
from be.services.identity import resolve_identity

ADMIN_SUB = "auth0|6982ec517d02ef45fb90bb50"
GOOGLE_SUB = "google-oauth2|118331541548289551436"


@pytest.fixture(autouse=True)
def _clear_negative_cache():
    identity.reset_negative_cache()
    yield
    identity.reset_negative_cache()


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.connect() as c:
        c.execute(text("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                auth0_id TEXT UNIQUE, user_level TEXT NOT NULL DEFAULT 'free',
                is_admin BOOLEAN NOT NULL DEFAULT 0, current_plan TEXT,
                email_verified BOOLEAN NOT NULL DEFAULT 0)
        """))
        c.execute(text("""
            CREATE TABLE user_identities (
                auth0_sub TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
                linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
        """))
        c.execute(text("""
            INSERT INTO users (user_id, email, auth0_id, user_level, is_admin) VALUES
              (1, 'admin@example.com', :admin, 'admin', 1),
              (2, 'guest@example.com', NULL, 'premium', 0)
        """), {"admin": ADMIN_SUB})
        c.commit()
        yield c


class Userinfo:
    """Stands in for Auth0 /userinfo; records how often it was consulted."""
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, 0

    def __call__(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.payload


def test_known_subject_resolves_without_calling_auth0(conn):
    userinfo = Userinfo()
    user = resolve_identity(conn, ADMIN_SUB, userinfo)
    assert (user.user_id, user.auth0_id, user.is_admin) == (1, ADMIN_SUB, True)
    assert userinfo.calls == 0


def test_linked_identity_resolves_to_canonical_account(conn):
    conn.execute(text("INSERT INTO user_identities (auth0_sub, user_id) VALUES (:s, 1)"), {"s": GOOGLE_SUB})
    userinfo = Userinfo()
    user = resolve_identity(conn, GOOGLE_SUB, userinfo)
    assert user.user_id == 1
    assert user.auth0_id == ADMIN_SUB  # routers query users by this, so it must be the canonical id
    assert userinfo.calls == 0


def test_verified_login_claims_unlinked_account_with_same_email(conn):
    userinfo = Userinfo({"sub": GOOGLE_SUB, "email": "guest@example.com", "email_verified": True})
    user = resolve_identity(conn, GOOGLE_SUB, userinfo)
    assert (user.user_id, user.auth0_id, user.user_level) == (2, GOOGLE_SUB, "premium")
    assert conn.execute(text("SELECT auth0_id FROM users WHERE user_id = 2")).scalar() == GOOGLE_SUB


def test_unverified_email_never_claims_an_account(conn):
    userinfo = Userinfo({"sub": GOOGLE_SUB, "email": "guest@example.com", "email_verified": False})
    assert resolve_identity(conn, GOOGLE_SUB, userinfo) is None
    assert conn.execute(text("SELECT auth0_id FROM users WHERE user_id = 2")).scalar() is None


def test_verified_email_does_not_merge_into_account_owned_by_another_identity(conn):
    # Account pre-hijacking guard: whoever registered admin@example.com first may
    # never have proven they own it, so a later verified login must not join them.
    userinfo = Userinfo({"sub": GOOGLE_SUB, "email": "admin@example.com", "email_verified": True})
    assert resolve_identity(conn, GOOGLE_SUB, userinfo) is None
    assert conn.execute(text("SELECT count(*) FROM user_identities")).scalar() == 0


def test_userinfo_for_a_different_subject_is_rejected(conn):
    userinfo = Userinfo({"sub": "google-oauth2|someone-else", "email": "guest@example.com", "email_verified": True})
    assert resolve_identity(conn, GOOGLE_SUB, userinfo) is None


def test_unresolvable_subject_is_not_rechecked_until_cache_expires(conn):
    clock = [1000.0]
    userinfo = Userinfo({"sub": GOOGLE_SUB, "email": "nobody@example.com", "email_verified": True})
    assert resolve_identity(conn, GOOGLE_SUB, userinfo, now=lambda: clock[0]) is None
    assert resolve_identity(conn, GOOGLE_SUB, userinfo, now=lambda: clock[0]) is None
    assert userinfo.calls == 1
    clock[0] += identity.NEGATIVE_CACHE_SECONDS + 1
    resolve_identity(conn, GOOGLE_SUB, userinfo, now=lambda: clock[0])
    assert userinfo.calls == 2


def test_auth0_outage_resolves_to_anonymous_instead_of_raising(conn):
    userinfo = Userinfo(error=OSError("auth0 unreachable"))
    assert resolve_identity(conn, GOOGLE_SUB, userinfo) is None
