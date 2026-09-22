-- 018: LBMA gold forecast survey — aggregate-only summary of the annual and
-- mid-year professional-analyst surveys. GLOBAL_INDICATOR_DB, same DB as
-- global_macro (Yahoo Finance) — this is also world/international-market data,
-- unrelated to any VN-specific source.
--
-- Deliberately AGGREGATE ONLY (avg/high/low/n_analysts), never per-analyst.
-- LBMA's own material states content "may not be altered in any way,
-- transmitted to, copied or distributed to any other party" without written
-- permission — the per-analyst "cards" (28 named individuals/firms) are LBMA's
-- own proprietary compiled data, not raw public administrative data like the
-- MOIT/GSO bulletins this project already crawls. Citing an aggregate
-- statistic with attribution ("theo khảo sát LBMA, trung bình X") is standard
-- journalistic practice and a materially smaller reuse than republishing the
-- full named-analyst listing. Do not extend this table to store per-analyst
-- rows without written permission from LBMA first — see the discussion in
-- CLAUDE.md's "LBMA gold forecast survey" section.
--
-- Two report types, two different publish behaviours:
--   annual  — https://www.lbma.org.uk/forecast-survey-{YEAR}/at-a-glance,
--             published mid-January, forecasts for that same calendar year.
--   midyear — a fixed, evergreen article URL LBMA reuses/updates in place
--             each July, so "new" is detected by the article's own published
--             date advancing, not by a new URL appearing.
--
-- Safe to re-run.

CREATE TABLE IF NOT EXISTS global_lbma_gold_forecast (
    id             SERIAL PRIMARY KEY,
    survey_type    VARCHAR(10) NOT NULL,   -- 'annual' | 'midyear'
    survey_year    INT NOT NULL,           -- calendar year the forecast targets
    published_date DATE NOT NULL,          -- when LBMA published this report
    n_analysts     INT NOT NULL,
    avg_price      NUMERIC NOT NULL,       -- USD/oz
    high_price     NUMERIC NOT NULL,       -- USD/oz
    low_price      NUMERIC NOT NULL,       -- USD/oz
    source_url     TEXT NOT NULL,
    crawl_time     TIMESTAMP NOT NULL,
    source         TEXT NOT NULL,
    group_name     VARCHAR(20) NOT NULL DEFAULT 'commodity',
    CONSTRAINT uq_lbma_survey_type_year UNIQUE (survey_type, survey_year),
    CONSTRAINT chk_lbma_survey_type CHECK (survey_type IN ('annual', 'midyear')),
    CONSTRAINT chk_lbma_price_order CHECK (low_price <= avg_price AND avg_price <= high_price)
);

CREATE INDEX IF NOT EXISTS idx_lbma_survey_year ON global_lbma_gold_forecast (survey_year);
