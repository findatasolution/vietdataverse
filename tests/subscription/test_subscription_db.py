"""Real-DB tests for the money-moving half of the subscription service.

subscribe() / cancel_subscription() / has_active_subscription() all talk to
KNOWLEDGE_MARKET_DB directly (no repository layer, no mocked-DB fixture exists
in this project), so these run against the real Neon database — the same way
Tasks 1-4 were verified by hand, just automated. Everything is namespaced to a
throwaway user id + a throwaway product code and torn down in a finally block,
so a re-run leaves no garbage behind and nothing touches the real
'fuel-forecast-advanced' product or any real user's wallet.

Skipped (not failed) when KNOWLEDGE_MARKET_DB isn't set, so a laptop without
.env can still run the pure-logic suite.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

try:  # repo-root .env, same file be/main.py reads
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # pragma: no cover
    pass

pytestmark = pytest.mark.skipif(
    not os.getenv("KNOWLEDGE_MARKET_DB"),
    reason="KNOWLEDGE_MARKET_DB not set — real-DB subscription tests skipped",
)

# Distinct from every id used by this codebase's manual verification scripts.
TEST_USER_ID = 999999002
TEST_PRODUCT = "test-sub-fixture-999"
TEST_PRICE = 60
TEST_PERIOD_DAYS = 30


def _engine():
    from be.core.engines import get_engine_knowledge
    return get_engine_knowledge()


def _wipe(conn):
    """Remove every row this module could have created, child-first."""
    conn.execute(text("""
        DELETE FROM platform_subscription_events
        WHERE subscription_id IN (
            SELECT id FROM platform_subscriptions WHERE user_id = :u
        )
    """), {"u": TEST_USER_ID})
    conn.execute(text("DELETE FROM platform_subscriptions WHERE user_id = :u"), {"u": TEST_USER_ID})
    conn.execute(text("DELETE FROM credit_ledger WHERE user_id = :u"), {"u": TEST_USER_ID})
    conn.execute(text("DELETE FROM credit_balance WHERE user_id = :u"), {"u": TEST_USER_ID})
    conn.execute(text("DELETE FROM platform_products WHERE code = :c"), {"c": TEST_PRODUCT})


@pytest.fixture
def wallet():
    """Yields a setter: wallet(starting_balance) seeds the throwaway product +
    wallet. Always wipes both before and after, so a crashed previous run can't
    poison this one."""
    engine = _engine()

    with engine.begin() as conn:
        _wipe(conn)
        conn.execute(text("""
            INSERT INTO platform_products (code, name, price_credits, list_price_credits,
                                           billing_period_days, active)
            VALUES (:c, 'Test fixture product', :p, :p, :d, true)
        """), {"c": TEST_PRODUCT, "p": TEST_PRICE, "d": TEST_PERIOD_DAYS})

    def _set_balance(balance: int):
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO credit_balance (user_id, balance, updated_at)
                VALUES (:u, :b, NOW())
                ON CONFLICT (user_id) DO UPDATE SET balance = :b, updated_at = NOW()
            """), {"u": TEST_USER_ID, "b": balance})

    try:
        yield _set_balance
    finally:
        with engine.begin() as conn:
            _wipe(conn)


def _fetch_one(sql, **params):
    with _engine().connect() as conn:
        return conn.execute(text(sql), params).first()


# ── C1: expiry is part of the entitlement check ──────────────────────────────

class TestHasActiveSubscriptionExpiry:
    """Regression for the finding that has_active_subscription() checked only
    status, so a single payment granted permanent access once the billing cron
    stopped flipping rows to past_due."""

    def _insert_sub(self, status, period_end):
        with _engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO platform_subscriptions (user_id, product_code, status, current_period_end)
                VALUES (:u, :p, :s, :pe)
            """), {"u": TEST_USER_ID, "p": TEST_PRODUCT, "s": status, "pe": period_end})

    def test_active_but_expired_is_not_entitled(self, wallet):
        from be.services.subscription import has_active_subscription
        wallet(0)
        self._insert_sub("active", datetime.utcnow() - timedelta(days=1))
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is False

    def test_active_and_unexpired_is_entitled(self, wallet):
        from be.services.subscription import has_active_subscription
        wallet(0)
        self._insert_sub("active", datetime.utcnow() + timedelta(days=1))
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is True

    def test_past_due_is_never_entitled(self, wallet):
        from be.services.subscription import has_active_subscription
        wallet(0)
        self._insert_sub("past_due", datetime.utcnow() + timedelta(days=5))
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is False

    def test_no_subscription_at_all(self, wallet):
        from be.services.subscription import has_active_subscription
        wallet(0)
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is False


# ── I2: the money-moving paths ───────────────────────────────────────────────

class TestSubscribeDebitsWallet:
    def test_balance_ledger_and_subscription_all_written(self, wallet):
        from be.services.subscription import subscribe
        wallet(200)

        result = subscribe(TEST_USER_ID, TEST_PRODUCT)

        balance = _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u", u=TEST_USER_ID)[0]
        assert balance == 200 - TEST_PRICE
        assert result["balance_after"] == 200 - TEST_PRICE

        ledger = _fetch_one("""
            SELECT amount, kind, ref_type, ref_id FROM credit_ledger
            WHERE user_id = :u AND kind = 'subscription_charge'
        """, u=TEST_USER_ID)
        assert ledger is not None, "no subscription_charge ledger row was written"
        assert ledger[0] == -TEST_PRICE
        assert ledger[1] == "subscription_charge"
        assert (ledger[2], ledger[3]) == ("subscription", result["subscription_id"])

        sub = _fetch_one("""
            SELECT id, status, current_period_end FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)
        assert sub is not None
        assert sub[0] == result["subscription_id"]
        assert sub[1] == "active"
        assert sub[2] > datetime.utcnow()

        events = [r[0] for r in _engine().connect().execute(text("""
            SELECT event_type FROM platform_subscription_events
            WHERE subscription_id = :sid ORDER BY id
        """), {"sid": result["subscription_id"]}).fetchall()]
        assert events == ["created", "charged"]

    def test_subscribing_twice_is_rejected(self, wallet):
        from be.services.subscription import subscribe
        wallet(500)
        subscribe(TEST_USER_ID, TEST_PRODUCT)
        with pytest.raises(ValueError, match="Already subscribed"):
            subscribe(TEST_USER_ID, TEST_PRODUCT)
        # Only the first charge landed.
        n = _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u", u=TEST_USER_ID)[0]
        assert n == 1


class TestSubscribeRollback:
    """The invariant the review flagged as unverified: when the wallet can't
    cover the charge, the whole transaction must roll back — no orphan
    subscription row, no ledger row, no balance movement."""

    def test_insufficient_balance_leaves_nothing_behind(self, wallet):
        # NOTE: import from `services.credit`, not `be.services.credit`.
        # conftest.py puts both the repo root and be/ on sys.path, so the two
        # spellings load two *distinct* module objects with two distinct
        # InsufficientCredits classes. be/services/subscription.py does
        # `from services.credit import ...`, so that is the class it raises —
        # `be.services.credit.InsufficientCredits` would not catch it.
        from services.credit import InsufficientCredits
        from be.services.subscription import subscribe
        wallet(TEST_PRICE - 1)

        with pytest.raises(InsufficientCredits):
            subscribe(TEST_USER_ID, TEST_PRODUCT)

        subs = _fetch_one("""
            SELECT count(*) FROM platform_subscriptions WHERE user_id = :u
        """, u=TEST_USER_ID)[0]
        assert subs == 0, "a platform_subscriptions row survived a failed subscribe()"

        ledger = _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u", u=TEST_USER_ID)[0]
        assert ledger == 0, "a credit_ledger row survived a failed subscribe()"

        balance = _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u", u=TEST_USER_ID)[0]
        assert balance == TEST_PRICE - 1, "balance moved despite the failed charge"


def _events():
    with _engine().connect() as conn:
        return [r[0] for r in conn.execute(text("""
            SELECT e.event_type FROM platform_subscription_events e
            JOIN platform_subscriptions s ON s.id = e.subscription_id
            WHERE s.user_id = :u ORDER BY e.id
        """), {"u": TEST_USER_ID}).fetchall()]


def _force_period_end(period_end):
    """Backdate/advance the test subscription's period end without touching any
    other column — stands in for "time passed" in tests that need an expired or
    still-running period."""
    with _engine().begin() as conn:
        conn.execute(text("""
            UPDATE platform_subscriptions SET current_period_end = :pe
            WHERE user_id = :u AND product_code = :p
        """), {"pe": period_end, "u": TEST_USER_ID, "p": TEST_PRODUCT})


class TestCancelSubscription:
    """Cancelling is now scheduled, not immediate: the user keeps the period
    they already paid for, and run_billing_cycle expires the row when that
    period ends."""

    def test_cancel_schedules_without_touching_status_or_money(self, wallet):
        from be.services.subscription import (cancel_subscription, get_subscription,
                                              has_active_subscription, subscribe)
        wallet(200)
        sub_result = subscribe(TEST_USER_ID, TEST_PRODUCT)

        balance_before = _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u", u=TEST_USER_ID)[0]
        ledger_before = _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u", u=TEST_USER_ID)[0]

        result = cancel_subscription(TEST_USER_ID, TEST_PRODUCT)
        assert result["status"] == "active"
        assert result["cancel_at_period_end"] is True
        assert result["current_period_end"] == sub_result["current_period_end"]

        sub = _fetch_one("""
            SELECT status, cancelled_at, cancel_at_period_end, current_period_end
            FROM platform_subscriptions WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)
        assert sub[0] == "active", "cancel must not revoke access mid-period"
        assert sub[1] is None, "cancelled_at belongs to the moment it actually ends"
        assert sub[2] is True
        assert sub[3] == sub_result["current_period_end"]

        # Access is unaffected until the period end, and /me reports the flag.
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is True
        assert get_subscription(TEST_USER_ID, TEST_PRODUCT)["cancel_at_period_end"] is True

        # No money moved, in either direction (no refund, no charge).
        assert _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == balance_before
        assert _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == ledger_before

        # 'cancel_scheduled', never 'cancelled' — the subscription has not ended.
        assert _events() == ["created", "charged", "cancel_scheduled"]

    def test_cancel_twice_writes_one_event(self, wallet):
        from be.services.subscription import cancel_subscription, subscribe
        wallet(200)
        subscribe(TEST_USER_ID, TEST_PRODUCT)
        first = cancel_subscription(TEST_USER_ID, TEST_PRODUCT)
        assert cancel_subscription(TEST_USER_ID, TEST_PRODUCT) == first
        assert _events().count("cancel_scheduled") == 1

    def test_cancel_with_no_paid_period_left_cancels_immediately(self, wallet):
        """A lapsed row (period already over, cron never ran) has no access to
        preserve, so there is nothing to schedule — it cancels outright."""
        from be.services.subscription import cancel_subscription, subscribe
        wallet(200)
        subscribe(TEST_USER_ID, TEST_PRODUCT)
        _force_period_end(datetime.utcnow() - timedelta(days=1))

        result = cancel_subscription(TEST_USER_ID, TEST_PRODUCT)
        assert result["status"] == "cancelled"
        assert result["cancel_at_period_end"] is False

        sub = _fetch_one("""
            SELECT status, cancelled_at, cancel_at_period_end FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)
        assert sub[0] == "cancelled"
        assert sub[1] is not None
        assert sub[2] is False
        assert _events() == ["created", "charged", "cancelled"]

        # …and cancelling an already-cancelled row stays the old no-op.
        assert cancel_subscription(TEST_USER_ID, TEST_PRODUCT) == {"status": "cancelled"}
        assert _events().count("cancelled") == 1

    def test_cancel_without_subscription_raises(self, wallet):
        from be.services.subscription import cancel_subscription
        wallet(200)
        with pytest.raises(ValueError, match="No subscription found"):
            cancel_subscription(TEST_USER_ID, TEST_PRODUCT)


class TestSubscribeUndoesScheduledCancel:
    """POST /subscribe on a subscription that is scheduled to cancel means
    "keep it" — it must clear the flag and charge nothing, because the running
    period was already paid for."""

    def test_undo_clears_flag_without_charging(self, wallet):
        from be.services.subscription import cancel_subscription, subscribe
        wallet(200)
        first = subscribe(TEST_USER_ID, TEST_PRODUCT)
        cancel_subscription(TEST_USER_ID, TEST_PRODUCT)

        balance_before = _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u", u=TEST_USER_ID)[0]
        ledger_before = _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u", u=TEST_USER_ID)[0]

        result = subscribe(TEST_USER_ID, TEST_PRODUCT)
        assert result["charged"] is False
        assert result["cancel_at_period_end"] is False
        assert result["subscription_id"] == first["subscription_id"]
        # The period is untouched — undoing a cancellation is not a renewal.
        assert result["current_period_end"] == first["current_period_end"]

        sub = _fetch_one("""
            SELECT status, current_period_end, cancel_at_period_end
            FROM platform_subscriptions WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)
        assert sub[0] == "active"
        assert sub[1] == first["current_period_end"]
        assert sub[2] is False

        assert _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == balance_before, "undo must not charge"
        assert _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == ledger_before

        assert _events() == ["created", "charged", "cancel_scheduled", "cancel_undone"]

    def test_after_undo_a_further_subscribe_is_rejected_again(self, wallet):
        from be.services.subscription import cancel_subscription, subscribe
        wallet(200)
        subscribe(TEST_USER_ID, TEST_PRODUCT)
        cancel_subscription(TEST_USER_ID, TEST_PRODUCT)
        subscribe(TEST_USER_ID, TEST_PRODUCT)  # undo
        with pytest.raises(ValueError, match="Already subscribed"):
            subscribe(TEST_USER_ID, TEST_PRODUCT)


class TestSubscribeOnExpiredActiveRow:
    """The dead end this change fixes: with no cron having run, an unpaid row
    still reads status='active' while has_active_subscription() (correctly)
    denies access. subscribe() used to reject it as "Already subscribed", so
    the user could neither use nor re-buy the product."""

    def test_expired_active_row_is_reactivatable(self, wallet):
        from be.services.subscription import has_active_subscription, subscribe
        wallet(200)
        first = subscribe(TEST_USER_ID, TEST_PRODUCT)
        _force_period_end(datetime.utcnow() - timedelta(days=1))
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is False

        result = subscribe(TEST_USER_ID, TEST_PRODUCT)

        assert result["charged"] is True
        assert result["subscription_id"] == first["subscription_id"], "reuses the row"
        assert result["balance_after"] == 200 - 2 * TEST_PRICE
        # A late reactivation buys a fresh period from now, it does not backdate.
        assert result["current_period_end"] > datetime.utcnow() + timedelta(days=TEST_PERIOD_DAYS - 1)
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is True

        assert _fetch_one("SELECT balance FROM credit_balance WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == 200 - 2 * TEST_PRICE
        assert _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == 2
        assert _events() == ["created", "charged", "reactivated"]

    def test_expired_active_row_with_cancel_scheduled_also_reactivates(self, wallet):
        """Same path regardless of the flag — and the fresh paid period must not
        inherit the stale cancellation."""
        from be.services.subscription import cancel_subscription, subscribe
        wallet(200)
        subscribe(TEST_USER_ID, TEST_PRODUCT)
        cancel_subscription(TEST_USER_ID, TEST_PRODUCT)  # schedules, period still running
        _force_period_end(datetime.utcnow() - timedelta(days=1))

        result = subscribe(TEST_USER_ID, TEST_PRODUCT)
        assert result["charged"] is True
        assert result["cancel_at_period_end"] is False
        assert _fetch_one("""
            SELECT cancel_at_period_end FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)[0] is False

    def test_past_due_row_reactivates_and_clears_a_stale_cancel_flag(self, wallet):
        """A user who scheduled a cancel, then fell past_due, then pays again is
        buying a fresh period — it must not carry the old cancellation."""
        from be.services.subscription import has_active_subscription, subscribe
        wallet(200)
        with _engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO platform_subscriptions (user_id, product_code, status,
                                                    current_period_end, grace_until,
                                                    cancel_at_period_end)
                VALUES (:u, :p, 'past_due', :pe, :g, true)
            """), {"u": TEST_USER_ID, "p": TEST_PRODUCT,
                   "pe": datetime.utcnow() - timedelta(days=1),
                   "g": datetime.utcnow() + timedelta(days=1)})

        result = subscribe(TEST_USER_ID, TEST_PRODUCT)
        assert result["charged"] is True
        assert result["cancel_at_period_end"] is False
        assert has_active_subscription(TEST_USER_ID, TEST_PRODUCT) is True

        sub = _fetch_one("""
            SELECT status, grace_until, cancel_at_period_end FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p
        """, u=TEST_USER_ID, p=TEST_PRODUCT)
        assert sub[0] == "active"
        assert sub[1] is None, "grace_until must be cleared on reactivation"
        assert sub[2] is False
        assert _events() == ["reactivated"]

    def test_expired_active_row_with_empty_wallet_still_refuses(self, wallet):
        """Reactivation is a real purchase — it must fail on 402, not silently
        extend the period for free."""
        from services.credit import InsufficientCredits
        from be.services.subscription import subscribe
        wallet(TEST_PRICE)
        subscribe(TEST_USER_ID, TEST_PRODUCT)  # spends the whole wallet
        _force_period_end(datetime.utcnow() - timedelta(days=1))

        with pytest.raises(InsufficientCredits):
            subscribe(TEST_USER_ID, TEST_PRODUCT)
        assert _fetch_one("SELECT count(*) FROM credit_ledger WHERE user_id = :u",
                          u=TEST_USER_ID)[0] == 1


# ── I5: billing-history timestamps carry an explicit UTC marker ──────────────

class TestHistoryTimestampFormat:
    def test_created_at_is_iso8601_utc(self, wallet):
        from be.services.subscription import list_subscription_history, subscribe
        wallet(200)
        subscribe(TEST_USER_ID, TEST_PRODUCT)

        history = list_subscription_history(TEST_USER_ID)
        assert history, "subscribe() should have produced history events"
        for row in history:
            ts = row["created_at"]
            assert isinstance(ts, str)
            assert ts.endswith("Z"), f"missing UTC marker: {ts!r}"
            assert "T" in ts, f"not ISO-8601 (space-separated): {ts!r}"
            # Parses back to the same instant — proves it's a real ISO string,
            # not just a string with a Z stapled on.
            datetime.fromisoformat(ts[:-1])
