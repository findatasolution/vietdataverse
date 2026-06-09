"""Run migration 005 on KNOWLEDGE_MARKET_DB.

Adds trust/verification columns to seller_profiles,
moderation columns to knowledge_products,
and creates listing_reports, dmca_notices, audit_log tables.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load from project root .env first, then be/.env as fallback
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DB_URL = os.getenv("KNOWLEDGE_MARKET_DB")
if not DB_URL:
    sys.exit("KNOWLEDGE_MARKET_DB not set — add it to .env and retry")

sql_path = Path(__file__).resolve().parent / "005_zero_admin_seller.sql"
sql = sql_path.read_text(encoding="utf-8")

engine = create_engine(DB_URL)
with engine.begin() as conn:
    conn.execute(text(sql))

print("Migration 005 applied successfully to KNOWLEDGE_MARKET_DB.")
print("Tables created/altered:")
print("  - seller_profiles: +email_verified, +email_verify_token, +email_verify_expires,")
print("                     +trust_tier, +tos_accepted_at, +tos_version,")
print("                     +violation_count, +banned_at, +ban_reason")
print("  - knowledge_products: +report_count, +auto_unpublished_reason, +unpublished_at,")
print("                        status CHECK updated to include 'live','takedown'")
print("  - listing_reports (new)")
print("  - dmca_notices (new)")
print("  - audit_log (new)")
