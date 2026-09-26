"""Grant the API tier that a wallet-billed subscription entitles a user to.

The wallet lives in KNOWLEDGE_MARKET_DB and `users.premium_expiry` in USER_DB,
so these two writes cannot share a transaction. **The wallet always commits
first.** A user holding a reservation with no entitlement is repaired by the
next billing pass; an entitlement with no reservation is money given away.

Every write here is an assignment, never an increment, so re-running it is
free — which is what makes that repair possible.
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from core.engines import get_engine_user

logger = logging.getLogger(__name__)

TRIAL_PLAN = "api-supper-lite"
PAID_LEVEL = "premium_developer"


def sync_api_entitlement(user_id: int, until: Optional[datetime]) -> dict:
    """Set (or clear) the API tier for `user_id`.

    `until=None` downgrades to free. Admin accounts are never touched: the
    admin row carries a `current_plan` of its own, and demoting it would
    silently cap an account that is supposed to be unlimited.
    """
    engine = get_engine_user()
    try:
        with engine.begin() as conn:
            if until is None:
                conn.execute(text("""
                    UPDATE users
                    SET current_plan = NULL, premium_expiry = NULL, user_level = 'free'
                    WHERE user_id = :u AND user_level <> 'admin'
                """), {"u": user_id})
                return {"user_level": "free", "premium_expiry": None}

            conn.execute(text("""
                UPDATE users
                SET current_plan = :p, premium_expiry = :e, user_level = :lv
                WHERE user_id = :u AND user_level <> 'admin'
            """), {"u": user_id, "p": TRIAL_PLAN, "e": until, "lv": PAID_LEVEL})
            return {"user_level": PAID_LEVEL, "premium_expiry": until}
    except Exception as exc:
        # Never let this failure roll back the wallet write that already
        # committed. The next billing pass re-runs this for every live
        # subscription, so the drift is self-healing — but it must be visible
        # in the meantime, hence exc_info rather than a bare pass.
        logger.error("sync_api_entitlement failed for user %s: %s",
                     user_id, exc, exc_info=True)
        return {"error": str(exc)}
