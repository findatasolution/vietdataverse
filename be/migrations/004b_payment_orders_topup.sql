-- Migration 004b: Extend payment_orders for credit topup support
-- Target DB: USER_DB
-- Run once — idempotent (uses ADD COLUMN IF NOT EXISTS)

ALTER TABLE payment_orders
    ADD COLUMN IF NOT EXISTS order_type VARCHAR(20) NOT NULL DEFAULT 'subscription'
        CHECK (order_type IN ('subscription','credit_topup'));

ALTER TABLE payment_orders
    ADD COLUMN IF NOT EXISTS credit_amount INTEGER;
