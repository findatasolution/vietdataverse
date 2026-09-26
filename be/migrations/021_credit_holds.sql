-- Migration 021: reserve credits without moving them.
--
-- A trial must not debit the wallet on day 0 — that is the whole point of a
-- trial, and the product decision was explicit about not touching the
-- customer's money to reassure them. But the money must still be there on
-- day 7. Debiting then refunding would move real money and write two
-- credit_ledger rows for a transaction that never happened.
--
-- A hold leaves credit_balance.balance untouched and makes *available*
-- balance — balance minus live holds — the number every spending path must
-- consult. See docs/superpowers/specs/2026-09-27-api-trial-wallet-hold-design.md
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

-- One live reservation per thing being reserved for. Without this a retried
-- request reserves twice, and the customer loses access to money that nothing
-- is owed on — the exact failure a hold exists to prevent.
CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_holds_active_ref
  ON credit_holds (ref_type, ref_id) WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_credit_holds_user_active
  ON credit_holds (user_id) WHERE status = 'active';
