"""Platform subscription billing — atomic, idempotent, same pattern as
be/services/credit.py's purchase_product(). New tables live in
KNOWLEDGE_MARKET_DB (same DB as credit_balance/credit_ledger), so a
subscription write and a wallet debit always share one transaction.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import text

from core.engines import get_engine_knowledge
from services.credit import InsufficientCredits

logger = logging.getLogger(__name__)

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

        # Second-granularity idem_key: a real collision would require two
        # subscribe() calls for the same (user, product) within the same
        # wall-clock second, but the `existing[1] in ("active", "past_due")`
        # guard above (taken under the same row lock) already rejects the
        # second call with ValueError before it reaches this INSERT.
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
    """Entitlement check. status='active' alone is NOT enough: run_billing_cycle
    only flips an unpaid row to 'past_due' on its next daily pass, so between
    current_period_end and that pass the row still reads 'active'. The period end
    is the real boundary — without this check a single payment would grant
    permanent access if the billing cron ever stopped running."""
    if user_id is None:
        return False
    sub = get_subscription(user_id, product_code)
    if not sub or sub["status"] != "active":
        return False
    period_end = sub["current_period_end"]
    return bool(period_end and period_end > datetime.utcnow())


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
    # created_at is a naive UTC timestamp in Postgres. Serialised with
    # json.dumps(default=str) it came out as "2026-09-11 03:11:00.123456" —
    # space-separated with no zone marker, which JS `new Date()` parses as LOCAL
    # time (7h off for a VN user) and some browsers reject outright. Emit
    # explicit ISO-8601 UTC instead.
    return [{
        "id": r[0], "event_type": r[1], "amount_credits": r[2], "note": r[3],
        "created_at": r[4].isoformat() + "Z" if r[4] is not None else None,
        "product_code": r[5],
    } for r in rows]


def _process_subscription(engine, sub_id: int, now: datetime) -> str | None:
    """Process one subscription's billing decision inside its own transaction.
    Returns the action taken ('charge', 'mark_past_due', 'cancel') or None for
    a noop / missing row. Raises on error (e.g. product deactivated while
    subscribers remain on it) — the caller isolates failures per-subscription
    so one stuck row can't block the rest of a run_billing_cycle() pass."""
    with engine.begin() as conn:
        sub = conn.execute(text("""
            SELECT id, user_id, product_code, status, current_period_end, grace_until
            FROM platform_subscriptions WHERE id = :id FOR UPDATE
        """), {"id": sub_id}).first()
        if not sub:
            return None
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
            return None

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
            return "charge"

        if decision["action"] == "mark_past_due":
            conn.execute(text("""
                UPDATE platform_subscriptions SET status = 'past_due', grace_until = :g
                WHERE id = :id
            """), {"g": decision["grace_until"], "id": sub_id})
            _write_event(conn, sub_id, decision["event"])
            return "mark_past_due"

        if decision["action"] == "cancel":
            conn.execute(text("""
                UPDATE platform_subscriptions SET status = 'cancelled', cancelled_at = :now
                WHERE id = :id
            """), {"now": now, "id": sub_id})
            _write_event(conn, sub_id, decision["event"], note=decision["note"])
            return "cancel"

        raise SubscriptionError(f"unknown _decide_renewal action: {decision['action']!r}")


def run_billing_cycle(now: datetime | None = None) -> dict:
    """Called by the daily cron. One short transaction per subscription — a
    stuck row must not block every other renewal, so each subscription's
    processing is isolated in its own try/except: a failure (e.g. a product
    deactivated while subscribers remain on it) is logged and skipped rather
    than aborting the whole run and leaving every later subscription in
    due_ids unprocessed."""
    now = now or datetime.utcnow()
    engine = get_engine_knowledge()
    counts = {"renewed": 0, "past_due": 0, "cancelled": 0}

    with engine.connect() as conn:
        # Only rows that can actually produce an action. An 'active' row whose
        # period hasn't ended yet is a guaranteed _decide_renewal noop, so it is
        # excluded here rather than loaded and discarded — this is the query
        # idx_platform_subs_status (status, current_period_end) exists for.
        # 'past_due' rows are always considered (their decision depends on
        # balance and grace_until, not on current_period_end). `now` is bound
        # from the caller's argument, not SQL NOW(), so run_billing_cycle stays
        # testable with an injected clock.
        due_ids = [r[0] for r in conn.execute(text("""
            SELECT id FROM platform_subscriptions
            WHERE (status = 'active' AND current_period_end <= :now)
               OR status = 'past_due'
        """), {"now": now}).fetchall()]

    action_to_count = {"charge": "renewed", "mark_past_due": "past_due", "cancel": "cancelled"}

    for sub_id in due_ids:
        try:
            action = _process_subscription(engine, sub_id, now)
        except Exception as e:
            logger.error("billing cycle: subscription %s failed: %s", sub_id, e)
            continue
        if action in action_to_count:
            counts[action_to_count[action]] += 1

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
