-- Migration 011 — User analytics & API metering layer (USER_DB)
--
-- Mục tiêu:
--   1. Lớp A — Login tracking: users.last_login_at / login_count + bảng login_events
--      → trả lời "bao nhiêu unique user đã đăng nhập / DAU / MAU".
--   2. Lớp B — Chuẩn hoá 2 bảng metering tạo tay (chưa có migration):
--      api_usage_monthly (enforce quota) + api_call_log (ai gọi endpoint gì, lúc nào)
--      + index để truy vấn theo ngày / endpoint / user rẻ.
--
-- Idempotent: dùng IF NOT EXISTS để chạy lại an toàn.

-- ── Lớp A: login tracking ────────────────────────────────────────────────────
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS login_count   INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS login_events (
    id      BIGSERIAL PRIMARY KEY,
    user_id INT         NOT NULL,
    at      TIMESTAMP   NOT NULL DEFAULT NOW(),
    method  VARCHAR(20),                       -- google | api_key | internal
    ip      VARCHAR(64)
);
CREATE INDEX IF NOT EXISTS idx_login_events_at      ON login_events (at);
CREATE INDEX IF NOT EXISTS idx_login_events_user_at ON login_events (user_id, at);

-- ── Lớp B: metering tables (chuẩn hoá bảng đã tạo tay) ───────────────────────
CREATE TABLE IF NOT EXISTS api_usage_monthly (
    user_id       INT         NOT NULL,
    quota_month   VARCHAR(7)  NOT NULL,        -- 'YYYY-MM' theo giờ VN
    request_count INT         NOT NULL DEFAULT 0,
    updated_at    TIMESTAMP   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, quota_month)
);

CREATE TABLE IF NOT EXISTS api_call_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INT,
    api_key_id  INT,
    endpoint    TEXT        NOT NULL,
    status_code INT,
    at          TIMESTAMP   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_api_call_log_at          ON api_call_log (at);
CREATE INDEX IF NOT EXISTS idx_api_call_log_user_at     ON api_call_log (user_id, at);
CREATE INDEX IF NOT EXISTS idx_api_call_log_endpoint_at ON api_call_log (endpoint, at);
