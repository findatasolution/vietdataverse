"""A brand-new users row must never be created with a blank email.

Regression for the 2026-06-30 → 2026-09-25 defect: an Auth0 access token has an
`email` claim only when the Action adding it is installed. /auth/me read the
missing claim as "" and inserted it. users.email is UNIQUE, so the first blank
row inserted fine and every later identity collided with it — a permanent 500
from /me, which the frontend rendered as "Vui lòng đăng nhập" to people who
were already signed in.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "be"))

from routers.auth_routes import (  # noqa: E402
    PLACEHOLDER_EMAIL_DOMAIN,
    is_placeholder_email,
    resolve_signup_email,
)


def test_present_claim_is_used_without_calling_userinfo():
    calls = []

    def fetch():
        calls.append(1)
        return "other@example.com"

    assert resolve_signup_email("person@example.com", fetch) == "person@example.com"
    assert calls == [], "a present claim must not cost an Auth0 round-trip"


@pytest.mark.parametrize("claim", [None, "", "   "])
def test_missing_claim_falls_back_to_userinfo(claim):
    assert resolve_signup_email(claim, lambda: "person@example.com") == "person@example.com"


@pytest.mark.parametrize("claim", [None, "", "   "])
@pytest.mark.parametrize("userinfo", [None, "", "   "])
def test_blank_everywhere_yields_blank_so_the_caller_refuses(claim, userinfo):
    # The route turns "" into a 400. What must never happen is a blank reaching
    # the INSERT, which is what poisoned the UNIQUE index for three months.
    assert resolve_signup_email(claim, lambda: userinfo) == ""


def test_userinfo_failure_is_not_swallowed_into_a_blank_insert():
    def fetch():
        raise RuntimeError("Auth0 unreachable")

    with pytest.raises(RuntimeError):
        resolve_signup_email("", fetch)


def test_claim_and_userinfo_values_are_trimmed():
    assert resolve_signup_email("  person@example.com  ", lambda: "") == "person@example.com"
    assert resolve_signup_email("", lambda: "  person@example.com  ") == "person@example.com"


def test_placeholder_detection_matches_migration_020():
    assert is_placeholder_email(f"unknown-10{PLACEHOLDER_EMAIL_DOMAIN}")
    assert not is_placeholder_email("person@example.com")
    assert not is_placeholder_email("")
    assert not is_placeholder_email(None)
