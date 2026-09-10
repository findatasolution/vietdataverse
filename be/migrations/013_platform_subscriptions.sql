-- be/migrations/013_platform_subscriptions.sql
-- Generic wallet-billed subscription primitive for VDV-owned "platform" data
-- products (as opposed to knowledge_products, which is the seller marketplace).
-- See docs/superpowers/specs/2026-09-10-fuel-forecast-subscription-design.md

CREATE TABLE IF NOT EXISTS platform_products (
  code                 VARCHAR(60) PRIMARY KEY,
  name                 TEXT NOT NULL,
  price_credits        INT NOT NULL,
  list_price_credits   INT,
  billing_period_days  INT NOT NULL DEFAULT 30,
  active               BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS platform_subscriptions (
  id                 SERIAL PRIMARY KEY,
  user_id            INT NOT NULL,
  product_code       VARCHAR(60) NOT NULL REFERENCES platform_products(code),
  status             VARCHAR(20) NOT NULL,
  current_period_end TIMESTAMP NOT NULL,
  grace_until        TIMESTAMP,
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  cancelled_at       TIMESTAMP,
  UNIQUE (user_id, product_code)
);
CREATE INDEX IF NOT EXISTS idx_platform_subs_status ON platform_subscriptions (status, current_period_end);

CREATE TABLE IF NOT EXISTS platform_subscription_events (
  id              SERIAL PRIMARY KEY,
  subscription_id INT NOT NULL REFERENCES platform_subscriptions(id),
  event_type      VARCHAR(20) NOT NULL,
  amount_credits  INT,
  note            TEXT,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_platform_sub_events_sub ON platform_subscription_events (subscription_id, created_at DESC);

INSERT INTO platform_products (code, name, price_credits, list_price_credits, billing_period_days, active)
VALUES ('fuel-forecast-advanced', 'Fuel Forecast — Advanced', 60, 120, 30, true)
ON CONFLICT (code) DO NOTHING;
