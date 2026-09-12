-- Migration 015: cancel-at-period-end for platform subscriptions.
-- Cancelling used to flip status straight to 'cancelled', revoking access the
-- instant the user clicked — even though they had already paid for the running
-- period and no refund/proration exists. Product decision: a cancellation is now
-- *scheduled*; the row keeps status='active' and its current_period_end, and the
-- daily billing cycle expires it (status='cancelled', event 'cancelled') when
-- that period end arrives instead of attempting a charge.
--
-- DEFAULT false is what makes this safe to apply to a live table: every existing
-- row keeps auto-renewing exactly as before, and NOT NULL means _decide_renewal
-- never has to treat NULL as a third state.

ALTER TABLE platform_subscriptions
    ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT false;
