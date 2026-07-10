-- Schema for FUEL_FORECAST_DB (isolated Neon database for the fuel-forecast product).
-- Apply once:  psql "$FUEL_FORECAST_DB" -f be/fuel/schema.sql
-- Medallion Silver + params (Gold tables added in Plan 2).

-- Silver: one row per cycle (Thursday) per fuel — parsed from MOIT announcements.
CREATE TABLE IF NOT EXISTS fuel_price_cycle (
  id SERIAL PRIMARY KEY,
  period DATE NOT NULL,                          -- announcement/cycle date (Thu)
  fuel VARCHAR(12) NOT NULL,                     -- RON95 | E5RON92 | DO005S
  retail_price NUMERIC NOT NULL,                 -- VND/L
  base_price NUMERIC NOT NULL,                   -- VND/L
  world_avg_price NUMERIC NOT NULL,              -- USD/barrel
  bog_contrib NUMERIC NOT NULL DEFAULT 0,        -- VND/L (trích Quỹ BOG)
  bog_use NUMERIC NOT NULL DEFAULT 0,            -- VND/L (chi Quỹ BOG)
  taxes JSONB NOT NULL DEFAULT '{}'::jsonb,
  crawl_time TIMESTAMP NOT NULL,
  source TEXT NOT NULL,
  group_name VARCHAR(20) NOT NULL DEFAULT 'commodity',
  UNIQUE (fuel, period)
);
CREATE INDEX IF NOT EXISTS idx_fuel_price_cycle_period ON fuel_price_cycle (period);

-- Silver: daily world-price futures (proxy for MOPS reference window).
CREATE TABLE IF NOT EXISTS fuel_world_daily (
  id SERIAL PRIMARY KEY,
  period DATE NOT NULL,
  instrument VARCHAR(12) NOT NULL,               -- SGGO | BRENT | RBOB
  close NUMERIC NOT NULL,
  crawl_time TIMESTAMP NOT NULL,
  source TEXT NOT NULL,
  group_name VARCHAR(20) NOT NULL DEFAULT 'commodity',
  UNIQUE (instrument, period)
);
CREATE INDEX IF NOT EXISTS idx_fuel_world_daily_period ON fuel_world_daily (period);

-- Nghị định 80 formula parameters, versioned (change when tax/fee policy changes).
CREATE TABLE IF NOT EXISTS fuel_formula_params (
  id SERIAL PRIMARY KEY,
  effective_from DATE NOT NULL,
  fuel VARCHAR(12) NOT NULL,
  import_pct NUMERIC NOT NULL,                    -- e.g. 0.10
  excise_pct NUMERIC NOT NULL,                    -- 0.10 RON95 / 0.08 E5 / 0.0 diesel
  env_vnd NUMERIC NOT NULL,                       -- environmental tax, VND/L (fixed)
  vat_pct NUMERIC NOT NULL,                       -- e.g. 0.10
  business_cost_norm NUMERIC NOT NULL,            -- VND/L
  profit_norm NUMERIC NOT NULL,                   -- VND/L
  freight_premium NUMERIC NOT NULL,               -- USD/barrel (freight + premium)
  import_weight_pct NUMERIC NOT NULL DEFAULT 100,
  domestic_weight_pct NUMERIC NOT NULL DEFAULT 0,
  UNIQUE (fuel, effective_from)
);
