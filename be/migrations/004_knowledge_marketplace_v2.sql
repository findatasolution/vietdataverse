-- Knowledge Marketplace v2 - run on KNOWLEDGE_MARKET_DB
-- Tables are transactional business data, NOT crawl time-series
-- → period/crawl_time/source/group_name N/A per CLAUDE.md scope

-- ============================================================
-- 1. SELLER PROFILES
-- ============================================================
CREATE TABLE IF NOT EXISTS seller_profiles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL UNIQUE,
    user_email_snapshot VARCHAR(200) NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    bio             TEXT,
    linkedin_url    VARCHAR(300) NOT NULL,
    apply_status    VARCHAR(15) NOT NULL DEFAULT 'pending'
                    CHECK (apply_status IN ('pending','approved','rejected')),
    apply_note      TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_seller_user ON seller_profiles(user_id);
CREATE INDEX IF NOT EXISTS ix_seller_status ON seller_profiles(apply_status);

-- ============================================================
-- 2. KNOWLEDGE PRODUCTS
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_products (
    id              SERIAL PRIMARY KEY,
    seller_id       INTEGER NOT NULL REFERENCES seller_profiles(id),
    slug            VARCHAR(150) NOT NULL UNIQUE,
    title           VARCHAR(200) NOT NULL,
    description     TEXT,
    category        VARCHAR(30) NOT NULL
                    CHECK (category IN ('accounting','trading','macro','policy','sentiment','risk-management','esg','crypto')),
    format          VARCHAR(10) NOT NULL
                    CHECK (format IN ('md','json','yaml','yml','csv','txt')),
    frameworks      VARCHAR(200),
    price_credits   INTEGER NOT NULL DEFAULT 0 CHECK (price_credits >= 0),
    preview_pct     INTEGER NOT NULL DEFAULT 25 CHECK (preview_pct BETWEEN 0 AND 40),
    version         VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    file_r2_key     VARCHAR(300) NOT NULL,
    file_sha256     CHAR(64) NOT NULL,
    file_size_bytes INTEGER NOT NULL,
    scan_status     VARCHAR(15) NOT NULL DEFAULT 'pending'
                    CHECK (scan_status IN ('pending','clean','infected','error')),
    scan_result_json JSONB,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending_review'
                    CHECK (status IN ('pending_review','approved','rejected','disabled')),
    rejection_reason TEXT,
    is_vd_owned     BOOLEAN NOT NULL DEFAULT FALSE,
    download_count  INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    published_at    TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_kprod_seller ON knowledge_products(seller_id);
CREATE INDEX IF NOT EXISTS ix_kprod_status ON knowledge_products(status);
CREATE INDEX IF NOT EXISTS ix_kprod_category ON knowledge_products(category);
CREATE INDEX IF NOT EXISTS ix_kprod_scan ON knowledge_products(scan_status);

-- ============================================================
-- 3. CREDIT LEDGER (append-only, event sourcing)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_ledger (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    amount      INTEGER NOT NULL,  -- +ve = credit, -ve = debit
    kind        VARCHAR(20) NOT NULL
                CHECK (kind IN ('topup','purchase','refund','admin_adjust')),
    ref_type    VARCHAR(20),
    ref_id      BIGINT,
    idem_key    VARCHAR(120) UNIQUE NOT NULL,
    note        TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ledger_user ON credit_ledger(user_id);
CREATE INDEX IF NOT EXISTS ix_ledger_kind ON credit_ledger(kind);

-- ============================================================
-- 4. CREDIT BALANCE (materialized, updated in same txn as ledger)
-- ============================================================
CREATE TABLE IF NOT EXISTS credit_balance (
    user_id     INTEGER PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 5. SELLER EARNINGS (VND, separate from buyer credits)
-- ============================================================
CREATE TABLE IF NOT EXISTS seller_earnings (
    user_id     INTEGER PRIMARY KEY,
    pending_vnd BIGINT NOT NULL DEFAULT 0 CHECK (pending_vnd >= 0),
    paid_vnd    BIGINT NOT NULL DEFAULT 0 CHECK (paid_vnd >= 0),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 6. PURCHASES (license to download)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_purchases (
    id              SERIAL PRIMARY KEY,
    buyer_id        INTEGER NOT NULL,
    buyer_email_snapshot VARCHAR(200) NOT NULL,
    product_id      INTEGER NOT NULL REFERENCES knowledge_products(id),
    seller_id       INTEGER NOT NULL REFERENCES seller_profiles(id),
    credits_paid    INTEGER NOT NULL CHECK (credits_paid >= 0),
    seller_share_vnd BIGINT NOT NULL DEFAULT 0,
    license_key     VARCHAR(80) NOT NULL UNIQUE,
    status          VARCHAR(15) NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','refunded')),
    purchased_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    refund_deadline TIMESTAMP NOT NULL,  -- = purchased_at + 1h
    UNIQUE (buyer_id, product_id)
);
CREATE INDEX IF NOT EXISTS ix_purchase_buyer ON knowledge_purchases(buyer_id);
CREATE INDEX IF NOT EXISTS ix_purchase_product ON knowledge_purchases(product_id);
CREATE INDEX IF NOT EXISTS ix_purchase_seller ON knowledge_purchases(seller_id);

-- ============================================================
-- 7. DOWNLOAD LOG (re-download window 30 days + audit)
-- ============================================================
CREATE TABLE IF NOT EXISTS knowledge_download_log (
    id              SERIAL PRIMARY KEY,
    purchase_id     INTEGER NOT NULL REFERENCES knowledge_purchases(id),
    buyer_id        INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    ip_addr         VARCHAR(45),
    user_agent      TEXT,
    downloaded_at   TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_dlog_purchase ON knowledge_download_log(purchase_id);

-- ============================================================
-- 8. FILE SCAN LOG (audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS file_scan_log (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER REFERENCES knowledge_products(id),
    file_hash   CHAR(64) NOT NULL,
    scanner     VARCHAR(20) NOT NULL,  -- 'custom_rules' | 'clamav' (Phase 2)
    result      VARCHAR(15) NOT NULL CHECK (result IN ('clean','infected','error')),
    detail      JSONB,
    scanned_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_scan_product ON file_scan_log(product_id);

-- ============================================================
-- 9. SELLER PAYOUT REQUESTS (admin-managed)
-- ============================================================
CREATE TABLE IF NOT EXISTS seller_payouts (
    id              SERIAL PRIMARY KEY,
    seller_id       INTEGER NOT NULL,
    seller_email_snapshot VARCHAR(200) NOT NULL,
    amount_vnd      BIGINT NOT NULL CHECK (amount_vnd > 0),
    status          VARCHAR(15) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','paid','rejected')),
    admin_note      TEXT,
    requested_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    paid_at         TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_payout_seller ON seller_payouts(seller_id);
CREATE INDEX IF NOT EXISTS ix_payout_status ON seller_payouts(status);
