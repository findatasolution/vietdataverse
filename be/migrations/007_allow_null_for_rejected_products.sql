-- Migration 007: Allow NULL file fields for rejected products (no R2 upload)
-- Rejected products are stored for audit but never had successful R2 upload

ALTER TABLE knowledge_products ALTER COLUMN file_r2_key DROP NOT NULL;
ALTER TABLE knowledge_products ALTER COLUMN file_sha256 DROP NOT NULL;
ALTER TABLE knowledge_products ALTER COLUMN file_size_bytes DROP NOT NULL;
