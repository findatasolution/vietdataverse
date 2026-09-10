-- Migration 014: Allow 'subscription_charge' as a credit_ledger.kind value.
-- Task 1 (013_platform_subscriptions.sql) added platform_products/
-- platform_subscriptions/platform_subscription_events but did not touch
-- credit_ledger. Task 2's subscription.py (subscribe() and run_billing_cycle())
-- debits the wallet via credit_ledger with kind='subscription_charge', which the
-- original CHECK constraint (migration 004, topup/purchase/refund/admin_adjust
-- only) rejects. Same pattern as migration 008 (widened a CHECK the same way).

ALTER TABLE credit_ledger DROP CONSTRAINT IF EXISTS credit_ledger_kind_check;
ALTER TABLE credit_ledger ADD CONSTRAINT credit_ledger_kind_check
    CHECK (kind IN ('topup', 'purchase', 'refund', 'admin_adjust', 'subscription_charge'));
