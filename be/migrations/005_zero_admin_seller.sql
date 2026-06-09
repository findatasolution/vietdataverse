-- Migration 005: Zero-admin seller trust layer
-- Target DB: KNOWLEDGE_MARKET_DB
-- Idempotent — safe to re-run (uses IF NOT EXISTS, DO NOTHING patterns)

-- ============================================================
-- 1. ALTER seller_profiles — trust + verification columns
-- ============================================================
ALTER TABLE seller_profiles
    ADD COLUMN IF NOT EXISTS email_verified        BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS email_verify_token    VARCHAR(128),
    ADD COLUMN IF NOT EXISTS email_verify_expires  TIMESTAMP,
    ADD COLUMN IF NOT EXISTS trust_tier            VARCHAR(15) NOT NULL DEFAULT 'basic'
                                                   CHECK (trust_tier IN ('basic','elevated','trusted')),
    ADD COLUMN IF NOT EXISTS tos_accepted_at       TIMESTAMP,
    ADD COLUMN IF NOT EXISTS tos_version           VARCHAR(10),
    ADD COLUMN IF NOT EXISTS violation_count       INTEGER     NOT NULL DEFAULT 0 CHECK (violation_count >= 0),
    ADD COLUMN IF NOT EXISTS banned_at             TIMESTAMP,
    ADD COLUMN IF NOT EXISTS ban_reason            TEXT;

-- ============================================================
-- 2. ALTER knowledge_products — moderation columns
--    Also update status CHECK to remove pending_review and
--    add 'live' as the published state.
-- ============================================================
ALTER TABLE knowledge_products
    ADD COLUMN IF NOT EXISTS report_count            INTEGER NOT NULL DEFAULT 0 CHECK (report_count >= 0),
    ADD COLUMN IF NOT EXISTS auto_unpublished_reason TEXT,
    ADD COLUMN IF NOT EXISTS unpublished_at          TIMESTAMP;

-- Drop old status CHECK and replace with expanded set.
-- The prior CHECK allowed: pending_review | approved | rejected | disabled
-- New set: pending_review | approved | rejected | disabled | live | takedown
-- (pending_review kept for rollback safety — no active code path will set it
--  after Step 2 routers land, but removing it now would break old rows.)
ALTER TABLE knowledge_products
    DROP CONSTRAINT IF EXISTS knowledge_products_status_check;

ALTER TABLE knowledge_products
    ADD CONSTRAINT knowledge_products_status_check
        CHECK (status IN ('pending_review','approved','rejected','disabled','live','takedown'));

-- ============================================================
-- 3. CREATE listing_reports
-- ============================================================
CREATE TABLE IF NOT EXISTS listing_reports (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES knowledge_products(id),
    reporter_id     INTEGER NOT NULL,                                           -- USER_DB user_id (no FK)
    reason          VARCHAR(30) NOT NULL
                    CHECK (reason IN ('pii','spam','misleading','copyright','malware','other')),
    detail          TEXT,
    status          VARCHAR(15) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','reviewed','dismissed')),
    admin_note      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMP,
    UNIQUE (product_id, reporter_id)                                            -- one report per user per product
);
CREATE INDEX IF NOT EXISTS ix_listrep_product  ON listing_reports(product_id);
CREATE INDEX IF NOT EXISTS ix_listrep_status   ON listing_reports(status);
CREATE INDEX IF NOT EXISTS ix_listrep_reporter ON listing_reports(reporter_id);

-- ============================================================
-- 4. CREATE dmca_notices
-- ============================================================
CREATE TABLE IF NOT EXISTS dmca_notices (
    id              SERIAL PRIMARY KEY,
    product_id      INTEGER NOT NULL REFERENCES knowledge_products(id),
    claimant_name   VARCHAR(200) NOT NULL,
    claimant_email  VARCHAR(200) NOT NULL,
    description     TEXT NOT NULL,
    original_url    TEXT,
    status          VARCHAR(15) NOT NULL DEFAULT 'received'
                    CHECK (status IN ('received','under_review','actioned','dismissed')),
    admin_note      TEXT,
    received_at     TIMESTAMP NOT NULL DEFAULT NOW(),
    actioned_at     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_dmca_product ON dmca_notices(product_id);
CREATE INDEX IF NOT EXISTS ix_dmca_status  ON dmca_notices(status);

-- ============================================================
-- 5. CREATE audit_log
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    action      VARCHAR(80) NOT NULL,                                           -- e.g. 'seller.email_verified'
    actor_type  VARCHAR(20) NOT NULL
                CHECK (actor_type IN ('user','admin','system')),
    actor_id    INTEGER,                                                        -- user_id or NULL for system
    target_type VARCHAR(30),                                                    -- 'seller_profile' | 'product' | ...
    target_id   INTEGER,
    detail      JSONB,                                                          -- arbitrary key/value context
    ip_addr     VARCHAR(45),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_auditlog_action     ON audit_log(action);
CREATE INDEX IF NOT EXISTS ix_auditlog_actor      ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS ix_auditlog_target     ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS ix_auditlog_created_at ON audit_log(created_at);
