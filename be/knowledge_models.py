"""
SQLAlchemy ORM models for Knowledge Marketplace v2.
All tables live on KNOWLEDGE_MARKET_DB — isolated from USER_DB.
No FK to users(user_id); buyer/seller identity stored as INTEGER + email snapshot.
Not crawl time-series data → period/crawl_time/source/group_name columns are N/A.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

# Current Terms of Service version — bump this when seller_tos_vN.md is updated
CURRENT_TOS_VERSION = "1.0"

Base = declarative_base()


class SellerProfile(Base):
    """
    Extended profile for users who apply to become sellers.
    apply_status progresses: pending → approved | rejected (manual admin, SLA 48h).
    No FK to USER_DB — user_id + email_snapshot for cross-DB identity.
    """
    __tablename__ = "seller_profiles"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(Integer, nullable=False, unique=True)           # USER_DB users.user_id (no FK)
    user_email_snapshot = Column(String(200), nullable=False)                    # email at apply time
    display_name        = Column(String(100), nullable=False)
    bio                 = Column(Text, nullable=True)
    linkedin_url        = Column(String(300), nullable=True)                     # optional (zero-admin flow)
    apply_status        = Column(String(15), nullable=False, default="auto_approved")  # pending|approved|rejected|auto_approved
    apply_note          = Column(Text, nullable=True)                            # admin rejection reason
    # Trust + verification columns (added in migration 005)
    email_verified       = Column(Boolean, nullable=False, default=False)        # True after email link clicked
    email_verify_token   = Column(String(128), nullable=True)                   # itsdangerous signed token
    email_verify_expires = Column(DateTime, nullable=True)                      # UTC expiry
    trust_tier           = Column(String(15), nullable=False, default="basic")  # basic|elevated|trusted
    tos_accepted_at      = Column(DateTime, nullable=True)                      # UTC when seller accepted ToS
    tos_version          = Column(String(10), nullable=True)                    # e.g. "1.0"
    violation_count      = Column(Integer, nullable=False, default=0)           # incremented by auto-moderation
    banned_at            = Column(DateTime, nullable=True)                      # NULL = not banned
    ban_reason           = Column(Text, nullable=True)
    created_at          = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at          = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_seller_user",   "user_id"),
        Index("ix_seller_status", "apply_status"),
        Index("ix_seller_trust",  "trust_tier"),
    )


class KnowledgeProduct(Base):
    """
    A sellable knowledge asset (prompt pack, playbook, data schema, etc.).
    File stored in Cloudflare R2 (file_r2_key). Scanned before publish.
    Status flow: pending_review → approved | rejected | disabled.
    Free products (price_credits=0) still require scan to pass.
    """
    __tablename__ = "knowledge_products"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    seller_id        = Column(Integer, ForeignKey("seller_profiles.id"), nullable=False)
    slug             = Column(String(150), nullable=False, unique=True)          # URL-safe identifier
    title            = Column(String(200), nullable=False)
    description      = Column(Text, nullable=True)
    category         = Column(String(30), nullable=False)                        # see CHECK in SQL
    format           = Column(String(10), nullable=False)                        # md|json|yaml|yml|csv|txt
    frameworks       = Column(String(200), nullable=True)                        # comma-sep: crewai,langchain
    price_credits    = Column(Integer, nullable=False, default=0)                # 0 = free; 1 credit = 1,000 VND
    price_usd        = Column(Numeric(10, 2), nullable=False, default=0)         # USD price; 0 = free; mirrored with price_credits
    preview_pct      = Column(Integer, nullable=False, default=25)               # 0–40% of file as preview
    version          = Column(String(20), nullable=False, default="1.0.0")
    file_r2_key      = Column(String(300), nullable=False)                       # Cloudflare R2 object key
    file_sha256      = Column(String(64), nullable=False)                        # hex SHA-256
    file_size_bytes  = Column(Integer, nullable=False)                           # bytes
    scan_status      = Column(String(15), nullable=False, default="pending")     # pending|clean|infected|error
    scan_result_json = Column(JSONB, nullable=True)                              # scan detail blob
    status           = Column(String(20), nullable=False, default="pending_review")
    # status values: pending_review | approved | rejected | disabled | live | takedown | published | unpublished | archived | deleted
    rejection_reason = Column(Text, nullable=True)
    is_vd_owned      = Column(Boolean, nullable=False, default=False)            # True = Viet Dataverse first-party
    download_count   = Column(Integer, nullable=False, default=0)
    # Moderation columns (added in migration 005)
    report_count             = Column(Integer, nullable=False, default=0)        # incremented on each ListingReport
    auto_unpublished_reason  = Column(Text, nullable=True)                       # set by auto-moderation rules
    unpublished_at           = Column(DateTime, nullable=True)                   # UTC when auto-unpublished
    created_at       = Column(DateTime, nullable=False, default=datetime.utcnow)
    published_at     = Column(DateTime, nullable=True)
    updated_at       = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_kprod_seller",   "seller_id"),
        Index("ix_kprod_status",   "status"),
        Index("ix_kprod_category", "category"),
        Index("ix_kprod_scan",     "scan_status"),
        Index("ix_kprod_reports",  "report_count"),
    )


class CreditLedger(Base):
    """
    Append-only event log for buyer credit movements.
    amount > 0 = credit (topup/refund); amount < 0 = debit (purchase).
    idem_key enforces idempotency — same key → no double write.
    Never delete rows; refunds are separate positive entries.
    """
    __tablename__ = "credit_ledger"

    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, nullable=False)                                 # USER_DB users.user_id (no FK)
    amount     = Column(Integer, nullable=False)                                 # credits; signed
    kind       = Column(String(20), nullable=False)                              # topup|purchase|refund|admin_adjust
    ref_type   = Column(String(20), nullable=True)                               # 'product' | None
    ref_id     = Column(BigInteger, nullable=True)                               # product_id / purchase_id
    idem_key   = Column(String(120), nullable=False, unique=True)                # caller-supplied idempotency key
    note       = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_ledger_user", "user_id"),
        Index("ix_ledger_kind", "kind"),
    )


class CreditBalance(Base):
    """
    Materialized running balance per buyer.
    Updated atomically in the same transaction as the ledger insert.
    CHECK (balance >= 0) prevents overdraft at DB level.
    """
    __tablename__ = "credit_balance"

    user_id    = Column(Integer, primary_key=True)                               # USER_DB users.user_id (no FK)
    balance    = Column(Integer, nullable=False, default=0)                      # credits remaining
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class SellerEarnings(Base):
    """
    Tracks seller revenue in VND (not credits).
    pending_vnd = earned but not yet disbursed.
    paid_vnd = cumulative disbursed total.
    Revenue split: 90% seller / 10% platform per purchase.
    """
    __tablename__ = "seller_earnings"

    user_id     = Column(Integer, primary_key=True)                              # seller USER_DB user_id (no FK)
    pending_vnd = Column(BigInteger, nullable=False, default=0)                  # VND awaiting payout
    paid_vnd    = Column(BigInteger, nullable=False, default=0)                  # VND already paid out
    updated_at  = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class KnowledgePurchase(Base):
    """
    Records a buyer's license to download a product.
    One purchase per (buyer_id, product_id) — enforced by UNIQUE constraint.
    Refund window: 1h from purchased_at, only if no download has occurred.
    Re-download window: 30 days from purchased_at (enforced in router).
    """
    __tablename__ = "knowledge_purchases"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    buyer_id             = Column(Integer, nullable=False)                        # USER_DB users.user_id (no FK)
    buyer_email_snapshot = Column(String(200), nullable=False)                   # email at purchase time
    product_id           = Column(Integer, ForeignKey("knowledge_products.id"), nullable=False)
    seller_id            = Column(Integer, ForeignKey("seller_profiles.id"), nullable=False)
    credits_paid         = Column(Integer, nullable=False)                       # credits deducted from buyer
    seller_share_vnd     = Column(BigInteger, nullable=False, default=0)         # VND credited to seller (90%)
    license_key          = Column(String(80), nullable=False, unique=True)       # token_urlsafe(48)
    status               = Column(String(15), nullable=False, default="active")  # active|refunded
    purchased_at         = Column(DateTime, nullable=False, default=datetime.utcnow)
    refund_deadline      = Column(DateTime, nullable=False)                      # purchased_at + 1h

    __table_args__ = (
        UniqueConstraint("buyer_id", "product_id", name="uq_purchase_buyer_product"),
        Index("ix_purchase_buyer",   "buyer_id"),
        Index("ix_purchase_product", "product_id"),
        Index("ix_purchase_seller",  "seller_id"),
    )


class KnowledgeDownloadLog(Base):
    """
    Audit log for every file download.
    Used to enforce 30-day re-download window and block refunds post-download.
    """
    __tablename__ = "knowledge_download_log"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id   = Column(Integer, ForeignKey("knowledge_purchases.id"), nullable=False)
    buyer_id      = Column(Integer, nullable=False)
    product_id    = Column(Integer, nullable=False)
    ip_addr       = Column(String(45), nullable=True)                            # IPv4 or IPv6
    user_agent    = Column(Text, nullable=True)
    downloaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dlog_purchase", "purchase_id"),
    )


class FileScanLog(Base):
    """
    Audit trail for every file security scan.
    Phase 1: scanner='custom_rules'. Phase 2 will add scanner='clamav'.
    Retained indefinitely for compliance.
    """
    __tablename__ = "file_scan_log"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("knowledge_products.id"), nullable=True)  # NULL if pre-upload scan
    file_hash  = Column(String(64), nullable=False)                              # hex SHA-256
    scanner    = Column(String(20), nullable=False)                              # custom_rules | clamav
    result     = Column(String(15), nullable=False)                              # clean|infected|error
    detail     = Column(JSONB, nullable=True)                                    # scan detail blob
    scanned_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_scan_product", "product_id"),
    )


class SellerPayout(Base):
    """
    Admin-managed payout requests.
    When admin triggers payout: pending_vnd snapshot → seller_payouts row, pending_vnd reset to 0.
    Bank info NOT stored — admin emails seller separately.
    """
    __tablename__ = "seller_payouts"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    seller_id             = Column(Integer, nullable=False)                       # seller USER_DB user_id (no FK)
    seller_email_snapshot = Column(String(200), nullable=False)                  # email at payout request time
    amount_vnd            = Column(BigInteger, nullable=False)                   # VND amount to disburse
    status                = Column(String(15), nullable=False, default="pending") # pending|paid|rejected
    admin_note            = Column(Text, nullable=True)
    requested_at          = Column(DateTime, nullable=False, default=datetime.utcnow)
    paid_at               = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_payout_seller", "seller_id"),
        Index("ix_payout_status", "status"),
    )


class ListingReport(Base):
    """
    User-submitted moderation report against a knowledge product.
    One report per (product_id, reporter_id) — enforced by UNIQUE constraint.
    When report_count crosses threshold, product may be auto-unpublished.
    """
    __tablename__ = "listing_reports"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    product_id  = Column(Integer, ForeignKey("knowledge_products.id"), nullable=False)
    reporter_id = Column(Integer, nullable=False)                                # USER_DB user_id (no FK)
    reason      = Column(String(30), nullable=False)                            # pii|spam|misleading|copyright|malware|other
    detail      = Column(Text, nullable=True)
    status      = Column(String(15), nullable=False, default="open")            # open|reviewed|dismissed
    admin_note  = Column(Text, nullable=True)
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("product_id", "reporter_id", name="uq_report_product_reporter"),
        Index("ix_listrep_product",  "product_id"),
        Index("ix_listrep_status",   "status"),
        Index("ix_listrep_reporter", "reporter_id"),
    )


class DmcaNotice(Base):
    """
    DMCA / copyright takedown notice submitted against a listed product.
    On receipt: product status set to 'takedown', seller notified by email.
    Admin reviews and sets status to 'actioned' or 'dismissed'.
    """
    __tablename__ = "dmca_notices"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    product_id      = Column(Integer, ForeignKey("knowledge_products.id"), nullable=False)
    claimant_name   = Column(String(200), nullable=False)
    claimant_email  = Column(String(200), nullable=False)
    description     = Column(Text, nullable=False)
    original_url    = Column(Text, nullable=True)                               # URL of original work
    status          = Column(String(15), nullable=False, default="received")    # received|under_review|actioned|dismissed
    admin_note      = Column(Text, nullable=True)
    received_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    actioned_at     = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_dmca_product", "product_id"),
        Index("ix_dmca_status",  "status"),
    )


class AuditLog(Base):
    """
    Append-only platform audit trail.
    Covers: email verification, ToS acceptance, product status changes,
    DMCA takedowns, seller bans, admin overrides.
    Never delete rows; never raise on insert failure (log and continue).
    """
    __tablename__ = "audit_log"

    id          = Column(BigInteger, primary_key=True, autoincrement=True)
    action      = Column(String(80), nullable=False)                            # e.g. 'seller.email_verified'
    actor_type  = Column(String(20), nullable=False)                            # user|admin|system
    actor_id    = Column(Integer, nullable=True)                                # user_id; NULL for system events
    target_type = Column(String(30), nullable=True)                             # 'seller_profile'|'product'|...
    target_id   = Column(Integer, nullable=True)
    detail      = Column(JSONB, nullable=True)                                  # arbitrary context blob
    ip_addr     = Column(String(45), nullable=True)                             # IPv4 or IPv6
    created_at  = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_auditlog_action",     "action"),
        Index("ix_auditlog_actor",      "actor_id"),
        Index("ix_auditlog_target",     "target_type", "target_id"),
        Index("ix_auditlog_created_at", "created_at"),
    )
