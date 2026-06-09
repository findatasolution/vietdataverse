"""
Migration 005 — tạo bảng webhook_subscriptions trong USER_DB.
Chạy: python be/migrations/run_005_webhooks.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

from sqlalchemy import create_engine, text

DB_URL = os.getenv("USER_DB")
if not DB_URL:
    sys.exit("ERROR: USER_DB not set")

engine = create_engine(DB_URL)

SQL = """
CREATE TABLE IF NOT EXISTS webhook_subscriptions (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    url               TEXT NOT NULL,
    events            TEXT[] NOT NULL DEFAULT '{}',
    secret            VARCHAR(64) NOT NULL,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMP NOT NULL DEFAULT NOW(),
    last_triggered_at TIMESTAMP,
    last_status_code  INTEGER,
    failure_count     INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT uq_user_url UNIQUE (user_id, url)
);

CREATE INDEX IF NOT EXISTS idx_webhook_user  ON webhook_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_webhook_event ON webhook_subscriptions USING GIN (events);
"""

with engine.begin() as conn:
    conn.execute(text(SQL))

print("✅ Migration 005 done — webhook_subscriptions table created.")
