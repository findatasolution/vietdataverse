"""
Seller payout — admin-managed manual bank transfer.
Bank account details are NOT stored in DB.
Admin is emailed separately for each payout (out-of-band).

Flow:
  1. Admin calls list_pending_payouts() to see who is eligible.
  2. Admin calls create_payout(seller_user_id) → creates seller_payouts row,
     resets seller_earnings.pending_vnd to 0.
  3. Admin transfers money out-of-band, then calls mark_paid(payout_id).
  4. mark_paid moves amount to seller_earnings.paid_vnd.
"""
from sqlalchemy import text

from core.engines import get_engine_knowledge

MIN_PAYOUT_VND = 500_000  # 500,000 VND minimum to trigger payout eligibility


def list_pending_payouts() -> list[dict]:
    """
    Return sellers with pending_vnd >= MIN_PAYOUT_VND, sorted by amount descending.
    Each row includes seller identity fields for admin to initiate bank transfer.
    """
    engine = get_engine_knowledge()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT
                se.user_id,
                se.pending_vnd,
                sp.display_name,
                sp.user_email_snapshot,
                sp.linkedin_url
            FROM seller_earnings se
            JOIN seller_profiles sp ON sp.user_id = se.user_id
            WHERE se.pending_vnd >= :min
            ORDER BY se.pending_vnd DESC
        """), {"min": MIN_PAYOUT_VND}).fetchall()

        return [dict(r._mapping) for r in rows]


def create_payout(seller_user_id: int) -> int:
    """
    Snapshot seller's pending_vnd into seller_payouts, reset pending to 0.
    Returns payout_id (INTEGER SERIAL).
    Raises ValueError if seller has no pending earnings.
    """
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        # Lock row to prevent double-payout race
        row = conn.execute(text("""
            SELECT se.pending_vnd, sp.user_email_snapshot
            FROM seller_earnings se
            JOIN seller_profiles sp ON sp.user_id = se.user_id
            WHERE se.user_id = :u
            FOR UPDATE
        """), {"u": seller_user_id}).first()

        if not row or row[0] <= 0:
            raise ValueError(f"No pending earnings for seller user_id={seller_user_id}")

        amount_vnd = row[0]
        email = row[1]

        payout_id = conn.execute(text("""
            INSERT INTO seller_payouts (seller_id, seller_email_snapshot, amount_vnd)
            VALUES (:u, :e, :a)
            RETURNING id
        """), {"u": seller_user_id, "e": email, "a": amount_vnd}).scalar()

        # Reset pending (amount moves to payout row; paid_vnd updated on mark_paid)
        conn.execute(text("""
            UPDATE seller_earnings
            SET pending_vnd = 0, updated_at = NOW()
            WHERE user_id = :u
        """), {"u": seller_user_id})

        return payout_id


def mark_paid(payout_id: int, admin_note: str | None = None) -> dict:
    """
    Mark a payout row as paid and move amount into seller_earnings.paid_vnd.
    Raises ValueError if payout_id not found or already processed.
    Returns: {"seller_id": int, "amount_vnd": int}
    """
    engine = get_engine_knowledge()
    with engine.begin() as conn:
        row = conn.execute(text("""
            UPDATE seller_payouts
            SET status = 'paid', paid_at = NOW(), admin_note = :n
            WHERE id = :id AND status = 'pending'
            RETURNING seller_id, amount_vnd
        """), {"id": payout_id, "n": admin_note}).first()

        if not row:
            raise ValueError(f"Payout {payout_id} not found or not in pending status")

        seller_id, amount_vnd = row[0], row[1]

        # Accumulate paid total
        conn.execute(text("""
            UPDATE seller_earnings
            SET paid_vnd = paid_vnd + :a, updated_at = NOW()
            WHERE user_id = :u
        """), {"a": amount_vnd, "u": seller_id})

        return {"seller_id": seller_id, "amount_vnd": amount_vnd}
