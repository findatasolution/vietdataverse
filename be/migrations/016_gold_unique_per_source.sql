-- 016: let two sources store the same day's SJC price side by side.
--
-- Until now the unique key was (date, type). With a single crawler that was
-- right: one row per brand per day. From 2026-09-14 two independent crawlers
-- read the SJC quote from two different sites (24h.com.vn and giavang.org), and
-- under the old key their upserts would overwrite each other — the stored value
-- would silently flip to whichever ran last, and a disagreement between the two
-- would be invisible. Keying on source instead keeps both readings, so they can
-- be compared and either one can cover for the other going missing.
--
-- Read path picks one deliberately rather than "latest wins": see
-- be/generate_static_data.py and be/routers/market_data.py, which prefer
-- 24h.com.vn and fall back to giavang.org.
--
-- Safe to re-run.

ALTER TABLE vn_macro_gold_daily
    ALTER COLUMN source SET NOT NULL;

DROP INDEX IF EXISTS uq_vn_gold_date_type;

CREATE UNIQUE INDEX IF NOT EXISTS uq_vn_gold_date_type_source
    ON vn_macro_gold_daily (date, type, source);

-- The read path filters on source, so give it an index to use.
CREATE INDEX IF NOT EXISTS idx_vn_gold_source
    ON vn_macro_gold_daily (source);
