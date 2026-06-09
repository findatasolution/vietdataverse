-- Migration 010: Add price_usd column to knowledge_products
-- Mirror-write: keep price_credits for backward-compat (1 release rollback window)
-- Conversion: $1 USD = 25,500 VND = 25.5 credits (1 credit = 1,000 VND)

ALTER TABLE knowledge_products
    ADD COLUMN IF NOT EXISTS price_usd NUMERIC(10,2) NOT NULL DEFAULT 0.00;

-- Backfill from price_credits where non-zero
-- price_credits * 1000 VND / 25500 per USD
UPDATE knowledge_products
SET price_usd = ROUND(price_credits * 1000.0 / 25500.0, 2)
WHERE price_credits > 0;
