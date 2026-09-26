-- Migration 022: a 7-day trial of a wallet-billed plan, and the record of the
-- customer agreeing to be charged when it ends.

ALTER TABLE platform_subscriptions ADD COLUMN IF NOT EXISTS trial_end TIMESTAMP;

-- What the customer actually agreed to, captured at the moment they agreed.
--
-- Deliberately NOT a boolean column on platform_subscriptions: that row is
-- overwritten every time someone resubscribes, and the question this table
-- answers — "did this person permit this charge, when, and for how much?" —
-- is about a past moment, not current state. Append-only, enforced by a
-- trigger, because a consent record that can be edited is not evidence.
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
-- VND_PER_CREDIT = 1000 (be/services/credit.py). Seeded active: unlike
-- fuel-forecast there is no legal review gating this one — it is the plan
-- already on sale through PayOS, now also reachable as a trial.
INSERT INTO platform_products (code, name, price_credits, list_price_credits, billing_period_days, active)
VALUES ('api-supper-lite', 'API Supper Lite', 45, NULL, 30, true)
ON CONFLICT (code) DO NOTHING;
