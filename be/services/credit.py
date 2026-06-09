"""Credit ledger operations — atomic, idempotent."""
import secrets
from datetime import datetime, timedelta

from sqlalchemy import text

from core.engines import get_engine_knowledge

VND_PER_CREDIT = 1000


class InsufficientCredits(Exception):
    pass


class DuplicateTransaction(Exception):
    pass


def get_balance(user_id: int) -> int:
    """Return current credit balance for user. Returns 0 if no balance row exists."""
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT balance FROM credit_balance WHERE user_id = :u"),
            {"u": user_id},
        ).first()
        return row[0] if row else 0


def credit_topup(user_id: int, credits: int, idem_key: str, note: str = "PayOS topup") -> dict:
    """
    Credit buyer account after confirmed PayOS payment.
    Idempotent: same idem_key → skip insert, return current balance with duplicate=True.
    Returns: {"balance": int, "duplicate": bool}
    """
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        # Check idempotency first
        exists = conn.execute(
            text("SELECT 1 FROM credit_ledger WHERE idem_key = :k"),
            {"k": idem_key},
        ).first()
        if exists:
            current = conn.execute(
                text("SELECT balance FROM credit_balance WHERE user_id = :u"),
                {"u": user_id},
            ).first()
            return {"balance": current[0] if current else 0, "duplicate": True}

        # Insert ledger entry
        conn.execute(text("""
            INSERT INTO credit_ledger (user_id, amount, kind, idem_key, note)
            VALUES (:u, :a, 'topup', :k, :n)
        """), {"u": user_id, "a": credits, "k": idem_key, "n": note})

        # Upsert balance
        conn.execute(text("""
            INSERT INTO credit_balance (user_id, balance, updated_at)
            VALUES (:u, :a, NOW())
            ON CONFLICT (user_id) DO UPDATE
                SET balance    = credit_balance.balance + :a,
                    updated_at = NOW()
        """), {"u": user_id, "a": credits})

        new_bal = conn.execute(
            text("SELECT balance FROM credit_balance WHERE user_id = :u"),
            {"u": user_id},
        ).scalar()
        return {"balance": new_bal, "duplicate": False}


def purchase_product(buyer_id: int, buyer_email: str, product_id: int) -> dict:
    """
    Atomic purchase flow:
      1. Check no existing purchase (raises DuplicateTransaction).
      2. Lock & verify buyer balance (raises InsufficientCredits).
      3. Verify product is approved (raises ValueError).
      4. Debit buyer credit_ledger + credit_balance.
      5. Create knowledge_purchases row (license_key + refund_deadline).
      6. Credit seller_earnings (90% of price in VND).
    Returns: {"purchase_id": int, "license_key": str, "balance_after": int}
    """
    engine = get_engine_knowledge()
    license_key = secrets.token_urlsafe(48)
    idem_key = f"purchase:{buyer_id}:{product_id}:{int(datetime.utcnow().timestamp())}"

    with engine.begin() as conn:
        # Guard: no duplicate purchase
        existing = conn.execute(
            text("SELECT id FROM knowledge_purchases WHERE buyer_id = :b AND product_id = :p"),
            {"b": buyer_id, "p": product_id},
        ).first()
        if existing:
            raise DuplicateTransaction(f"Already purchased: purchase_id={existing[0]}")

        # Lock balance row
        balance_row = conn.execute(
            text("SELECT balance FROM credit_balance WHERE user_id = :u FOR UPDATE"),
            {"u": buyer_id},
        ).first()
        balance = balance_row[0] if balance_row else 0

        # Fetch product (must be live/approved/published — all mean publicly buyable)
        product = conn.execute(text("""
            SELECT price_credits, seller_id
            FROM knowledge_products
            WHERE id = :p AND status IN ('approved', 'published', 'live')
        """), {"p": product_id}).first()
        if not product:
            raise ValueError("Product not available for purchase")

        price, seller_pid = product[0], product[1]

        if balance < price:
            raise InsufficientCredits(f"Insufficient credits: need {price}, have {balance}")

        # Debit buyer
        conn.execute(text("""
            INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
            VALUES (:u, :a, 'purchase', 'product', :p, :k, 'Purchase product')
        """), {"u": buyer_id, "a": -price, "p": product_id, "k": idem_key})

        conn.execute(text("""
            UPDATE credit_balance
            SET balance = balance - :a, updated_at = NOW()
            WHERE user_id = :u
        """), {"u": buyer_id, "a": price})

        # Calc seller share: 90% of price converted to VND
        seller_share_vnd = int(price * VND_PER_CREDIT * 0.9)

        # Create purchase row
        purchase_id = conn.execute(text("""
            INSERT INTO knowledge_purchases
                (buyer_id, buyer_email_snapshot, product_id, seller_id,
                 credits_paid, seller_share_vnd, license_key, refund_deadline)
            VALUES (:b, :be, :p, :s, :c, :sv, :lk, NOW() + INTERVAL '1 hour')
            RETURNING id
        """), {
            "b":  buyer_id,
            "be": buyer_email,
            "p":  product_id,
            "s":  seller_pid,
            "c":  price,
            "sv": seller_share_vnd,
            "lk": license_key,
        }).scalar()

        # Resolve seller user_id from seller_profiles
        seller_user_id = conn.execute(
            text("SELECT user_id FROM seller_profiles WHERE id = :s"),
            {"s": seller_pid},
        ).scalar()

        # Credit seller earnings (upsert)
        conn.execute(text("""
            INSERT INTO seller_earnings (user_id, pending_vnd, updated_at)
            VALUES (:u, :a, NOW())
            ON CONFLICT (user_id) DO UPDATE
                SET pending_vnd = seller_earnings.pending_vnd + :a,
                    updated_at  = NOW()
        """), {"u": seller_user_id, "a": seller_share_vnd})

        return {
            "purchase_id":   purchase_id,
            "license_key":   license_key,
            "balance_after": balance - price,
        }


def refund_purchase(purchase_id: int, buyer_id: int) -> dict:
    """
    Cancel purchase within 1h window, restoring credits.
    Raises ValueError if: not found, already refunded, window expired, or file downloaded.
    Returns: {"refunded_credits": int}
    """
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        p = conn.execute(text("""
            SELECT product_id, seller_id, credits_paid, seller_share_vnd,
                   refund_deadline, status
            FROM knowledge_purchases
            WHERE id = :id AND buyer_id = :b
            FOR UPDATE
        """), {"id": purchase_id, "b": buyer_id}).first()

        if not p:
            raise ValueError("Purchase not found")
        if p[5] != "active":
            raise ValueError(f"Cannot refund — status is '{p[5]}'")
        if datetime.utcnow() > p[4]:
            raise ValueError("Refund window expired (1 hour)")

        # Block refund if already downloaded
        dl = conn.execute(
            text("SELECT 1 FROM knowledge_download_log WHERE purchase_id = :id LIMIT 1"),
            {"id": purchase_id},
        ).first()
        if dl:
            raise ValueError("Cannot refund — file already downloaded")

        idem = f"refund:{purchase_id}"
        credits_paid = p[2]
        seller_share = p[3]
        seller_pid = p[1]

        # Restore buyer credits via ledger
        conn.execute(text("""
            INSERT INTO credit_ledger (user_id, amount, kind, ref_type, ref_id, idem_key, note)
            VALUES (:u, :a, 'refund', 'purchase', :pid, :k, 'Refund within 1h window')
        """), {"u": buyer_id, "a": credits_paid, "pid": purchase_id, "k": idem})

        conn.execute(text("""
            UPDATE credit_balance
            SET balance = balance + :a, updated_at = NOW()
            WHERE user_id = :u
        """), {"u": buyer_id, "a": credits_paid})

        # Reverse seller earnings
        seller_user_id = conn.execute(
            text("SELECT user_id FROM seller_profiles WHERE id = :s"),
            {"s": seller_pid},
        ).scalar()

        conn.execute(text("""
            UPDATE seller_earnings
            SET pending_vnd = pending_vnd - :a, updated_at = NOW()
            WHERE user_id = :u
        """), {"u": seller_user_id, "a": seller_share})

        # Mark purchase refunded
        conn.execute(
            text("UPDATE knowledge_purchases SET status = 'refunded' WHERE id = :id"),
            {"id": purchase_id},
        )

        return {"refunded_credits": credits_paid}
