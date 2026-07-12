-- Gold layer for FUEL_FORECAST_DB (forecasts + backtest metrics). Apply once:
--   python script loading FUEL_FORECAST_DB and executing this file.

CREATE TABLE IF NOT EXISTS fuel_forecast (
  id SERIAL PRIMARY KEY,
  run_ts TIMESTAMP NOT NULL,
  fuel VARCHAR(12) NOT NULL,
  target_cycle DATE NOT NULL,
  horizon INT NOT NULL,                        -- 1 = next cycle
  scenario VARCHAR(6) NOT NULL,                -- low | base | high
  point NUMERIC NOT NULL,                      -- VND/L
  lo NUMERIC NOT NULL,
  hi NUMERIC NOT NULL,
  breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
  model_version VARCHAR(40) NOT NULL,
  methodology_version VARCHAR(40) NOT NULL,
  UNIQUE (run_ts, fuel, target_cycle, scenario)
);
CREATE INDEX IF NOT EXISTS idx_fuel_forecast_target ON fuel_forecast (target_cycle);

CREATE TABLE IF NOT EXISTS fuel_backtest (
  id SERIAL PRIMARY KEY,
  run_ts TIMESTAMP NOT NULL,
  fuel VARCHAR(12) NOT NULL,
  horizon INT NOT NULL,
  mae NUMERIC NOT NULL,                        -- VND/L
  rmse NUMERIC NOT NULL,
  coverage NUMERIC NOT NULL,                   -- fraction of actuals inside [lo,hi]
  n INT NOT NULL,                              -- number of held-out cycles
  skill_vs_rw NUMERIC NOT NULL,                -- 1 - MAE_model/MAE_randomwalk
  model_version VARCHAR(40) NOT NULL,
  UNIQUE (run_ts, fuel, horizon, model_version)   -- one row per model per run
);
