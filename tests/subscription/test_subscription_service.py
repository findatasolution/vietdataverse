"""Pure-logic tests for the subscription billing state machine — no DB."""
from datetime import datetime, timedelta
import pytest
from be.services.subscription import _decide_renewal


def _dt(days_from_now, now):
    return now + timedelta(days=days_from_now)


class TestDecideRenewalActive:
    def test_active_not_due_is_noop(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(5, now), grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
        )
        assert result == {"action": "noop"}

    def test_active_due_sufficient_balance_charges_from_anchor(self):
        now = datetime(2026, 9, 10)
        period_end = _dt(-1, now)  # due yesterday
        result = _decide_renewal(
            status="active", current_period_end=period_end, grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
        )
        assert result["action"] == "charge"
        assert result["new_status"] == "active"
        assert result["new_period_end"] == period_end + timedelta(days=30)
        assert result["event"] == "charged"

    def test_active_due_insufficient_balance_marks_past_due(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(-1, now), grace_until=None,
            balance=10, price=60, billing_period_days=30, now=now,
        )
        assert result["action"] == "mark_past_due"
        assert result["grace_until"] == now + timedelta(days=3)
        assert result["event"] == "charge_failed"


class TestDecideRenewalPastDue:
    def test_past_due_sufficient_balance_reactivates_from_now(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-5, now), grace_until=_dt(1, now),
            balance=100, price=60, billing_period_days=30, now=now,
        )
        assert result["action"] == "charge"
        assert result["new_status"] == "active"
        assert result["new_period_end"] == now + timedelta(days=30)
        assert result["event"] == "reactivated"

    def test_past_due_within_grace_still_short_is_noop(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-1, now), grace_until=_dt(1, now),
            balance=10, price=60, billing_period_days=30, now=now,
        )
        assert result == {"action": "noop"}

    def test_past_due_grace_expired_cancels(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-4, now), grace_until=_dt(-1, now),
            balance=10, price=60, billing_period_days=30, now=now,
        )
        assert result["action"] == "cancel"
        assert result["event"] == "cancelled"
        assert "grace" in result["note"].lower()


class TestDecideRenewalCancelled:
    def test_cancelled_is_always_noop(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="cancelled", current_period_end=_dt(-100, now), grace_until=None,
            balance=1000, price=60, billing_period_days=30, now=now,
        )
        assert result == {"action": "noop"}
