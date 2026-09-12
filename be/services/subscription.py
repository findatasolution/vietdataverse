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

GRACE_PERIOD_DAYS = 2


class SubscriptionError(Exception):
    pass


def _decide_renewal(status: str, current_period_end: datetime, grace_until: datetime | None,
                    balance: int, price: int, billing_period_days: int,
                    now: datetime, cancel_at_period_end: bool) -> dict:
    """PURE. One decision for one subscription row during a billing-cycle pass.
    See docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md
    "run_billing_cycle" for the two-pass rationale (on-time renewal extends from
    the existing anchor date; a late reactivation buys a fresh period from now).

    `cancel_at_period_end` is only consulted on the 'active'-and-due branch —
    that is the exact moment a scheduled cancellation becomes due, and the whole
    point of the flag is "don't charge for the next period". It is deliberately
    NOT checked on the 'past_due' branch: a past_due row has no remaining paid
    period, so cancel_subscription() cancels it outright rather than scheduling
    (see that function), and a past_due row reactivated in time has the flag
    cleared by whichever path reactivates it.

    `cancel_at_period_end` has no default on purpose: forgetting to pass it
    would otherwise silently charge a user who asked to cancel."""
    if status == "cancelled":
        return {"action": "noop"}

    if status == "active":
        if current_period_end > now:
            return {"action": "noop"}
        if cancel_at_period_end:
            # No charge attempted, and no mark_past_due even if the wallet is
            # empty — the user asked to stop, so the period simply ends.
            return {
                "action": "expire",
                "event": "cancelled",
                "note": "Cancelled at period end as requested",
            }
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
    """Subscribe, reactivate, or undo a scheduled cancellation.

    Four cases, decided under the subscription row's own FOR UPDATE lock:

    1. No row, or status='cancelled'  -> new paid period from now ('created' +
       'charged').
    2. status='active', period still running, cancel_at_period_end=false ->
       ValueError; they are mid-period, there is nothing to buy.
    3. status='active', period still running, cancel_at_period_end=true -> undo
       the scheduled cancellation. NO CHARGE: the running period is already
       paid for. Returns charged=False.
    4. status='active' but current_period_end has already passed, or
       status='past_due' -> reactivation: charge and start a fresh period from
       now ('reactivated').

    Case 4's active-and-expired half exists because run_billing_cycle may never
    have run (the cron is not merged yet, see CLAUDE.md). Such a row reads
    'active' in the DB while has_active_subscription() correctly reports no
    entitlement — before this, subscribe() rejected it as "already subscribed"
    and the user had no way out except a manual DB fix.

    Raises InsufficientCredits if the wallet can't cover the charge (cases 1
    and 4 only)."""
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        product = _get_product(conn, product_code)
        price = product["price_credits"]
        period_days = product["billing_period_days"]

        existing = conn.execute(text("""
            SELECT id, status, current_period_end, cancel_at_period_end
            FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p FOR UPDATE
        """), {"u": user_id, "p": product_code}).first()

        now = datetime.utcnow()

        if existing:
            sub_id, ex_status, ex_period_end, ex_cancel_at_end = existing
            if ex_status == "active" and ex_period_end > now:
                if not ex_cancel_at_end:
                    raise ValueError(f"Already subscribed (status={ex_status})")
                # Case 3 — "keep my subscription after all". Money must not
                # move here: the period they are standing in is already paid.
                conn.execute(text("""
                    UPDATE platform_subscriptions SET cancel_at_period_end = false
                    WHERE id = :id
                """), {"id": sub_id})
                _write_event(conn, sub_id, "cancel_undone",
                             note="User resumed subscription before period end")
                balance_row = conn.execute(text(
                    "SELECT balance FROM credit_balance WHERE user_id = :u"
                ), {"u": user_id}).first()
                return {"subscription_id": sub_id, "status": "active",
                        "current_period_end": ex_period_end,
                        "cancel_at_period_end": False, "charged": False,
                        "balance_after": balance_row[0] if balance_row else 0}
            # Case 4: a cancelled row is a fresh signup ('created'); an expired
            # 'active' or a 'past_due' row is a reactivation, labelled the same
            # way run_billing_cycle labels its own past_due reactivation.
            is_reactivation = ex_status in ("active", "past_due")
        else:
            sub_id = None
            is_reactivation = False

        balance_row = conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"
        ), {"u": user_id}).first()
        balance = balance_row[0] if balance_row else 0
        if balance < price:
            raise InsufficientCredits(f"Insufficient credits: need {price}, have {balance}")

        period_end = now + timedelta(days=period_days)

        if sub_id is not None:
            # cancel_at_period_end is reset unconditionally: a fresh paid period
            # must never silently inherit a cancellation the user scheduled
            # against the previous one.
            conn.execute(text("""
                UPDATE platform_subscriptions
                SET status='active', current_period_end=:pe, grace_until=NULL,
                    cancelled_at=NULL, cancel_at_period_end=false
                WHERE id = :id
            """), {"pe": period_end, "id": sub_id})
        else:
            sub_id = conn.execute(text("""
                INSERT INTO platform_subscriptions (user_id, product_code, status,
                                                    current_period_end, cancel_at_period_end)
                VALUES (:u, :p, 'active', :pe, false) RETURNING id
            """), {"u": user_id, "p": product_code, "pe": period_end}).scalar()

        # Second-granularity idem_key: a real collision would require two
        # charging subscribe() calls for the same (user, product) within the
        # same wall-clock second. The row lock above serialises them, and the
        # first one leaves the row active with current_period_end in the
        # future — so the second is rejected by the case-2 guard (or turned
        # into the no-charge case 3) before it ever reaches this INSERT.
        idem_key = f"subscription:{sub_id}:{int(now.timestamp())}"
        conn.execute(text("""
            INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
            VALUES (:u, :a, 'subscription_charge', 'subscription', :sid, :k, :n)
        """), {"u": user_id, "a": -price, "sid": sub_id, "k": idem_key,
               "n": f"{'Reactivate' if is_reactivation else 'Subscribe'} {product_code}"})
        conn.execute(text("""
            UPDATE credit_balance SET balance = balance - :a, updated_at = NOW() WHERE user_id = :u
        """), {"a": price, "u": user_id})

        if is_reactivation:
            _write_event(conn, sub_id, "reactivated", amount_credits=price)
        else:
            _write_event(conn, sub_id, "created")
            _write_event(conn, sub_id, "charged", amount_credits=price)

        return {"subscription_id": sub_id, "status": "active",
                "current_period_end": period_end,
                "cancel_at_period_end": False, "charged": True,
                "balance_after": balance - price}


def cancel_subscription(user_id: int, product_code: str) -> dict:
    """Cancel at the end of the already-paid period — access continues until
    current_period_end, and run_billing_cycle then expires the row instead of
    renewing it. No proration, no refund (settled product decision).

    The one case that still cancels *immediately* is a subscription with no
    paid time left to honour: a 'past_due' row (its period already lapsed and
    the renewal charge failed) or an 'active' row whose current_period_end has
    already passed. Neither grants entitlement today — has_active_subscription()
    returns False for both — so there is nothing to keep the user in, and
    scheduling instead would leave a past_due row eligible for the cron's
    reactivation charge, i.e. billing someone who just asked to stop.

    Idempotent: cancelling an already-cancelled subscription is a no-op."""
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        row = conn.execute(text("""
            SELECT id, status, current_period_end, cancel_at_period_end
            FROM platform_subscriptions
            WHERE user_id = :u AND product_code = :p FOR UPDATE
        """), {"u": user_id, "p": product_code}).first()
        if not row:
            raise ValueError("No subscription found")
        sub_id, status, period_end, already_scheduled = row
        if status == "cancelled":
            return {"status": "cancelled"}

        if status == "active" and period_end > datetime.utcnow():
            if not already_scheduled:
                conn.execute(text("""
                    UPDATE platform_subscriptions SET cancel_at_period_end = true
                    WHERE id = :id
                """), {"id": sub_id})
                # 'cancel_scheduled', not 'cancelled': the latter is reserved
                # for the moment the subscription actually ends, written by
                # run_billing_cycle's 'expire' action.
                _write_event(conn, sub_id, "cancel_scheduled",
                             note="User requested cancellation; effective at period end")
            return {"status": "active", "cancel_at_period_end": True,
                    "current_period_end": period_end}

        conn.execute(text("""
            UPDATE platform_subscriptions
            SET status='cancelled', cancelled_at=NOW() WHERE id = :id
        """), {"id": sub_id})
        _write_event(conn, sub_id, "cancelled",
                     note="Cancelled by user (no paid period remaining)")
        return {"status": "cancelled", "cancel_at_period_end": False,
                "current_period_end": period_end}


def get_subscription(user_id: int, product_code: str) -> dict | None:
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, status, current_period_end, grace_until, created_at, cancelled_at,
                   cancel_at_period_end, product_code
            FROM platform_subscriptions WHERE user_id = :u AND product_code = :p
        """), {"u": user_id, "p": product_code}).first()
    if not row:
        return None
    # product_code is echoed back because GET /me returns a *list* of these and
    # the rows were otherwise indistinguishable once more than one platform
    # product exists.
    return {
        "id": row[0], "status": row[1], "current_period_end": row[2],
        "grace_until": row[3], "created_at": row[4], "cancelled_at": row[5],
        "cancel_at_period_end": row[6], "product_code": row[7],
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
    Returns the action taken ('charge', 'mark_past_due', 'cancel', 'expire') or
    None for a noop / missing row. Raises on error (e.g. product deactivated
    while subscribers remain on it) — the caller isolates failures
    per-subscription so one stuck row can't block the rest of a
    run_billing_cycle() pass."""
    with engine.begin() as conn:
        sub = conn.execute(text("""
            SELECT id, user_id, product_code, status, current_period_end, grace_until,
                   cancel_at_period_end
            FROM platform_subscriptions WHERE id = :id FOR UPDATE
        """), {"id": sub_id}).first()
        if not sub:
            return None
        _, user_id, product_code, status, period_end, grace_until, cancel_at_period_end = sub
        product = _get_product(conn, product_code)

        balance_row = conn.execute(text(
            "SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"
        ), {"u": user_id}).first()
        balance = balance_row[0] if balance_row else 0

        decision = _decide_renewal(
            status=status, current_period_end=period_end, grace_until=grace_until,
            balance=balance, price=product["price_credits"],
            billing_period_days=product["billing_period_days"], now=now,
            cancel_at_period_end=bool(cancel_at_period_end),
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

        # 'cancel' (grace exhausted) and 'expire' (the user's scheduled
        # cancellation coming due) differ only in why they happened — the note
        # carries that — so they share one DB update rather than duplicating it.
        if decision["action"] in ("cancel", "expire"):
            conn.execute(text("""
                UPDATE platform_subscriptions SET status = 'cancelled', cancelled_at = :now
                WHERE id = :id
            """), {"now": now, "id": sub_id})
            _write_event(conn, sub_id, decision["event"], note=decision["note"])
            return decision["action"]

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

    # 'expire' (scheduled cancellation reaching its period end) counts as a
    # cancellation like 'cancel' (grace exhausted) — both end the subscription.
    action_to_count = {"charge": "renewed", "mark_past_due": "past_due",
                       "cancel": "cancelled", "expire": "cancelled"}

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
