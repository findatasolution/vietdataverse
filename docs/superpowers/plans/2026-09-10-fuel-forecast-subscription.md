# Fuel Forecast Subscription Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a generic, wallet-billed "platform subscription" primitive (reusing the existing Agent-Market credit ledger) and use it to gate a new Fuel Forecast API endpoint + page, so a user can subscribe monthly and have the charge deducted straight from their existing wallet balance.

**Architecture:** Three new tables in `KNOWLEDGE_MARKET_DB` (same DB as `credit_balance`/`credit_ledger`, so debits stay atomic in one transaction) — `platform_products`, `platform_subscriptions`, `platform_subscription_events`. A pure decision function (`_decide_renewal`) drives the billing state machine so it's unit-testable without a database; a thin DB-wrapping layer (`be/services/subscription.py`) applies its decisions atomically, following the exact lock/debit pattern already used by `purchase_product()` in `be/services/credit.py`. A daily GitHub Actions cron runs the billing cycle. Two new FastAPI routers expose subscribe/cancel/history and the gated fuel-forecast data itself. One new static page adapts the already-approved artifact prototype to call the real endpoints.

**Tech Stack:** FastAPI, SQLAlchemy Core (`text()` queries, matching every existing router — no ORM), PostgreSQL (Neon, `KNOWLEDGE_MARKET_DB` + `FUEL_FORECAST_DB`), pytest, vanilla JS + Chart.js (no build step, per repo convention), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md`

## Global Constraints

- No ORM — every DB access uses SQLAlchemy Core `text()` queries, matching `be/services/credit.py` and every router in `be/routers/`.
- Every debit MUST insert a `credit_ledger` row in the same transaction as the `credit_balance` update — never a bare balance write (existing rule, `purchase_product` is the reference implementation).
- New tables live in `KNOWLEDGE_MARKET_DB` (`get_engine_knowledge()`), the same DB as `credit_balance` — a cross-database transaction cannot be atomic, so subscription writes and wallet debits must share one engine/connection.
- Router auth: required auth uses `await authenticate_user(request)` called inside the endpoint body (matches `wallet.py`); optional/anonymous-OK auth uses `Depends(authenticate_user_optional)` + reading `request.state.user` (matches `reports.py`). Never invent a third pattern.
- Each router duplicates its own private `_resolve_user_id` helper — this repo's existing (if not ideal) convention across `wallet.py`, `seller.py`, `knowledge.py`. Do not extract a shared helper as part of this plan.
- Response envelope for every new endpoint: `{"success": true, "source": "<name>", "count": N, "data": ...}` — matches every existing endpoint in the codebase.
- `.env` is loaded from the repo root, not `be/.env` — every migration script's `load_dotenv` call must use `Path(__file__).resolve().parent.parent.parent / '.env'` (migrations dir is `be/migrations/`, three parents up is repo root), matching `run_012.py`.
- Money units: 1 credit = 1,000 VND (`VND_PER_CREDIT` in `credit.py`/`wallet.py`). The Advanced plan is `price_credits=60` (60,000đ), `list_price_credits=120` for the struck-through display.
- Grace period is exactly 3 days (`grace_until = now + timedelta(days=3)`), confirmed in the spec.
- Never commit anything in this plan to git unless the user explicitly asks — follow the project's existing git rule.

---

### Task 1: Database migration — subscription tables

**Files:**
- Create: `be/migrations/013_platform_subscriptions.sql`
- Create: `be/migrations/run_013.py`

**Interfaces:**
- Produces: tables `platform_products`, `platform_subscriptions`, `platform_subscription_events` in `KNOWLEDGE_MARKET_DB`, plus one seed row for `fuel-forecast-advanced`. Every later task depends on these existing.

- [ ] **Step 1: Write the migration SQL**

```sql
-- be/migrations/013_platform_subscriptions.sql
-- Generic wallet-billed subscription primitive for VDV-owned "platform" data
-- products (as opposed to knowledge_products, which is the seller marketplace).
-- See docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md

CREATE TABLE IF NOT EXISTS platform_products (
  code                 VARCHAR(60) PRIMARY KEY,
  name                 TEXT NOT NULL,
  price_credits        INT NOT NULL,
  list_price_credits   INT,
  billing_period_days  INT NOT NULL DEFAULT 30,
  active               BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS platform_subscriptions (
  id                 SERIAL PRIMARY KEY,
  user_id            INT NOT NULL,
  product_code       VARCHAR(60) NOT NULL REFERENCES platform_products(code),
  status             VARCHAR(20) NOT NULL,
  current_period_end TIMESTAMP NOT NULL,
  grace_until        TIMESTAMP,
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  cancelled_at       TIMESTAMP,
  UNIQUE (user_id, product_code)
);
CREATE INDEX IF NOT EXISTS idx_platform_subs_status ON platform_subscriptions (status, current_period_end);

CREATE TABLE IF NOT EXISTS platform_subscription_events (
  id              SERIAL PRIMARY KEY,
  subscription_id INT NOT NULL REFERENCES platform_subscriptions(id),
  event_type      VARCHAR(20) NOT NULL,
  amount_credits  INT,
  note            TEXT,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_platform_sub_events_sub ON platform_subscription_events (subscription_id, created_at DESC);

INSERT INTO platform_products (code, name, price_credits, list_price_credits, billing_period_days, active)
VALUES ('fuel-forecast-advanced', 'Fuel Forecast — Advanced', 60, 120, 30, true)
ON CONFLICT (code) DO NOTHING;
```

- [ ] **Step 2: Write the run script**

```python
"""Run migration 013 on KNOWLEDGE_MARKET_DB (platform subscriptions)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "013_platform_subscriptions.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))
    for table in ("platform_products", "platform_subscriptions", "platform_subscription_events"):
        cols = [r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=:t AND table_schema='public' ORDER BY ordinal_position"
        ), {"t": table})]
        print(f"{table}: {cols}")
    seeded = conn.execute(text("SELECT code, price_credits, list_price_credits FROM platform_products")).fetchall()
    print("platform_products rows:", seeded)

print("Migration 013 applied successfully to KNOWLEDGE_MARKET_DB")
```

- [ ] **Step 3: Run it against the real dev DB**

Run: `~/.pyenv/versions/3.11.9/bin/python be/migrations/run_013.py` (adjust the
python path to whatever this environment uses — this repo has previously used
`~/.pyenv/versions/3.11.9/bin/python` when a bare `python`/`python3` wasn't on
PATH).

Expected: prints the three tables' column lists and one seeded
`platform_products` row `('fuel-forecast-advanced', 60, 120)`.

- [ ] **Step 4: Commit**

```bash
git add be/migrations/013_platform_subscriptions.sql be/migrations/run_013.py
git commit -m "feat(subscription): add platform_products/subscriptions/events tables"
```

---

### Task 2: Billing engine — `be/services/subscription.py`

**Files:**
- Create: `be/services/subscription.py`
- Create: `tests/subscription/test_subscription_service.py`

**Interfaces:**
- Consumes: `get_engine_knowledge()` from `be/core/engines.py`; `InsufficientCredits` from `be/services/credit.py` (import, do not redefine).
- Produces (used by Task 3, 4, 5):
  - `subscribe(user_id: int, product_code: str) -> dict` → `{"subscription_id": int, "current_period_end": datetime, "balance_after": int}`
  - `cancel_subscription(user_id: int, product_code: str) -> dict` → `{"status": "cancelled"}`
  - `has_active_subscription(user_id: int | None, product_code: str) -> bool`
  - `get_subscription(user_id: int, product_code: str) -> dict | None` → row as dict, or `None`
  - `list_subscription_history(user_id: int, limit: int = 50, offset: int = 0) -> list[dict]`
  - `run_billing_cycle(now: datetime | None = None) -> dict` → `{"renewed": int, "past_due": int, "cancelled": int}`
  - `_decide_renewal(status, current_period_end, grace_until, balance, price, billing_period_days, now) -> dict` — the pure function other tasks do NOT call directly, but its shape matters for Task 2's own tests.

- [ ] **Step 1: Write the failing tests for the pure decision function**

```python
# tests/subscription/test_subscription_service.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `~/.pyenv/versions/3.11.9/bin/python -m pytest tests/subscription/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'be.services.subscription'` (module does not exist yet).

- [ ] **Step 3: Implement the pure decision function + the full service module**

```python
# be/services/subscription.py
"""Platform subscription billing — atomic, idempotent, same pattern as
be/services/credit.py's purchase_product(). New tables live in
KNOWLEDGE_MARKET_DB (same DB as credit_balance/credit_ledger), so a
subscription write and a wallet debit always share one transaction.
"""
from datetime import datetime, timedelta

from sqlalchemy import text

from core.engines import get_engine_knowledge
from services.credit import InsufficientCredits

GRACE_PERIOD_DAYS = 3


class SubscriptionError(Exception):
    pass


def _decide_renewal(status: str, current_period_end: datetime, grace_until: datetime | None,
                    balance: int, price: int, billing_period_days: int,
                    now: datetime) -> dict:
    """PURE. One decision for one subscription row during a billing-cycle pass.
    See docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md
    "run_billing_cycle" for the two-pass rationale (on-time renewal extends from
    the existing anchor date; a late reactivation buys a fresh period from now)."""
    if status == "cancelled":
        return {"action": "noop"}

    if status == "active":
        if current_period_end > now:
            return {"action": "noop"}
        if balance >= price:
            return {
                "action": "charge",
                "new_status": "active",
                "new_period_end": current_period_end + timedelta(days=billing_period_days),
                "event": "charged",
            }
        return {
            "action": "mark_past_due",
            "grace_until": now + timedelta(days=GRACE_PERIOD_DAYS),
            "event": "charge_failed",
        }

    if status == "past_due":
        if balance >= price:
            return {
                "action": "charge",
                "new_status": "active",
                "new_period_end": now + timedelta(days=billing_period_days),
                "event": "reactivated",
            }
        if grace_until is not None and now > grace_until:
            return {
                "action": "cancel",
                "event": "cancelled",
                "note": "Grace period expired without sufficient balance",
            }
        return {"action": "noop"}

    raise SubscriptionError(f"unknown subscription status: {status!r}")


def _get_product(conn, product_code: str) -> dict:
    row = conn.execute(text("""
        SELECT price_credits, billing_period_days, active
        FROM platform_products WHERE code = :c
    """), {"c": product_code}).first()
    if not row:
        raise ValueError(f"Unknown product_code: {product_code}")
    if not row[2]:
        raise ValueError(f"Product not active: {product_code}")
    return {"price_credits": row[0], "billing_period_days": row[1]}


def _write_event(conn, subscription_id: int, event_type: str,
                 amount_credits: int | None = None, note: str | None = None) -> None:
    conn.execute(text("""
        INSERT INTO platform_subscription_events (subscription_id, event_type, amount_credits, note)
        VALUES (:sid, :et, :amt, :note)
    """), {"sid": subscription_id, "et": event_type, "amt": amount_credits, "note": note})


def subscribe(user_id: int, product_code: str) -> dict:
    """Subscribe (or reactivate a cancelled subscription). Raises ValueError if
    already active/past_due, or if the product doesn't exist/is inactive.
    Raises InsufficientCredits if the wallet can't cover the first charge."""
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        product = _get_product(conn, product_code)
        price = product["price_credits"]
        period_days = product["billing_period_days"]

        existing = conn.execute(text("""
            SELECT id, status FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p FOR UPDATE
        """), {"u": user_id, "p": product_code}).first()
        if existing and existing[1] in ("active", "past_due"):
            raise ValueError(f"Already subscribed (status={existing[1]})")

        balance_row = conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"
        ), {"u": user_id}).first()
        balance = balance_row[0] if balance_row else 0
        if balance < price:
            raise InsufficientCredits(f"Insufficient credits: need {price}, have {balance}")

        now = datetime.utcnow()
        period_end = now + timedelta(days=period_days)

        if existing:
            sub_id = existing[0]
            conn.execute(text("""
                UPDATE platform_subscriptions
                SET status='active', current_period_end=:pe, grace_until=NULL, cancelled_at=NULL
                WHERE id = :id
            """), {"pe": period_end, "id": sub_id})
        else:
            sub_id = conn.execute(text("""
                INSERT INTO platform_subscriptions (user_id, product_code, status, current_period_end)
                VALUES (:u, :p, 'active', :pe) RETURNING id
            """), {"u": user_id, "p": product_code, "pe": period_end}).scalar()

        idem_key = f"subscription:{sub_id}:{int(now.timestamp())}"
        conn.execute(text("""
            INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
            VALUES (:u, :a, 'subscription_charge', 'subscription', :sid, :k, :n)
        """), {"u": user_id, "a": -price, "sid": sub_id, "k": idem_key,
               "n": f"Subscribe {product_code}"})
        conn.execute(text("""
            UPDATE credit_balance SET balance = balance - :a, updated_at = NOW() WHERE user_id = :u
        """), {"a": price, "u": user_id})

        _write_event(conn, sub_id, "created")
        _write_event(conn, sub_id, "charged", amount_credits=price)

        return {"subscription_id": sub_id, "current_period_end": period_end,
                "balance_after": balance - price}


def cancel_subscription(user_id: int, product_code: str) -> dict:
    """Idempotent: cancelling an already-cancelled subscription is a no-op."""
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, status FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p FOR UPDATE
        """), {"u": user_id, "p": product_code}).first()
        if not row:
            raise ValueError("No subscription found")
        sub_id, status = row
        if status == "cancelled":
            return {"status": "cancelled"}

        conn.execute(text("""
            UPDATE platform_subscriptions
            SET status='cancelled', cancelled_at=NOW() WHERE id = :id
        """), {"id": sub_id})
        _write_event(conn, sub_id, "cancelled", note="Cancelled by user")
        return {"status": "cancelled"}


def get_subscription(user_id: int, product_code: str) -> dict | None:
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, status, current_period_end, grace_until, created_at, cancelled_at
            FROM platform_subscriptions WHERE user_id = :u AND product_code = :p
        """), {"u": user_id, "p": product_code}).first()
    if not row:
        return None
    return {
        "id": row[0], "status": row[1], "current_period_end": row[2],
        "grace_until": row[3], "created_at": row[4], "cancelled_at": row[5],
    }


def has_active_subscription(user_id: int | None, product_code: str) -> bool:
    if user_id is None:
        return False
    sub = get_subscription(user_id, product_code)
    return bool(sub and sub["status"] == "active")


def list_subscription_history(user_id: int, limit: int = 50, offset: int = 0) -> list[dict]:
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT e.id, e.event_type, e.amount_credits, e.note, e.created_at,
                   s.product_code
            FROM platform_subscription_events e
            JOIN platform_subscriptions s ON s.id = e.subscription_id
            WHERE s.user_id = :u
            ORDER BY e.created_at DESC
            LIMIT :lim OFFSET :off
        """), {"u": user_id, "lim": limit, "off": offset}).fetchall()
    return [{
        "id": r[0], "event_type": r[1], "amount_credits": r[2], "note": r[3],
        "created_at": r[4], "product_code": r[5],
    } for r in rows]


def run_billing_cycle(now: datetime | None = None) -> dict:
    """Called by the daily cron. One short transaction per subscription — a
    stuck row must not block every other renewal."""
    now = now or datetime.utcnow()
    engine = get_engine_knowledge()
    counts = {"renewed": 0, "past_due": 0, "cancelled": 0}

    with engine.connect() as conn:
        due_ids = [r[0] for r in conn.execute(text("""
            SELECT id FROM platform_subscriptions WHERE status IN ('active', 'past_due')
        """)).fetchall()]

    for sub_id in due_ids:
        with engine.begin() as conn:
            sub = conn.execute(text("""
                SELECT id, user_id, product_code, status, current_period_end, grace_until
                FROM platform_subscriptions WHERE id = :id FOR UPDATE
            """), {"id": sub_id}).first()
            if not sub:
                continue
            _, user_id, product_code, status, period_end, grace_until = sub
            product = _get_product(conn, product_code)

            balance_row = conn.execute(text(
                "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"
            ), {"u": user_id}).first()
            balance = balance_row[0] if balance_row else 0

            decision = _decide_renewal(
                status=status, current_period_end=period_end, grace_until=grace_until,
                balance=balance, price=product["price_credits"],
                billing_period_days=product["billing_period_days"], now=now,
            )

            if decision["action"] == "noop":
                continue

            if decision["action"] == "charge":
                price = product["price_credits"]
                idem_key = f"subscription:{sub_id}:renew:{int(now.timestamp())}"
                conn.execute(text("""
                    INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
                    VALUES (:u, :a, 'subscription_charge', 'subscription', :sid, :k, :n)
                """), {"u": user_id, "a": -price, "sid": sub_id, "k": idem_key,
                       "n": f"Renew {product_code}"})
                conn.execute(text("""
                    UPDATE credit_balance SET balance = balance - :a, updated_at = NOW() WHERE user_id = :u
                """), {"a": price, "u": user_id})
                conn.execute(text("""
                    UPDATE platform_subscriptions
                    SET status = :st, current_period_end = :pe, grace_until = NULL
                    WHERE id = :id
                """), {"st": decision["new_status"], "pe": decision["new_period_end"], "id": sub_id})
                _write_event(conn, sub_id, decision["event"], amount_credits=price)
                counts["renewed"] += 1

            elif decision["action"] == "mark_past_due":
                conn.execute(text("""
                    UPDATE platform_subscriptions SET status = 'past_due', grace_until = :g
                    WHERE id = :id
                """), {"g": decision["grace_until"], "id": sub_id})
                _write_event(conn, sub_id, decision["event"])
                counts["past_due"] += 1

            elif decision["action"] == "cancel":
                conn.execute(text("""
                    UPDATE platform_subscriptions SET status = 'cancelled', cancelled_at = :now
                    WHERE id = :id
                """), {"now": now, "id": sub_id})
                _write_event(conn, sub_id, decision["event"], note=decision["note"])
                counts["cancelled"] += 1

    return counts


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    if "--run-billing-cycle" in sys.argv:
        result = run_billing_cycle()
        print(f"Billing cycle complete: {result}")
    else:
        sys.exit("Usage: python be/services/subscription.py --run-billing-cycle")
```

- [ ] **Step 4: Run the pure-function tests to verify they pass**

Run: `~/.pyenv/versions/3.11.9/bin/python -m pytest tests/subscription/ -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Manually verify the DB-touching functions against the real dev DB**

This repo has no existing pytest fixture for a live-DB transaction test (checked:
no test file exists for `credit.py` either) — don't invent a new fixture
convention as a side effect of this task. Verify by running a one-off script,
the same way this session already verified `crawl_moit_fuel.py` and
`be/fuel/backtest.py` against the real `FUEL_FORECAST_DB`:

```bash
~/.pyenv/versions/3.11.9/bin/python - <<'EOF'
import sys
sys.path.insert(0, "be")
from services.subscription import subscribe, cancel_subscription, get_subscription, run_billing_cycle
from services.credit import credit_topup, get_balance

TEST_USER = 999999001  # arbitrary id unlikely to collide with a real user
credit_topup(TEST_USER, credits=100, idem_key="test-topup-1")
print("balance before:", get_balance(TEST_USER))
result = subscribe(TEST_USER, "fuel-forecast-advanced")
print("subscribed:", result)
print("balance after:", get_balance(TEST_USER))
print("subscription row:", get_subscription(TEST_USER, "fuel-forecast-advanced"))
print("cancel:", cancel_subscription(TEST_USER, "fuel-forecast-advanced"))
print("subscription row after cancel:", get_subscription(TEST_USER, "fuel-forecast-advanced"))
EOF
```

Expected: balance goes 100 → 40 after subscribing (100 - 60), subscription row
shows `status='active'`, then `status='cancelled'` after cancel. If anything
raises, fix `subscription.py` before moving on — do not proceed to Task 3
with an unverified service layer.

Clean up the test row afterward (this is throwaway data, not a fixture other
tests rely on):

```bash
~/.pyenv/versions/3.11.9/bin/python - <<'EOF'
import sys
sys.path.insert(0, "be")
from core.engines import get_engine_knowledge
from sqlalchemy import text
TEST_USER = 999999001
with get_engine_knowledge().begin() as conn:
    conn.execute(text("DELETE FROM platform_subscription_events WHERE subscription_id IN (SELECT id FROM platform_subscriptions WHERE user_id=:u)"), {"u": TEST_USER})
    conn.execute(text("DELETE FROM platform_subscriptions WHERE user_id=:u"), {"u": TEST_USER})
    conn.execute(text("DELETE FROM credit_ledger WHERE user_id=:u"), {"u": TEST_USER})
    conn.execute(text("DELETE FROM credit_balance WHERE user_id=:u"), {"u": TEST_USER})
print("cleaned up")
EOF
```

- [ ] **Step 6: Commit**

```bash
git add be/services/subscription.py tests/subscription/test_subscription_service.py
git commit -m "feat(subscription): add wallet-billed subscription service with billing state machine"
```

---

### Task 3: Subscription API router

**Files:**
- Create: `be/routers/subscription.py`
- Modify: `be/main.py` (router import line + `include_router` calls)

**Interfaces:**
- Consumes: `subscribe`, `cancel_subscription`, `get_subscription`, `list_subscription_history` from `be.services.subscription` (Task 2); `authenticate_user` from `middleware`; `get_engine_user`, `get_engine_knowledge` from `core.engines`.
- Produces: `router` (FastAPI `APIRouter`), imported and mounted by `be/main.py`.

- [ ] **Step 1: Write the router**

```python
# be/routers/subscription.py
"""
Subscription router — platform product catalog, subscribe/cancel, billing history.

Endpoints:
  GET  /api/v1/subscriptions/plans      (public)
  GET  /api/v1/subscriptions/me         (auth)
  POST /api/v1/subscriptions/subscribe  (auth) body: {"product_code": str}
  POST /api/v1/subscriptions/cancel     (auth) body: {"product_code": str}
  GET  /api/v1/subscriptions/history?limit&offset (auth)
"""
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_user, get_engine_knowledge
from middleware import authenticate_user
from services.credit import InsufficientCredits
from services.subscription import (
    subscribe as _subscribe,
    cancel_subscription as _cancel_subscription,
    get_subscription,
    list_subscription_history,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _require_auth(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _resolve_user_id(auth0_id: str) -> int:
    with get_engine_user().connect() as conn:
        row = conn.execute(text(
            "SELECT user_id FROM users WHERE auth0_id = :aid"
        ), {"aid": auth0_id}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row[0]


class ProductCodeBody(BaseModel):
    product_code: str


@router.get("/plans")
async def list_plans():
    with get_engine_knowledge().connect() as conn:
        rows = conn.execute(text("""
            SELECT code, name, price_credits, list_price_credits, billing_period_days
            FROM platform_products WHERE active = true
        """)).fetchall()
    data = [{
        "code": r[0], "name": r[1], "price_credits": r[2],
        "list_price_credits": r[3], "billing_period_days": r[4],
    } for r in rows]
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})


@router.get("/me")
async def my_subscriptions(request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    with get_engine_knowledge().connect() as conn:
        codes = [r[0] for r in conn.execute(text(
            "SELECT code FROM platform_products WHERE active = true"
        )).fetchall()]
    data = [s for s in (get_subscription(user_id, c) for c in codes) if s]
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})


@router.post("/subscribe")
async def do_subscribe(body: ProductCodeBody, request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    try:
        result = _subscribe(user_id, body.product_code)
    except InsufficientCredits as e:
        raise HTTPException(status_code=402, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _json_response({"success": True, "source": "subscriptions", "count": 1, "data": result})


@router.post("/cancel")
async def do_cancel(body: ProductCodeBody, request: Request):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    try:
        result = _cancel_subscription(user_id, body.product_code)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return _json_response({"success": True, "source": "subscriptions", "count": 1, "data": result})


@router.get("/history")
async def history(request: Request, limit: int = 50, offset: int = 0):
    await authenticate_user(request)
    user = _require_auth(request)
    user_id = _resolve_user_id(user.get("auth0_id"))

    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    data = list_subscription_history(user_id, limit=limit, offset=offset)
    return _json_response({"success": True, "source": "subscriptions", "count": len(data), "data": data})
```

- [ ] **Step 2: Register the router in `be/main.py`**

Modify the import line:

```python
from routers import market_data, analysis, auth_routes, interest, admin, developer, vn30_data, student_verify, knowledge, wallet, seller, reports, takedown, webhooks, feedback, subscription
```

Add after `app.include_router(wallet.router)`:

```python
app.include_router(subscription.router)
```

- [ ] **Step 3: Smoke-test the plans endpoint locally**

Run: `cd be && uvicorn main:app --reload` (in one terminal), then in another:

```bash
curl -s http://localhost:8000/api/v1/subscriptions/plans | python3 -m json.tool
```

Expected: `{"success": true, "source": "subscriptions", "count": 1, "data": [{"code": "fuel-forecast-advanced", "name": "Fuel Forecast — Advanced", "price_credits": 60, "list_price_credits": 120, "billing_period_days": 30}]}`

Stop the server (Ctrl-C) once verified.

- [ ] **Step 4: Commit**

```bash
git add be/routers/subscription.py be/main.py
git commit -m "feat(subscription): add subscription API router"
```

---

### Task 4: Gated Fuel Forecast endpoint

**Files:**
- Create: `be/routers/fuel_forecast.py`
- Modify: `be/main.py`

**Interfaces:**
- Consumes: `has_active_subscription` from `be.services.subscription` (Task 2); `get_engine_fuel` from `core.engines`; `authenticate_user_optional` from `middleware`.
- Produces: `router`, mounted by `be/main.py`.

- [ ] **Step 1: Write the router**

```python
# be/routers/fuel_forecast.py
"""
Fuel Forecast router — gated by platform subscription 'fuel-forecast-advanced'.

  GET /api/v1/fuel-forecast/{fuel}   fuel in {RON95, E5RON92, DO005S}

Auth optional. Without an active subscription: history + base scenario only,
breakdown stripped to the disclaimer. With one: full response including the
low/high scenarios and the model breakdown (k, resid_std, sigma_world).
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_fuel, get_engine_user
from middleware import authenticate_user_optional
from services.subscription import has_active_subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/fuel-forecast", tags=["fuel-forecast"])

VALID_FUELS = {"RON95", "E5RON92", "DO005S"}
PRODUCT_CODE = "fuel-forecast-advanced"


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _resolve_user_id_optional(auth0_id: Optional[str]) -> Optional[int]:
    if not auth0_id:
        return None
    try:
        with get_engine_user().connect() as conn:
            row = conn.execute(text(
                "SELECT user_id FROM users WHERE auth0_id = :aid"
            ), {"aid": auth0_id}).fetchone()
        return row[0] if row else None
    except Exception:
        return None


@router.get("/{fuel}")
async def get_forecast(fuel: str, request: Request, _auth: None = Depends(authenticate_user_optional)):
    if fuel not in VALID_FUELS:
        raise HTTPException(status_code=404, detail=f"Unknown fuel. Valid: {sorted(VALID_FUELS)}")

    user = getattr(request.state, "user", None)
    user_id = _resolve_user_id_optional(user.get("auth0_id")) if user else None
    is_advanced = has_active_subscription(user_id, PRODUCT_CODE)

    engine = get_engine_fuel()
    with engine.connect() as conn:
        hist = conn.execute(text("""
            SELECT period, retail_price FROM fuel_price_cycle
            WHERE fuel = :f ORDER BY period
        """), {"f": fuel}).fetchall()

        run_ts = conn.execute(text(
            "SELECT max(run_ts) FROM fuel_forecast WHERE fuel = :f"
        ), {"f": fuel}).scalar()

        fc_rows = []
        if run_ts is not None:
            fc_rows = conn.execute(text("""
                SELECT horizon, scenario, target_cycle, point, breakdown
                FROM fuel_forecast WHERE fuel = :f AND run_ts = :rt
                ORDER BY horizon
            """), {"f": fuel, "rt": run_ts}).fetchall()

    history = [{"period": str(p), "retail_price": float(r)} for p, r in hist]

    forecast = []
    for horizon, scenario, target_cycle, point, breakdown in fc_rows:
        if not is_advanced and scenario != "base":
            continue
        bd = breakdown if isinstance(breakdown, dict) else json.loads(breakdown)
        row = {
            "horizon": horizon, "scenario": scenario,
            "target_cycle": str(target_cycle), "point": float(point),
        }
        if is_advanced:
            row["breakdown"] = bd
        else:
            row["breakdown"] = {"disclaimer": bd.get("disclaimer")}
        forecast.append(row)

    return _json_response({
        "success": True, "source": "fuel-forecast", "count": len(history) + len(forecast),
        "data": {
            "fuel": fuel, "tier": "advanced" if is_advanced else "free",
            "history": history, "forecast": forecast,
        },
    })
```

- [ ] **Step 2: Register the router in `be/main.py`**

Modify the import line from Task 3 to also include `fuel_forecast`:

```python
from routers import market_data, analysis, auth_routes, interest, admin, developer, vn30_data, student_verify, knowledge, wallet, seller, reports, takedown, webhooks, feedback, subscription, fuel_forecast
```

Add after `app.include_router(subscription.router)`:

```python
app.include_router(fuel_forecast.router)
```

- [ ] **Step 3: Smoke-test both tiers locally**

Run: `cd be && uvicorn main:app --reload`, then:

```bash
curl -s http://localhost:8000/api/v1/fuel-forecast/RON95 | python3 -m json.tool
```

Expected: `"tier": "free"`, `forecast` array contains only `"scenario": "base"`
rows, each `breakdown` has only `disclaimer`. (Testing the `"advanced"` tier
end-to-end requires a real Bearer token + an active subscription — cover that
manually once Task 6's page exists, not here.)

Stop the server once verified.

- [ ] **Step 4: Commit**

```bash
git add be/routers/fuel_forecast.py be/main.py
git commit -m "feat(subscription): add gated fuel-forecast API endpoint"
```

---

### Task 5: Billing cron

**Files:**
- Create: `.github/workflows/subscription-billing.yml`

**Interfaces:**
- Consumes: `run_billing_cycle()` via the `python be/services/subscription.py --run-billing-cycle` CLI entrypoint from Task 2.

- [ ] **Step 1: Write the workflow**

```yaml
name: Subscription Billing

# Daily wallet-debit billing cycle for platform subscriptions. Odd, non-:00/:30
# minute per CLAUDE.md's crawl-scheduling rule (avoids GitHub's congested
# round-minute slots) — this job doesn't need same-minute precision, it just
# must not silently fail to run for days without anyone noticing.
on:
  schedule:
    - cron: '11 3 * * *'   # 10:11 VN
  workflow_dispatch:

jobs:
  run-billing-cycle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r be/requirements.txt
      - name: Run billing cycle
        run: python be/services/subscription.py --run-billing-cycle
        env:
          KNOWLEDGE_MARKET_DB: ${{ secrets.KNOWLEDGE_MARKET_DB }}
```

- [ ] **Step 2: Verify the workflow YAML is well-formed**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/subscription-billing.yml'))" && echo OK`
Expected: `OK` (no `pip install pyyaml` needed if it's already present from
other tooling; if `ModuleNotFoundError: yaml`, run
`~/.pyenv/versions/3.11.9/bin/python -m pip install --user pyyaml` first, then
retry).

- [ ] **Step 3: Confirm the `KNOWLEDGE_MARKET_DB` secret already exists in the repo**

Run: `gh secret list | grep KNOWLEDGE_MARKET_DB`
Expected: a line showing the secret exists (it must already be there — every
other workflow that touches Knowledge Market data depends on it too). If it's
missing, stop and tell the user — do not add DB secrets on your own.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/subscription-billing.yml
git commit -m "feat(subscription): add daily billing-cycle cron"
```

---

### Task 6: Fuel Forecast page

**Files:**
- Create: `fe/pages/fuel-forecast.html`

**Interfaces:**
- Consumes: `GET /api/v1/fuel-forecast/{fuel}` (Task 4), `GET /api/v1/subscriptions/plans`, `GET /api/v1/subscriptions/me`, `POST /api/v1/subscriptions/subscribe`, `GET /api/v1/subscriptions/history` (Task 3); `fetchWithAuth`, `login`, `isAuthenticated` from `fe/auth.js`; Chart.js (already loaded site-wide via `_layout_head.html` pattern — this is a standalone page like the rest of `fe/pages/`, so it loads its own copy the same way `fe/pages/admin.html` or similar standalone pages already do).

- [ ] **Step 1: Check how an existing standalone page loads Chart.js + auth.js, to match exactly**

Run: `grep -n "chart.js\|auth.js\|auth0-spa-js" fe/pages/account.html fe/pages/admin.html 2>/dev/null | head -20`

Use whatever `<script src="...">` tags and load order that shows — don't
improvise a different CDN path or version than what the rest of `fe/pages/`
already uses.

- [ ] **Step 2: Build the page**

Base the markup, styling and fan-chart JS on the already-approved artifact
prototype (`https://claude.ai/code/artifact/4c4d1d04-43e4-484f-a097-4fd3ffe97029`
— re-read it with the Artifact tool's `action: "read"` for the exact HTML/CSS/JS
to start from). Required changes from that prototype:

1. Replace the hardcoded `DATA` JSON blob with a `fetch` call per fuel to
   `/api/v1/fuel-forecast/{fuel}` on page load and on fuel-tab switch.
2. Replace the demo toggle buttons (`#btn-locked`/`#btn-unlocked`) with real
   state driven by the response's `"tier"` field (`"free"` → show lock
   overlay as before; `"advanced"` → show full chart, no toggle needed at all
   once a real subscription exists — a paying user should never see a fake
   "preview as free" button).
3. Replace the `"Xem như khách hàng B2B"` button with a real subscribe flow:
   if `isAuthenticated()` is false, call `login(currentPageUrl)` (same
   pattern as the `dev-link`/`login-link` distinction in `fe/CLAUDE.md`
   §13.4); if true, `POST /api/v1/subscriptions/subscribe` with
   `{"product_code": "fuel-forecast-advanced"}`, then re-fetch the forecast
   endpoint so the page flips to the advanced view without a reload. On a 402
   (insufficient credits), show a message pointing at the wallet top-up flow
   instead of a generic error.
4. Add the "Lịch sử thanh toán" card: fetch `/api/v1/subscriptions/history`
   once the page knows the user has ever subscribed (any row from
   `/subscriptions/me`, regardless of status), render event rows with these
   Vietnamese labels:
   - `created` → "Đăng ký mới"
   - `charged` → "Gia hạn thành công"
   - `charge_failed` → "Không đủ số dư — vào grace period"
   - `cancelled` → "Huỷ"
   - `reactivated` → "Kích hoạt lại"
5. Keep the methodology disclaimer card and the stat tiles (k, R², skill) —
   those numbers come from the model, not from the subscription state, so
   they render the same in both tiers except the paid tier also gets the
   `breakdown.k_vnd_per_usd_bbl` etc. fields the free-tier response omits
   (Task 4 strips them server-side already — the page just renders whatever
   the response contains, no client-side gating logic needed for that part).

- [ ] **Step 3: Manual verification in a real browser**

Run the backend (`cd be && uvicorn main:app --reload`) and open
`fe/pages/fuel-forecast.html` directly (or via the FastAPI static mount if
running the full stack) with a real logged-in test account:

1. Confirm the free view loads with real history + a base-only line and the
   lock overlay, no console errors.
2. Confirm clicking subscribe (with a wallet balance >= 60 credits already
   topped up) flips the page to the advanced view with the full fan chart.
3. Confirm `/subscriptions/history` shows a `"created"`/`"Đăng ký mới"` row
   after subscribing.
4. Confirm cancelling and reloading returns the page to the free view.

This step needs a browser and a logged-in Auth0 session — do it manually, or
via the `browser-automation` skill if a way to authenticate the headless
session against this project's Auth0 tenant already exists; don't invent a
mock-auth bypass for this page alone just to make the check automatable.

- [ ] **Step 4: Commit**

```bash
git add fe/pages/fuel-forecast.html
git commit -m "feat(subscription): add Fuel Forecast product page"
```

---

### Task 7: Documentation close-out

**Files:**
- Modify: `CLAUDE.md`
- Modify: `BACKLOG.md`

**Interfaces:** None — this task only updates docs, per the repo's
Documentation Close-out rule ("Do not close a task while related
documentation is known to be stale").

- [ ] **Step 1: Update `CLAUDE.md`**

Add a new subsection under "Backend (FastAPI)" (or directly after the
existing Fuel Forecast model section) documenting:
- The three new tables and which DB they live in (`KNOWLEDGE_MARKET_DB`, not
  `FUEL_FORECAST_DB` — a common mix-up risk since the *feature* is about fuel
  forecasting but the *billing* tables sit with the wallet).
- The `/api/v1/subscriptions/*` and `/api/v1/fuel-forecast/{fuel}` endpoints
  and their auth requirements (from this plan's Task 3/4 docstrings — copy
  the endpoint list, don't re-derive it).
- The daily billing cron and the 3-day grace period behavior.
- That `fuel_world_daily`/Brent-RBOB remain unused by this endpoint too (it
  reads only `fuel_price_cycle`/`fuel_forecast`) — consistent with the
  "structural-v1 removed" note already in `CLAUDE.md`.

- [ ] **Step 2: Update `BACKLOG.md`**

In the Fuel-forecast backlog item, replace the "Plan 3/4... CHƯA bắt đầu,
không có router fuel nào trong `be/main.py`" line (written earlier this
session) with the actual current state: Plan 3-equivalent (public data
endpoint) done via the free/advanced tier split, billed via wallet
subscription rather than the originally-envisioned corporate OAuth2 API —
note explicitly that this is a deliberate pivot from the original Plan 4
design (confirmed with the user this session), not an oversight. Keep the
existing note that the NĐ169 legal opinion is still unresolved and that
opening this to real paying customers (as opposed to having the mechanism
exist) still waits on it.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md BACKLOG.md
git commit -m "docs(subscription): document platform subscription system and fuel-forecast gating"
```

---

## Self-Review Notes

- **Spec coverage**: all 7 spec sections (data model, billing engine, cron,
  API, fuel-forecast gating, FE, testing) map to Tasks 1-6; the spec's
  "explicitly out of scope" items are respected (no proration code, no
  catalog admin UI, no NĐ169 work attempted).
- **Type/name consistency checked**: `_decide_renewal`'s return dict keys
  (`action`, `new_status`, `new_period_end`, `event`, `grace_until`, `note`)
  are used identically in both the Task 2 tests and `run_billing_cycle`'s
  consumption of them in Task 2's implementation step. `PRODUCT_CODE =
  "fuel-forecast-advanced"` in Task 4 matches the seed row in Task 1 and the
  FE's `product_code` body in Task 6 exactly.
- **No placeholder scan**: every step has real, complete code — no "similar
  to Task N", no "add error handling" without showing it.
