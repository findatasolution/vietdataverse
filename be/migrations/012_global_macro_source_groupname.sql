-- 012: add required source/group_name columns to global_macro (GLOBAL_INDICATOR_DB)
-- Root cause: crawl_gold_silver.py global section INSERTs source/group_name but the
-- table never had these columns -> psycopg2 UndefinedColumn -> global_macro stale since 2026-06-12.
-- Pattern per CLAUDE.md: ALTER -> UPDATE backfill -> NOT NULL.
-- global_* taxonomy -> group_name = 'commodity'; source = 'Yahoo Finance'.

ALTER TABLE global_macro ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE global_macro ADD COLUMN IF NOT EXISTS group_name VARCHAR(20);

UPDATE global_macro SET source = 'Yahoo Finance' WHERE source IS NULL;
UPDATE global_macro SET group_name = 'commodity' WHERE group_name IS NULL;

ALTER TABLE global_macro ALTER COLUMN source SET NOT NULL;
ALTER TABLE global_macro ALTER COLUMN group_name SET NOT NULL;
