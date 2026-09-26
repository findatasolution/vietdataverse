# API Trial with Wallet Hold — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user start a 7-day trial of the paid API plan without being charged, by reserving one month's price in their wallet and auto-charging that reservation when the trial ends.

**Architecture:** `credit_balance.balance` never moves at trial start. A new `credit_holds` row reserves the price; every spending path switches from raw balance to *available* balance (`balance − active holds`). The trial is a new `status='trialing'` on the existing `platform_subscriptions` row, so the existing `run_billing_cycle` cron converts it. Consent is an append-only `trial_consents` row, not a mutable flag.

**Tech Stack:** FastAPI, SQLAlchemy Core (raw `text()` SQL, the house style), PostgreSQL on Neon, pytest. No new dependency.

**Spec:** `docs/superpowers/specs/2026-09-27-api-trial-wallet-hold-design.md`

## Global Constraints

- Wallet tables live in `KNOWLEDGE_MARKET_DB` (`get_engine_knowledge()`); `users.current_plan` / `premium_expiry` / `user_level` live in `USER_DB` (`get_engine_user()`). **There is no shared transaction.** Wallet side commits first; entitlement second and idempotently.
- `VND_PER_CREDIT = 1000` (`be/services/credit.py`). The API plan is 45.000đ → **45 credits**.
- Trial length is **7 days**. Billing period after conversion is **30 days**.
- Every new `credit_ledger.kind` value needs the CHECK constraint widened in the same migration, or the INSERT fails at runtime (this bit us in migration 014).
- Migration files are `be/migrations/NNN_name.sql` plus a `run_NNN.py` runner that verifies its own effect (see `run_019.py`, `run_020.py`).
- All user-facing copy is Vietnamese; code, comments and commit messages are English.
- Money amounts shown to the user are VND, not credits. Convert at the edge.

## Review Focus

1. **A second trial after the first one ended.** `trial_consents` is append-only and `platform_subscriptions` is `UNIQUE (user_id, product_code)`, so a returning user hits an existing row — the trial must be refused (one per user per product), not silently granted again. Covered in Task 4.
2. **Wallet drained to exactly the hold amount.** Available balance must reach 0, not go negative, and an unrelated purchase attempt at that moment must be refused rather than eating the reservation. Covered in Task 2.
3. **Cron runs twice on the same trial.** `run_billing_cycle` is a daily cron with `workflow_dispatch`; a manual run on the same day must not charge twice or release the hold twice. Covered in Task 5.
4. **Entitlement write fails after the wallet write succeeded.** The user is holding money with no API tier. The next cron pass must repair it rather than leaving it stuck. Covered in Task 6.
5. **User cancels during the trial.** The hold must be released immediately and no charge may follow — cancelling a trial is not the same as cancelling a paid period, where access continues to period end. Covered in Task 7.

---

### Task 1: `credit_holds` table and its migration

**Files:**
- Create: `be/migrations/021_credit_holds.sql`
- Create: `be/migrations/run_021.py`
- Test: `tests/subscription/test_credit_holds_schema.py`

**Interfaces:**
- Consumes: nothing.
- Produces: table `credit_holds (id, user_id, amount_credits, reason, ref_type, ref_id, status, expires_at, created_at, released_at)` with `status IN ('active','released','captured')`; partial unique index preventing two active holds for the same `(ref_type, ref_id)`.

- [ ] **Step 1: Write the failing test**

```python
"""credit_holds must make a double reservation impossible at the DB level."""
import os
import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    not os.getenv("KNOWLEDGE_MARKET_DB"), reason="needs KNOWLEDGE_MARKET_DB")


@pytest.fixture
def conn():
    engine = create_engine(os.environ["KNOWLEDGE_MARKET_DB"])
    with engine.connect() as c:
        yield c
        c.rollback()


def test_table_and_columns_exist(conn):
    cols = {r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'credit_holds'"""))}
    assert {"id", "user_id", "amount_credits", "reason", "ref_type", "ref_id",
            "status", "expires_at", "created_at", "released_at"} <= cols


def test_two_active_holds_for_same_ref_are_rejected(conn):
    conn.execute(text("""
        INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
        VALUES (-1, 45, 'trial', 'subscription', -1, 'active', NOW() + interval '7 days')"""))
    with pytest.raises(Exception):
        conn.execute(text("""
            INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
            VALUES (-1, 45, 'trial', 'subscription', -1, 'active', NOW() + interval '7 days')"""))


def test_released_hold_does_not_block_a_new_active_one(conn):
    conn.execute(text("""
        INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at, released_at)
        VALUES (-2, 45, 'trial', 'subscription', -2, 'released', NOW(), NOW())"""))
    conn.execute(text("""
        INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
        VALUES (-2, 45, 'trial', 'subscription', -2, 'active', NOW() + interval '7 days')"""))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_credit_holds_schema.py -v`
Expected: FAIL — `credit_holds` does not exist.

- [ ] **Step 3: Write the migration**

```sql
-- be/migrations/021_credit_holds.sql
-- Reserve credits without moving them.
--
-- A trial must not debit the wallet on day 0 (that is the whole point of a
-- trial), but the money must still be there on day 7. Debiting and refunding
-- would move real money and write two credit_ledger rows for a transaction
-- that never happened. A hold leaves credit_balance.balance untouched and
-- makes *available* balance the number every spending path must consult.
CREATE TABLE IF NOT EXISTS credit_holds (
  id             SERIAL PRIMARY KEY,
  user_id        INT NOT NULL,
  amount_credits INT NOT NULL CHECK (amount_credits > 0),
  reason         VARCHAR(40) NOT NULL,
  ref_type       VARCHAR(40) NOT NULL,
  ref_id         INT NOT NULL,
  status         VARCHAR(12) NOT NULL CHECK (status IN ('active', 'released', 'captured')),
  expires_at     TIMESTAMP NOT NULL,
  created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
  released_at    TIMESTAMP
);

-- One live reservation per thing being reserved for. Without this, a retried
-- request reserves twice and the user loses access to money nothing is owed on.
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_holds_active_ref
  ON credit_holds (ref_type, ref_id) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_credit_holds_user_active
  ON credit_holds (user_id) WHERE status = 'active';
```

- [ ] **Step 4: Write the runner**

```python
"""Run migration 021 on KNOWLEDGE_MARKET_DB (credit_holds)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql = (Path(__file__).resolve().parent / "021_credit_holds.sql").read_text(encoding="utf-8")
engine = create_engine(DB_URL)

with engine.begin() as conn:
    conn.execute(text(sql))
    cols = [r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'credit_holds' ORDER BY ordinal_position"""))]
    print("credit_holds columns:", cols)

    # The point of the migration: a second active hold on the same ref must be
    # impossible. Probe inside a savepoint so nothing is stored.
    savepoint = conn.begin_nested()
    try:
        for _ in range(2):
            conn.execute(text("""
                INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
                VALUES (-999, 1, 'probe', 'probe', -999, 'active', NOW())"""))
        print("double active hold: ACCEPTED — unique index missing")
        sys.exit(1)
    except Exception as exc:
        print(f"double active hold: rejected ({type(exc).__name__}) — as intended")
    finally:
        savepoint.rollback()
```

- [ ] **Step 5: Run the migration and the test**

Run: `python3 be/migrations/run_021.py && python3 -m pytest tests/subscription/test_credit_holds_schema.py -v`
Expected: runner prints "rejected ... as intended"; tests PASS.

- [ ] **Step 6: Commit**

```bash
git add be/migrations/021_credit_holds.sql be/migrations/run_021.py tests/subscription/test_credit_holds_schema.py
git commit -m "feat(wallet): credit_holds — reserve credits without moving them"
```

---

### Task 2: Available balance, and every spending path switched to it

**Files:**
- Modify: `be/services/credit.py` (add `get_available_balance`, `hold_credits`, `release_hold`, `capture_hold`; change the balance check in `purchase_product`)
- Modify: `be/services/subscription.py:185` and `:367` (balance checks)
- Modify: `be/routers/wallet.py:96-104` (report both numbers)
- Test: `tests/subscription/test_available_balance.py`

**Interfaces:**
- Consumes: `credit_holds` from Task 1.
- Produces:
  - `get_available_balance(user_id: int) -> int`
  - `get_wallet_state(user_id: int) -> dict` with keys `balance`, `held`, `available`
  - `hold_credits(conn, user_id, amount, reason, ref_type, ref_id, expires_at) -> int` (hold id; asserts availability under the caller's lock)
  - `release_hold(conn, hold_id) -> None`
  - `capture_hold(conn, hold_id) -> int` (amount captured)
  - `InsufficientCredits` keeps its existing name and meaning.

- [ ] **Step 1: Write the failing test**

```python
"""A hold must be invisible to the balance and fatal to a competing spend."""
import pytest
from services.credit import get_wallet_state, InsufficientCredits


def test_hold_reduces_available_but_not_balance(wallet_with_100_credits, hold_45):
    state = get_wallet_state(wallet_with_100_credits)
    assert state["balance"] == 100
    assert state["held"] == 45
    assert state["available"] == 55


def test_purchase_cannot_spend_held_credits(wallet_with_100_credits, hold_45):
    from services.credit import purchase_product
    with pytest.raises(InsufficientCredits):
        purchase_product(wallet_with_100_credits, "x@example.com", product_costing(60))


def test_purchase_can_spend_exactly_the_available_amount(wallet_with_100_credits, hold_45):
    from services.credit import purchase_product, get_wallet_state
    purchase_product(wallet_with_100_credits, "x@example.com", product_costing(55))
    assert get_wallet_state(wallet_with_100_credits)["available"] == 0


def test_released_hold_frees_the_credits(wallet_with_100_credits, hold_45):
    from services.credit import release_hold, get_wallet_state
    release_hold_by_id(hold_45)
    assert get_wallet_state(wallet_with_100_credits)["available"] == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_available_balance.py -v`
Expected: FAIL — `get_wallet_state` does not exist.

- [ ] **Step 3: Implement in `be/services/credit.py`**

```python
def _held_credits(conn, user_id: int) -> int:
    """Sum of live reservations. Expired holds do not count: a hold whose
    expires_at has passed was never captured, so the money is the user's
    again even if the cron that releases it has not run yet."""
    row = conn.execute(text("""
        SELECT COALESCE(SUM(amount_credits), 0) FROM credit_holds
        WHERE user_id = :u AND status = 'active' AND expires_at > NOW()
    """), {"u": user_id}).first()
    return int(row[0]) if row else 0


def get_wallet_state(user_id: int) -> dict:
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        bal = conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u"), {"u": user_id}).first()
        balance = bal[0] if bal else 0
        held = _held_credits(conn, user_id)
        return {"balance": balance, "held": held, "available": balance - held}


def get_available_balance(user_id: int) -> int:
    return get_wallet_state(user_id)["available"]


def hold_credits(conn, user_id: int, amount: int, reason: str,
                 ref_type: str, ref_id: int, expires_at) -> int:
    """Reserve `amount`. Caller must already hold the credit_balance row lock,
    otherwise two concurrent holds can each see the full balance."""
    bal = conn.execute(text(
        "SELECT balance FROM credit_balance WHERE user_id = :u"), {"u": user_id}).first()
    balance = bal[0] if bal else 0
    available = balance - _held_credits(conn, user_id)
    if available < amount:
        raise InsufficientCredits(f"Insufficient credits: need {amount}, available {available}")
    return conn.execute(text("""
        INSERT INTO credit_holds (user_id, amount_credits, reason, ref_type, ref_id, status, expires_at)
        VALUES (:u, :a, :r, :rt, :ri, 'active', :e) RETURNING id
    """), {"u": user_id, "a": amount, "r": reason, "rt": ref_type,
           "ri": ref_id, "e": expires_at}).scalar()


def release_hold(conn, hold_id: int) -> None:
    """Idempotent: a hold already released or captured is left alone."""
    conn.execute(text("""
        UPDATE credit_holds SET status='released', released_at=NOW()
        WHERE id = :id AND status = 'active'
    """), {"id": hold_id})


def capture_hold(conn, hold_id: int) -> int:
    """Mark the reservation consumed and return its amount. The caller writes
    the credit_ledger row and decrements credit_balance — capture only closes
    the reservation, so a caller that forgets to debit is a visible bug rather
    than silently free money."""
    row = conn.execute(text("""
        UPDATE credit_holds SET status='captured', released_at=NOW()
        WHERE id = :id AND status = 'active' RETURNING amount_credits
    """), {"id": hold_id}).first()
    if row is None:
        raise ValueError(f"Hold {hold_id} is not active")
    return int(row[0])
```

- [ ] **Step 4: Switch the three spending checks**

In `be/services/credit.py` `purchase_product`, and `be/services/subscription.py` at both `SELECT balance ... FOR UPDATE` sites, replace the bare `balance` comparison with available balance:

```python
        balance_row = conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"
        ), {"u": user_id}).first()
        balance = balance_row[0] if balance_row else 0
        # Held credits are spoken for (a trial about to convert). Spending them
        # here would let the wallet fall below what the trial already promised.
        available = balance - _held_credits(conn, user_id)
        if available < price:
            raise InsufficientCredits(f"Insufficient credits: need {price}, available {available}")
```

- [ ] **Step 5: Report both numbers from the wallet endpoint**

In `be/routers/wallet.py`, replace the `get_balance` import and call with `get_wallet_state`, returning `balance`, `held`, `available` so the FE can say *why* a purchase is refused.

- [ ] **Step 6: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v && python3 -m pytest tests/ -q`
Expected: PASS, and no existing test regresses.

- [ ] **Step 7: Commit**

```bash
git add be/services/credit.py be/services/subscription.py be/routers/wallet.py tests/subscription/test_available_balance.py
git commit -m "feat(wallet): available balance = balance - active holds, on every spending path"
```

---

### Task 3: `trial_consents` table and the trial columns

**Files:**
- Create: `be/migrations/022_trial_consent.sql`
- Create: `be/migrations/run_022.py`
- Test: `tests/subscription/test_trial_schema.py`

**Interfaces:**
- Consumes: `platform_subscriptions` (migration 013), `credit_holds` (Task 1).
- Produces: `platform_subscriptions.trial_end TIMESTAMP NULL`, status value `'trialing'`; table `trial_consents (id, user_id, product_code, subscription_id, consented, amount_credits, amount_vnd, charge_on, consent_text, user_agent, created_at)`.

- [ ] **Step 1: Write the failing test**

```python
def test_trial_columns_exist(conn):
    cols = {r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'platform_subscriptions'"""))}
    assert "trial_end" in cols


def test_trialing_is_an_allowed_status(conn):
    conn.execute(text("""
        INSERT INTO platform_products (code, name, price_credits, billing_period_days, active)
        VALUES ('probe-product', 'probe', 45, 30, false) ON CONFLICT DO NOTHING"""))
    conn.execute(text("""
        INSERT INTO platform_subscriptions (user_id, product_code, status, current_period_end, trial_end)
        VALUES (-3, 'probe-product', 'trialing', NOW() + interval '7 days', NOW() + interval '7 days')"""))


def test_consent_row_records_the_exact_promise(conn):
    cols = {r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'trial_consents'"""))}
    assert {"user_id", "product_code", "subscription_id", "consented",
            "amount_credits", "amount_vnd", "charge_on", "consent_text",
            "created_at"} <= cols


def test_consent_rows_cannot_be_updated(conn):
    conn.execute(text("""
        INSERT INTO trial_consents (user_id, product_code, subscription_id, consented,
                                    amount_credits, amount_vnd, charge_on, consent_text)
        VALUES (-4, 'probe-product', -4, true, 45, 45000, NOW() + interval '7 days', 'x')"""))
    with pytest.raises(Exception):
        conn.execute(text("UPDATE trial_consents SET consented = false WHERE user_id = -4"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_trial_schema.py -v`
Expected: FAIL — no `trial_end`, no `trial_consents`.

- [ ] **Step 3: Write the migration**

```sql
-- be/migrations/022_trial_consent.sql
-- A 7-day trial of a wallet-billed plan, and the record of the customer
-- agreeing to be charged when it ends.

ALTER TABLE platform_subscriptions ADD COLUMN IF NOT EXISTS trial_end TIMESTAMP;

-- What the customer actually agreed to, captured at the moment they agreed.
--
-- Deliberately NOT a boolean column on platform_subscriptions: that row is
-- overwritten on every resubscribe, and the question this table answers —
-- "did this person permit this charge, when, and for how much?" — is about a
-- past moment, not current state. Append-only, enforced by a trigger, because
-- a consent record that can be edited is not evidence.
CREATE TABLE IF NOT EXISTS trial_consents (
  id              SERIAL PRIMARY KEY,
  user_id         INT NOT NULL,
  product_code    VARCHAR(60) NOT NULL,
  subscription_id INT,
  consented       BOOLEAN NOT NULL,
  amount_credits  INT NOT NULL,
  amount_vnd      INT NOT NULL,
  charge_on       TIMESTAMP NOT NULL,
  consent_text    TEXT NOT NULL,
  user_agent      TEXT,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trial_consents_user ON trial_consents (user_id, created_at DESC);

CREATE OR REPLACE FUNCTION trial_consents_append_only() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'trial_consents is append-only (attempted %)', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_trial_consents_append_only ON trial_consents;
CREATE TRIGGER trg_trial_consents_append_only
  BEFORE UPDATE OR DELETE ON trial_consents
  FOR EACH ROW EXECUTE FUNCTION trial_consents_append_only();

-- The API plan as a wallet-billed platform product. 45 credits = 45.000đ at
-- VND_PER_CREDIT = 1000. Seeded active: unlike fuel-forecast there is no legal
-- review gating this one, it is the plan already on sale through PayOS.
INSERT INTO platform_products (code, name, price_credits, list_price_credits, billing_period_days, active)
VALUES ('api-supper-lite', 'API Supper Lite', 45, NULL, 30, true)
ON CONFLICT (code) DO NOTHING;
```

- [ ] **Step 4: Write the runner**

Copy `run_021.py`, point it at `022_trial_consent.sql`, and make its probe the
append-only guarantee: insert a consent row inside a savepoint, attempt an
`UPDATE`, assert it raises, roll back.

- [ ] **Step 5: Run the migration and tests**

Run: `python3 be/migrations/run_022.py && python3 -m pytest tests/subscription/test_trial_schema.py -v`
Expected: runner prints the rejection; tests PASS.

- [ ] **Step 6: Commit**

```bash
git add be/migrations/022_trial_consent.sql be/migrations/run_022.py tests/subscription/test_trial_schema.py
git commit -m "feat(trial): trial_end column, append-only trial_consents, api-supper-lite product"
```

---

### Task 4: `start_trial()` — the balance rule, the hold, the consent

**Files:**
- Modify: `be/services/subscription.py`
- Test: `tests/subscription/test_start_trial.py`

**Interfaces:**
- Consumes: `hold_credits`, `get_wallet_state` (Task 2); `trial_consents`, `trial_end` (Task 3).
- Produces: `start_trial(user_id, product_code, consented, consent_text, user_agent=None) -> dict` returning `{subscription_id, status, trial_end, charge_on, hold_id, amount_credits, amount_vnd, charged: False}`; raises `ConsentRequired`, `InsufficientCredits`, `TrialAlreadyUsed`.

- [ ] **Step 1: Write the failing test**

```python
def test_refuses_without_consent(user_with_credits):
    with pytest.raises(ConsentRequired):
        start_trial(user_with_credits, "api-supper-lite", consented=False, consent_text="x")


def test_refuses_when_wallet_below_one_month(user_with_credits_44):
    with pytest.raises(InsufficientCredits) as e:
        start_trial(user_with_credits_44, "api-supper-lite", consented=True, consent_text="x")
    # The message must carry the shortfall: the UI prints it verbatim.
    assert "45" in str(e.value) and "44" in str(e.value)


def test_does_not_charge_at_start(user_with_credits):
    before = get_wallet_state(user_with_credits)["balance"]
    start_trial(user_with_credits, "api-supper-lite", consented=True, consent_text="x")
    after = get_wallet_state(user_with_credits)
    assert after["balance"] == before      # no money moved
    assert after["held"] == 45             # but it is reserved
    assert after["available"] == before - 45


def test_records_consent_with_the_exact_amount_and_date(user_with_credits, conn):
    res = start_trial(user_with_credits, "api-supper-lite", consented=True,
                      consent_text="Tôi đồng ý bị trừ 45.000đ khi hết dùng thử")
    row = conn.execute(text("""
        SELECT consented, amount_credits, amount_vnd, charge_on, consent_text
        FROM trial_consents WHERE user_id = :u"""), {"u": user_with_credits}).first()
    assert row[0] is True and row[1] == 45 and row[2] == 45000
    assert row[3] == res["charge_on"]
    assert "45.000đ" in row[4]


def test_second_trial_is_refused(user_with_credits):
    start_trial(user_with_credits, "api-supper-lite", consented=True, consent_text="x")
    with pytest.raises(TrialAlreadyUsed):
        start_trial(user_with_credits, "api-supper-lite", consented=True, consent_text="x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_start_trial.py -v`
Expected: FAIL — `start_trial` does not exist.

- [ ] **Step 3: Implement**

```python
TRIAL_DAYS = 7


class ConsentRequired(Exception):
    pass


class TrialAlreadyUsed(Exception):
    pass


def start_trial(user_id: int, product_code: str, *, consented: bool,
                consent_text: str, user_agent: str | None = None) -> dict:
    """Begin a trial: reserve one period's price, charge nothing, record consent.

    The order inside the transaction matters. Consent is checked before the
    wallet is touched, and the hold is taken before the subscription row is
    written, so a wallet that cannot cover the charge leaves no trace at all.
    """
    if not consented:
        raise ConsentRequired("Cần tích xác nhận cho phép trừ tiền khi hết dùng thử.")

    engine = get_engine_knowledge()
    with engine.begin() as conn:
        product = _get_product(conn, product_code)
        price = product["price_credits"]
        now = datetime.utcnow()
        trial_end = now + timedelta(days=TRIAL_DAYS)

        existing = conn.execute(text("""
            SELECT id, status FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p FOR UPDATE
        """), {"u": user_id, "p": product_code}).first()
        # One trial per person per product, ever. The consent log is the
        # authority rather than the subscription row, which resubscribing
        # overwrites.
        used = conn.execute(text("""
            SELECT 1 FROM trial_consents
            WHERE user_id = :u AND product_code = :p AND consented LIMIT 1
        """), {"u": user_id, "p": product_code}).first()
        if used or (existing and existing[1] in ("trialing", "active")):
            raise TrialAlreadyUsed("Tài khoản này đã dùng thử gói trên rồi.")

        conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"), {"u": user_id})

        if existing:
            sub_id = existing[0]
            conn.execute(text("""
                UPDATE platform_subscriptions
                SET status='trialing', trial_end=:te, current_period_end=:te,
                    grace_until=NULL, cancelled_at=NULL, cancel_at_period_end=false
                WHERE id = :id"""), {"te": trial_end, "id": sub_id})
        else:
            sub_id = conn.execute(text("""
                INSERT INTO platform_subscriptions (user_id, product_code, status,
                                                    current_period_end, trial_end, cancel_at_period_end)
                VALUES (:u, :p, 'trialing', :te, :te, false) RETURNING id
            """), {"u": user_id, "p": product_code, "te": trial_end}).scalar()

        hold_id = hold_credits(conn, user_id, price, "trial", "subscription",
                               sub_id, trial_end)

        conn.execute(text("""
            INSERT INTO trial_consents (user_id, product_code, subscription_id, consented,
                                        amount_credits, amount_vnd, charge_on, consent_text, user_agent)
            VALUES (:u, :p, :sid, true, :ac, :av, :co, :ct, :ua)
        """), {"u": user_id, "p": product_code, "sid": sub_id, "ac": price,
               "av": price * VND_PER_CREDIT, "co": trial_end,
               "ct": consent_text, "ua": user_agent})

        _write_event(conn, sub_id, "trial_started", amount_credits=0,
                     note=f"Hold {price} credits until {trial_end.isoformat()}")

        state = get_wallet_state(user_id)
        return {"subscription_id": sub_id, "status": "trialing",
                "trial_end": trial_end, "charge_on": trial_end,
                "hold_id": hold_id, "amount_credits": price,
                "amount_vnd": price * VND_PER_CREDIT, "charged": False,
                "wallet": state}
```

- [ ] **Step 4: Widen the event vocabulary**

`platform_subscription_events.event_type` gains `trial_started`, `trial_converted`, `trial_cancelled`. Add them to the docstring list in `be/services/subscription.py` and to `fe/pages/fuel-forecast.html`'s Vietnamese label map so an unknown event never renders as a raw English token.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add be/services/subscription.py tests/subscription/test_start_trial.py
git commit -m "feat(trial): start_trial reserves one period, charges nothing, records consent"
```

---

### Task 5: Converting the trial in `run_billing_cycle`

**Files:**
- Modify: `be/services/subscription.py` (`_decide_renewal`, the cycle body)
- Test: `tests/subscription/test_trial_conversion.py`

**Interfaces:**
- Consumes: `capture_hold`, `release_hold` (Task 2); `start_trial` (Task 4).
- Produces: `_decide_renewal` returns the new action `"convert_trial"`; `run_billing_cycle` reports `converted` in its summary dict.

- [ ] **Step 1: Write the failing test**

```python
def test_trial_not_yet_over_is_left_alone():
    assert _decide_renewal("trialing", FUTURE, None, trial_end=FUTURE, now=NOW) == "skip"


def test_trial_that_ended_converts():
    assert _decide_renewal("trialing", PAST, None, trial_end=PAST, now=NOW) == "convert_trial"


def test_conversion_captures_the_hold_and_charges_exactly_once(trialing_user):
    run_billing_cycle(now=AFTER_TRIAL)
    state = get_wallet_state(trialing_user)
    assert state["balance"] == 100 - 45      # charged
    assert state["held"] == 0                # reservation consumed
    run_billing_cycle(now=AFTER_TRIAL)       # cron fired twice the same day
    assert get_wallet_state(trialing_user)["balance"] == 100 - 45   # not twice


def test_conversion_extends_thirty_days_from_trial_end(trialing_user, conn):
    run_billing_cycle(now=AFTER_TRIAL)
    row = conn.execute(text("""
        SELECT status, current_period_end, trial_end FROM platform_subscriptions
        WHERE user_id = :u"""), {"u": trialing_user}).first()
    assert row[0] == "active"
    assert row[1] == row[2] + timedelta(days=30)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_trial_conversion.py -v`
Expected: FAIL — `_decide_renewal` has no `trial_end` parameter.

- [ ] **Step 3: Implement the decision and the action**

```python
def _decide_renewal(status, current_period_end, grace_until, *, trial_end=None, now):
    if status == "trialing":
        # A trial converts on its own end date, not on current_period_end,
        # which start_trial deliberately set to the same instant — keeping the
        # two separate means a later change to one cannot silently move the
        # charge date.
        return "convert_trial" if trial_end and trial_end <= now else "skip"
    ...  # existing branches unchanged
```

```python
        if action == "convert_trial":
            hold = conn.execute(text("""
                SELECT id, amount_credits FROM credit_holds
                WHERE ref_type='subscription' AND ref_id=:sid AND status='active'
                FOR UPDATE
            """), {"sid": sub_id}).first()
            if hold is None:
                # Already converted by an earlier pass today. Nothing to do —
                # this is what makes a second cron run in the same day safe.
                continue
            hold_id, amount = hold
            capture_hold(conn, hold_id)
            period_end = trial_end + timedelta(days=period_days)
            conn.execute(text("""
                INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
                VALUES (:u, :a, 'subscription_charge', 'subscription', :sid, :k, :n)
            """), {"u": user_id, "a": -amount, "sid": sub_id,
                   "k": f"trial_convert:{sub_id}", "n": f"Trial converted {product_code}"})
            conn.execute(text("""
                UPDATE credit_balance SET balance = balance - :a, updated_at = NOW()
                WHERE user_id = :u"""), {"a": amount, "u": user_id})
            conn.execute(text("""
                UPDATE platform_subscriptions
                SET status='active', current_period_end=:pe WHERE id=:id
            """), {"pe": period_end, "id": sub_id})
            _write_event(conn, sub_id, "trial_converted", amount_credits=amount)
```

The `idem_key` is `trial_convert:<sub_id>` with no timestamp: a trial converts
exactly once, so the ledger's unique index on `idem_key` is a second, independent
guard against a double charge.

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add be/services/subscription.py tests/subscription/test_trial_conversion.py
git commit -m "feat(trial): convert trialing subscriptions by capturing the hold"
```

---

### Task 6: Granting and repairing the API entitlement across two databases

**Files:**
- Create: `be/services/api_entitlement.py`
- Modify: `be/services/subscription.py` (call it after the wallet commits)
- Test: `tests/subscription/test_api_entitlement.py`

**Interfaces:**
- Consumes: `platform_subscriptions` rows (Tasks 4–5).
- Produces: `sync_api_entitlement(user_id: int, until: datetime | None) -> dict` — sets `users.current_plan`, `users.premium_expiry`, `users.user_level` in `USER_DB`; `until=None` downgrades to free. Idempotent by assignment, never by increment.

- [ ] **Step 1: Write the failing test**

```python
def test_grant_sets_expiry_to_the_given_instant(user_row):
    sync_api_entitlement(user_row, until=TRIAL_END)
    assert read_user(user_row)["premium_expiry"] == TRIAL_END
    assert read_user(user_row)["user_level"] == "premium_developer"


def test_calling_twice_does_not_extend(user_row):
    sync_api_entitlement(user_row, until=TRIAL_END)
    sync_api_entitlement(user_row, until=TRIAL_END)
    assert read_user(user_row)["premium_expiry"] == TRIAL_END


def test_none_downgrades_to_free(user_row):
    sync_api_entitlement(user_row, until=TRIAL_END)
    sync_api_entitlement(user_row, until=None)
    assert read_user(user_row)["user_level"] == "free"
    assert read_user(user_row)["current_plan"] is None


def test_cron_repairs_a_subscription_whose_entitlement_never_landed(trialing_user):
    # Simulate the crash window: wallet side committed, USER_DB write lost.
    clear_entitlement(trialing_user)
    run_billing_cycle(now=DURING_TRIAL)
    assert read_user(trialing_user)["user_level"] == "premium_developer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_api_entitlement.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement**

```python
"""Grant the API tier that a wallet-billed subscription entitles a user to.

The wallet lives in KNOWLEDGE_MARKET_DB and users.premium_expiry in USER_DB, so
these two writes cannot share a transaction. The wallet always commits first:
a user holding a reservation with no entitlement is repaired by the next cron
pass, whereas an entitlement with no reservation is money given away.

Every write is an assignment, never an increment, so re-running it is free.
"""
from datetime import datetime

from sqlalchemy import text

from core.engines import get_engine_user

TRIAL_PLAN = "api-supper-lite"


def sync_api_entitlement(user_id: int, until: datetime | None) -> dict:
    engine = get_engine_user()
    with engine.begin() as conn:
        if until is None:
            conn.execute(text("""
                UPDATE users SET current_plan = NULL, premium_expiry = NULL,
                       user_level = 'free', updated_at = NOW()
                WHERE user_id = :u AND user_level <> 'admin'
            """), {"u": user_id})
            return {"user_level": "free", "premium_expiry": None}
        conn.execute(text("""
            UPDATE users SET current_plan = :p, premium_expiry = :e,
                   user_level = 'premium_developer', updated_at = NOW()
            WHERE user_id = :u AND user_level <> 'admin'
        """), {"u": user_id, "p": TRIAL_PLAN, "e": until})
        return {"user_level": "premium_developer", "premium_expiry": until}
```

`user_level <> 'admin'` is not defensive clutter: the admin account carries a
`current_plan` today, and an entitlement sync that demoted it would silently cap
an unlimited account.

- [ ] **Step 4: Call it, and make the cron repair drift**

After `start_trial` returns, call `sync_api_entitlement(user_id, trial_end)`.
After a conversion, call it with the new `current_period_end`. In
`run_billing_cycle`, for every `trialing` or `active` row whose period has not
ended, call it unconditionally — that single line is what heals a lost write.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add be/services/api_entitlement.py be/services/subscription.py tests/subscription/test_api_entitlement.py
git commit -m "feat(trial): sync API entitlement across the wallet/user database split"
```

---

### Task 7: Cancelling during the trial

**Files:**
- Modify: `be/services/subscription.py` (`cancel_subscription`)
- Test: `tests/subscription/test_trial_cancel.py`

**Interfaces:**
- Consumes: `release_hold` (Task 2), `sync_api_entitlement` (Task 6).
- Produces: `cancel_subscription` handles `status='trialing'` by releasing the hold and cancelling immediately.

- [ ] **Step 1: Write the failing test**

```python
def test_cancelling_a_trial_releases_the_hold_immediately(trialing_user):
    cancel_subscription(trialing_user, "api-supper-lite")
    state = get_wallet_state(trialing_user)
    assert state["held"] == 0
    assert state["available"] == state["balance"]


def test_cancelled_trial_is_never_charged(trialing_user):
    cancel_subscription(trialing_user, "api-supper-lite")
    before = get_wallet_state(trialing_user)["balance"]
    run_billing_cycle(now=AFTER_TRIAL)
    assert get_wallet_state(trialing_user)["balance"] == before


def test_cancelling_a_trial_ends_access_now_not_at_period_end(trialing_user):
    # A paid period is honoured to its end because it was paid for. A trial was
    # not, so there is nothing to honour.
    cancel_subscription(trialing_user, "api-supper-lite")
    assert has_active_subscription(trialing_user, "api-supper-lite") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_trial_cancel.py -v`
Expected: FAIL — cancel treats `trialing` like `active` and schedules for period end.

- [ ] **Step 3: Implement the branch**

```python
        if status == "trialing":
            hold = conn.execute(text("""
                SELECT id FROM credit_holds
                WHERE ref_type='subscription' AND ref_id=:sid AND status='active' FOR UPDATE
            """), {"sid": sub_id}).first()
            if hold:
                release_hold(conn, hold[0])
            conn.execute(text("""
                UPDATE platform_subscriptions
                SET status='cancelled', cancelled_at=NOW(), cancel_at_period_end=false
                WHERE id=:id"""), {"id": sub_id})
            _write_event(conn, sub_id, "trial_cancelled")
            return {"status": "cancelled", "hold_released": bool(hold),
                    "access_until": None}
```

- [ ] **Step 4: Downgrade the entitlement**

After the wallet transaction commits, call `sync_api_entitlement(user_id, None)`.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add be/services/subscription.py tests/subscription/test_trial_cancel.py
git commit -m "feat(trial): cancelling a trial releases the hold and ends access now"
```

---

### Task 8: HTTP endpoints

**Files:**
- Modify: `be/routers/subscription.py`
- Test: `tests/subscription/test_trial_routes.py`

**Interfaces:**
- Consumes: Tasks 4–7.
- Produces:
  - `GET  /api/v1/subscriptions/trial-eligibility?product_code=` → `{eligible, reason, required_credits, required_vnd, wallet:{balance,held,available}, shortfall_vnd, trial_days, charge_on}`
  - `POST /api/v1/subscriptions/trial` body `{product_code, consented, consent_text}` → 200, or **409** `TrialAlreadyUsed`, **402** `InsufficientCredits` with `shortfall_vnd`, **400** `ConsentRequired`.

- [ ] **Step 1: Write the failing test**

```python
def test_eligibility_reports_the_shortfall_in_vnd(client, user_with_20_credits):
    r = client.get("/api/v1/subscriptions/trial-eligibility?product_code=api-supper-lite")
    body = r.json()
    assert body["eligible"] is False
    assert body["required_vnd"] == 45000
    assert body["shortfall_vnd"] == 25000     # 45.000 - 20.000


def test_post_without_consent_is_400(client, user_with_credits):
    r = client.post("/api/v1/subscriptions/trial",
                    json={"product_code": "api-supper-lite", "consented": False,
                          "consent_text": "x"})
    assert r.status_code == 400


def test_post_with_thin_wallet_is_402_and_names_the_gap(client, user_with_20_credits):
    r = client.post("/api/v1/subscriptions/trial",
                    json={"product_code": "api-supper-lite", "consented": True,
                          "consent_text": "x"})
    assert r.status_code == 402
    assert r.json()["detail"]["shortfall_vnd"] == 25000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/subscription/test_trial_routes.py -v`
Expected: FAIL — 404, routes do not exist.

- [ ] **Step 3: Implement the routes**

Mirror the existing `subscribe`/`cancel` handlers in `be/routers/subscription.py`:
required auth via `middleware.authenticate_user`, map `ConsentRequired` → 400,
`InsufficientCredits` → 402 with a `detail` object carrying `required_vnd`,
`available_vnd` and `shortfall_vnd`, and `TrialAlreadyUsed` → 409. The consent
text sent by the client is stored verbatim; the server does not invent it,
because the record must say what the customer actually saw.

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/subscription/ -v && python3 -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add be/routers/subscription.py tests/subscription/test_trial_routes.py
git commit -m "feat(trial): trial-eligibility and trial endpoints"
```

---

### Task 9: The pricing-page UI

**Files:**
- Modify: `fe/pages/pricing.html`
- Test: `tests/journey/trial_checkout.test.cjs`

**Interfaces:**
- Consumes: Task 8's two endpoints.
- Produces: a "Dùng thử 7 ngày" control with a consent checkbox, disabled until both the wallet check passes and the box is ticked.

- [ ] **Step 1: Write the failing test**

```javascript
// Headless Chrome, stubbed /api/v1/subscriptions/*, in the style of
// tests/journey/admin_tabs.test.cjs.
assert.equal(await text('#trial-shortfall'),
  'Ví của bạn có 20.000đ. Cần tối thiểu 45.000đ để bắt đầu dùng thử — nạp thêm 25.000đ.');
assert.equal(await prop('#btn-start-trial', 'disabled'), true);
// tick the box with a sufficient wallet
assert.equal(await prop('#btn-start-trial', 'disabled'), false);
assert.equal(await text('#trial-consent-label'),
  'Tôi đồng ý cho Viet Dataverse trừ 45.000đ từ ví vào ngày 04/10/2026, khi hết 7 ngày dùng thử.');
assert.equal(consoleErrors.length, 0);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/journey/trial_checkout.test.cjs`
Expected: FAIL — no `#btn-start-trial`.

- [ ] **Step 3: Build the block**

```html
<div class="trial-box" id="trial-box" hidden>
  <h3>Dùng thử 7 ngày</h3>
  <p id="trial-explain">
    Không trừ tiền hôm nay. Chúng tôi <strong>tạm khoá 45.000đ</strong> trong ví
    của bạn trong 7 ngày để đảm bảo đủ tiền khi hết hạn — số tiền này vẫn là của
    bạn và sẽ được trả lại ngay nếu bạn huỷ trước ngày <span id="trial-charge-on"></span>.
  </p>
  <p id="trial-shortfall" class="trial-warning" hidden></p>
  <label id="trial-consent-label">
    <input type="checkbox" id="trial-consent">
    <span></span>
  </label>
  <button id="btn-start-trial" class="btn-data-primary" disabled>Bắt đầu dùng thử</button>
</div>
```

The consent sentence is built in JS from the endpoint's own `amount_vnd` and
`charge_on` so the text stored in `trial_consents` is the text the customer read.
Format VND with `toLocaleString('vi-VN')` and the date as `DD/MM/YYYY` read from
the ISO prefix as text, not `new Date()` — the existing fuel-forecast page
documents why parsing these server dates as local time shifts the displayed day.

- [ ] **Step 4: Run the test**

Run: `node tests/journey/trial_checkout.test.cjs`
Expected: PASS, 0 console errors.

- [ ] **Step 5: Commit**

```bash
git add fe/pages/pricing.html tests/journey/trial_checkout.test.cjs
git commit -m "feat(trial): pricing page trial box with wallet check and consent"
```

---

### Task 10: Ship it — cron, docs, deploy

**Files:**
- Modify: `.github/workflows/subscription-billing.yml`
- Modify: `CLAUDE.md`, `BACKLOG.md`, `docs/open-data-journey.md`
- Modify: `.claude/rules/DESIGN.md` §13.6

- [ ] **Step 1: Confirm the cron actually runs**

`CLAUDE.md` records that `subscription-billing.yml` was **never merged**, blocked
on the `KNOWLEDGE_MARKET_DB` repo secret. Check with `gh secret list`. Without
this cron **no trial ever converts** — verify before claiming the feature ships.

- [ ] **Step 2: Document**

In `CLAUDE.md`, under the platform-subscriptions section: the hold model, the
two-database ordering rule, one trial per user per product, and the fact that
`available = balance − active holds` is now what every spending path reads.

- [ ] **Step 3: Run everything**

Run: `python3 -m pytest tests/ -q && for t in tests/journey/*.cjs; do node "$t"; done`
Expected: all PASS.

- [ ] **Step 4: Commit, push, verify on prod**

```bash
git add -A && git commit -m "docs(trial): record the wallet-hold trial design and its constraints"
git push origin main
```

Then check `/api/v1/subscriptions/trial-eligibility` answers on prod and that the
billing workflow is listed by `gh workflow list`.
