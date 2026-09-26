"""Run migration 022 on KNOWLEDGE_MARKET_DB (trial columns + consent log)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql = (Path(__file__).resolve().parent / "022_trial_consent.sql").read_text(encoding="utf-8")
engine = create_engine(DB_URL)

with engine.begin() as conn:
    conn.execute(text(sql))
    print("platform_subscriptions.trial_end:", conn.execute(text("""
        SELECT data_type FROM information_schema.columns
        WHERE table_name='platform_subscriptions' AND column_name='trial_end'""")).scalar())
    print("trial_consents columns:", [r[0] for r in conn.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='trial_consents' ORDER BY ordinal_position"""))])
    print("api-supper-lite:", conn.execute(text("""
        SELECT code, price_credits, billing_period_days, active
        FROM platform_products WHERE code='api-supper-lite'""")).first())

    # The point of the migration: consent rows are evidence, so they must not
    # be editable. Probe inside a savepoint so nothing is stored.
    savepoint = conn.begin_nested()
    ok = False
    try:
        conn.execute(text("""
            INSERT INTO trial_consents (user_id, product_code, subscription_id, consented,
                                        amount_credits, amount_vnd, charge_on, consent_text)
            VALUES (-999, 'api-supper-lite', -999, true, 45, 45000, NOW(), 'probe')"""))
        conn.execute(text("UPDATE trial_consents SET consented=false WHERE user_id=-999"))
    except Exception as exc:
        ok = True
        print(f"UPDATE on trial_consents: rejected ({type(exc).__name__}) — as intended")
    finally:
        savepoint.rollback()
    if not ok:
        sys.exit("UPDATE on trial_consents: ACCEPTED — append-only trigger missing")

    savepoint = conn.begin_nested()
    ok = False
    try:
        conn.execute(text("""
            INSERT INTO trial_consents (user_id, product_code, subscription_id, consented,
                                        amount_credits, amount_vnd, charge_on, consent_text)
            VALUES (-998, 'api-supper-lite', -998, true, 45, 45000, NOW(), 'probe')"""))
        conn.execute(text("DELETE FROM trial_consents WHERE user_id=-998"))
    except Exception as exc:
        ok = True
        print(f"DELETE on trial_consents: rejected ({type(exc).__name__}) — as intended")
    finally:
        savepoint.rollback()
    if not ok:
        sys.exit("DELETE on trial_consents: ACCEPTED — append-only trigger missing")
