-- Migration 003: Knowledge Marketplace
-- Target DB: USER_DB (NOT crawl DB — no period/crawl_time/source/group_name required)
-- Run once manually or via deployment script.

-- ── knowledge_products ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_products (
    id                SERIAL          PRIMARY KEY,
    slug              VARCHAR(120)    NOT NULL UNIQUE,
    seller_id         INTEGER         REFERENCES users(user_id),
    title             VARCHAR(200)    NOT NULL,
    description       TEXT            NOT NULL DEFAULT '',
    category          VARCHAR(30)     NOT NULL
                      CHECK (category IN ('accounting','banking','insurance','trading','macro','policy','sentiment')),
    format            VARCHAR(10)     NOT NULL
                      CHECK (format IN ('md','json','yaml')),
    frameworks        VARCHAR(100)    NOT NULL DEFAULT '',  -- comma-sep: "crewai,langchain,claude"
    price_vnd         INTEGER         NOT NULL DEFAULT 0 CHECK (price_vnd >= 0),
    preview_pct       INTEGER         NOT NULL DEFAULT 25 CHECK (preview_pct BETWEEN 0 AND 40),
    file_key          TEXT,           -- Cloudflare R2 object key; NULL = not yet uploaded
    file_size_bytes   INTEGER,
    file_hash_sha256  CHAR(64),
    version           VARCHAR(20)     NOT NULL DEFAULT '1.0.0',
    status            VARCHAR(15)     NOT NULL DEFAULT 'pending_review'
                      CHECK (status IN ('pending_review','approved','rejected','archived')),
    is_vd_owned       BOOLEAN         NOT NULL DEFAULT FALSE,
    download_count    INTEGER         NOT NULL DEFAULT 0,
    rating_avg        NUMERIC(2,1)    NOT NULL DEFAULT 0,
    rating_count      INTEGER         NOT NULL DEFAULT 0,
    created_at        TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_products_status
    ON knowledge_products(status);
CREATE INDEX IF NOT EXISTS ix_knowledge_products_category
    ON knowledge_products(category);
CREATE INDEX IF NOT EXISTS ix_knowledge_products_seller
    ON knowledge_products(seller_id);

-- ── knowledge_purchases ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_purchases (
    id              SERIAL          PRIMARY KEY,
    buyer_id        INTEGER         NOT NULL REFERENCES users(user_id),
    product_id      INTEGER         NOT NULL REFERENCES knowledge_products(id),
    amount_vnd      INTEGER         NOT NULL DEFAULT 0,
    purchase_type   VARCHAR(15)     NOT NULL DEFAULT 'one_off',
    license_key     CHAR(36)        NOT NULL UNIQUE,   -- UUID v4
    status          VARCHAR(15)     NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','expired','refunded')),
    expires_at      TIMESTAMP       NULL,              -- NULL = lifetime
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (buyer_id, product_id, purchase_type)
);

CREATE INDEX IF NOT EXISTS ix_knowledge_purchases_buyer
    ON knowledge_purchases(buyer_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_purchases_license
    ON knowledge_purchases(license_key);

-- ── knowledge_reviews ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_reviews (
    id              SERIAL          PRIMARY KEY,
    purchase_id     INTEGER         NOT NULL REFERENCES knowledge_purchases(id),
    buyer_id        INTEGER         NOT NULL REFERENCES users(user_id),
    product_id      INTEGER         NOT NULL REFERENCES knowledge_products(id),
    rating          INTEGER         NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment         TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UNIQUE (purchase_id)
);

CREATE INDEX IF NOT EXISTS ix_knowledge_reviews_product
    ON knowledge_reviews(product_id);

-- ── seller_profiles ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS seller_profiles (
    user_id         INTEGER         PRIMARY KEY REFERENCES users(user_id),
    display_name    VARCHAR(100)    NOT NULL DEFAULT '',
    bio             TEXT            NOT NULL DEFAULT '',
    total_revenue   BIGINT          NOT NULL DEFAULT 0,
    payout_pending  BIGINT          NOT NULL DEFAULT 0,
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);
