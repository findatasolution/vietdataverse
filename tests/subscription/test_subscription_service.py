"""Pure-logic tests for the subscription billing state machine — no DB."""
from datetime import datetime, timedelta
from be.services.subscription import _decide_renewal


def _dt(days_from_now, now):
    return now + timedelta(days=days_from_now)


class TestDecideRenewalActive:
    def test_active_not_due_is_noop(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(5, now), grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=False,
        )
        assert result == {"action": "noop"}

    def test_active_due_sufficient_balance_charges_from_anchor(self):
        now = datetime(2026, 9, 10)
        period_end = _dt(-1, now)  # due yesterday
        result = _decide_renewal(
            status="active", current_period_end=period_end, grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=False,
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
            cancel_at_period_end=False,
        )
        assert result["action"] == "mark_past_due"
        assert result["grace_until"] == now + timedelta(days=2)
        assert result["event"] == "charge_failed"

    # ── cancel_at_period_end: the scheduled cancellation coming due ──────────

    def test_active_not_due_with_cancel_scheduled_is_still_noop(self):
        """Access continues until the period actually ends — the flag changes
        nothing before current_period_end."""
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(5, now), grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=True,
        )
        assert result == {"action": "noop"}

    def test_active_due_with_cancel_scheduled_expires_without_charging(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(-1, now), grace_until=None,
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=True,
        )
        assert result["action"] == "expire"
        assert result["event"] == "cancelled"
        assert "cancel" in result["note"].lower()
        # No charge was even considered, despite a wallet that could pay.
        assert "new_period_end" not in result

    def test_active_due_with_cancel_scheduled_and_empty_wallet_still_expires(self):
        """An empty wallet must not turn a requested cancellation into
        past_due — the user asked to stop, not to be dunned."""
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="active", current_period_end=_dt(-1, now), grace_until=None,
            balance=0, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=True,
        )
        assert result["action"] == "expire"
        assert result["event"] == "cancelled"


class TestDecideRenewalPastDue:
    def test_past_due_sufficient_balance_reactivates_from_now(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-5, now), grace_until=_dt(1, now),
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=False,
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
            cancel_at_period_end=False,
        )
        assert result == {"action": "noop"}

    def test_past_due_grace_expired_cancels(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-4, now), grace_until=_dt(-1, now),
            balance=10, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=False,
        )
        assert result["action"] == "cancel"
        assert result["event"] == "cancelled"
        assert "grace" in result["note"].lower()

    def test_past_due_ignores_cancel_at_period_end(self):
        """The flag is only read on the active-and-due branch. cancel_subscription()
        never schedules on a past_due row (it cancels outright, since there is no
        paid period left), so this state is unreachable in practice — pinned here
        so a future change to the past_due branch is a deliberate one."""
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="past_due", current_period_end=_dt(-5, now), grace_until=_dt(1, now),
            balance=100, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=True,
        )
        assert result["action"] == "charge"
        assert result["event"] == "reactivated"


class TestDecideRenewalCancelled:
    def test_cancelled_is_always_noop(self):
        now = datetime(2026, 9, 10)
        result = _decide_renewal(
            status="cancelled", current_period_end=_dt(-100, now), grace_until=None,
            balance=1000, price=60, billing_period_days=30, now=now,
            cancel_at_period_end=False,
        )
        assert result == {"action": "noop"}


class _FakeRows:
    """Mimics the small slice of a SQLAlchemy CursorResult run_billing_cycle
    actually calls: .fetchall() returning [(id,), (id,), ...]."""
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConnForDueIds:
    """Fake connection used only for the initial due_ids SELECT in
    run_billing_cycle — engine.connect() context manager."""
    def __init__(self, due_ids):
        self._due_ids = due_ids

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *args, **kwargs):
        return _FakeRows([(i,) for i in self._due_ids])


class _FakeEngine:
    """Only implements .connect() (used by run_billing_cycle to fetch due_ids).
    _process_subscription is monkeypatched directly in the test below, so this
    fake never needs to implement .begin()."""
    def __init__(self, due_ids):
        self._due_ids = due_ids

    def connect(self):
        return _FakeConnForDueIds(self._due_ids)


class TestRunBillingCycleExceptionIsolation:
    """run_billing_cycle's docstring promises one failing subscription can't
    block the rest of a run — verified here without a real DB by monkeypatching
    _process_subscription (the per-subscription transaction helper) to raise
    for one id and succeed for the others, then asserting every id was still
    attempted and the successful ones were still counted."""

    def test_one_failing_subscription_does_not_block_others(self, monkeypatch):
        import be.services.subscription as sub_mod

        due_ids = [1, 2, 3]
        attempted = []

        def fake_process_subscription(engine, sub_id, now):
            attempted.append(sub_id)
            if sub_id == 2:
                raise ValueError("Product not active: some-deactivated-product")
            return "charge"

        monkeypatch.setattr(sub_mod, "get_engine_knowledge", lambda: _FakeEngine(due_ids))
        monkeypatch.setattr(sub_mod, "_process_subscription", fake_process_subscription)

        result = sub_mod.run_billing_cycle(now=datetime(2026, 9, 10))

        # All three ids were attempted — subscription 2's failure did not stop
        # the loop from reaching subscription 3.
        assert attempted == [1, 2, 3]
        # The two subscriptions that didn't raise were still counted; the
        # failing one contributed to no counter (it was skipped, not silently
        # treated as any particular outcome).
        assert result == {"renewed": 2, "past_due": 0, "cancelled": 0}

    def test_all_failing_returns_zero_counts_without_raising(self, monkeypatch):
        import be.services.subscription as sub_mod

        due_ids = [10, 11]

        def always_raise(engine, sub_id, now):
            raise RuntimeError(f"boom on {sub_id}")

        monkeypatch.setattr(sub_mod, "get_engine_knowledge", lambda: _FakeEngine(due_ids))
        monkeypatch.setattr(sub_mod, "_process_subscription", always_raise)

        # Must not raise — every failure is caught and logged, not propagated.
        result = sub_mod.run_billing_cycle(now=datetime(2026, 9, 10))
        assert result == {"renewed": 0, "past_due": 0, "cancelled": 0}
