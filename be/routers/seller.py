"""
Seller router — zero-admin pipeline.

Endpoints (prefix /api/v1/seller):
  POST /register          — register as seller (replaces /apply)
  GET  /verify-email      — verify email token (public, link from email)
  POST /resend-verify     — resend verification email (auth required)
  GET  /me                — current seller profile + earnings
  POST /products          — upload product, instant auto-scan pipeline
  GET  /products          — list own products

Zero-admin flow:
  register → verify email → upload → auto-scan → published OR rejected instantly
"""

import json
import logging
import math
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.config import USD_VND_RATE, VND_PER_CREDIT
from core.engines import get_engine_knowledge, get_engine_user
from middleware import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/seller", tags=["seller"])

CURRENT_TOS_VERSION = "1.0"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5500")

VALID_CATEGORIES = {"accounting", "trading", "macro", "policy", "sentiment"}
VALID_FORMATS    = {"md", "json", "yaml", "csv"}

CONTENT_TYPE_MAP = {
    "md":   "text/markdown",
    "json": "application/json",
    "yaml": "text/yaml",
    "yml":  "text/yaml",
    "csv":  "text/csv",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(
        content=raw,
        media_type="application/json",
        headers={"Content-Length": str(len(raw))},
    )


def _require_auth(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _resolve_user_id(auth0_id: str) -> int:
    with get_engine_user().connect() as conn:
        row = conn.execute(
            text("SELECT user_id FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return row[0]


def _resolve_user_email(auth0_id: str) -> str:
    with get_engine_user().connect() as conn:
        row = conn.execute(
            text("SELECT email FROM users WHERE auth0_id = :aid"),
            {"aid": auth0_id},
        ).fetchone()
    return row[0] if row else ""


def _fix_suggestion(reason: str) -> str:
    """Map a rejection reason string to a human-readable fix suggestion."""
    r = reason.lower()
    if "too large" in r:
        return "Giảm kích thước file xuống dưới 10 MB."
    if "too small" in r or "< 100 bytes" in r:
        return "File quá ngắn — cần ít nhất 100 bytes nội dung."
    if "description too short" in r:
        return "Viết mô tả chi tiết hơn — tối thiểu 50 ký tự."
    if "invalid json" in r:
        return "Kiểm tra lại cú pháp JSON (dùng jsonlint.com)."
    if "invalid yaml" in r:
        return "Kiểm tra lại cú pháp YAML (dùng yamllint.com)."
    if "invalid csv" in r or "csv too short" in r:
        return "CSV cần ít nhất 2 dòng (header + 1 dữ liệu)."
    if "pii" in r or "cccd" in r or "phone" in r:
        return "Xóa thông tin cá nhân (CCCD, số điện thoại, email cá nhân) trước khi tải lên."
    if "secret" in r or "credential" in r or "private key" in r or "api key" in r:
        return "Xóa mọi credentials, API key, private key khỏi file."
    if "extension not allowed" in r:
        return "Chỉ chấp nhận định dạng: .md, .json, .yaml, .csv."
    if "magic bytes" in r or "executable" in r or "archive" in r:
        return "Không chấp nhận file binary/archive. Chỉ dùng text plain."
    if "utf-8" in r:
        return "File phải được encode UTF-8."
    return "Xem lại nội dung file và thử lại."


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    display_name: str
    accept_tos:   bool
    tos_version:  str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
async def register_seller(body: RegisterRequest, request: Request):
    """
    Register as a seller. Sends a verification email immediately.
    Idempotent: if already verified, returns existing profile without re-sending.
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")

    if not body.accept_tos:
        raise HTTPException(status_code=400, detail="Bạn phải đồng ý với điều khoản dịch vụ (accept_tos=true)")
    if body.tos_version != CURRENT_TOS_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Phiên bản ToS không hợp lệ. Cần: {CURRENT_TOS_VERSION}",
        )
    display_name = body.display_name.strip()
    if len(display_name) < 3 or len(display_name) > 100:
        raise HTTPException(status_code=400, detail="display_name phải từ 3-100 ký tự")

    user_id = _resolve_user_id(auth0_id)
    email   = _resolve_user_email(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            existing = conn.execute(text("""
                SELECT id, email_verified, email_verify_expires
                FROM seller_profiles
                WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

        # Already verified — idempotent return
        if existing and existing[1]:
            return _json_response({
                "success": True,
                "source":  "seller",
                "count":   1,
                "data": {
                    "already_verified": True,
                    "email_sent_to":    email,
                    "expires_in_hours": 0,
                },
            })

        # Generate new verify token
        verify_token   = secrets.token_urlsafe(32)
        verify_expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=24)
        verify_url     = f"{FRONTEND_URL}/pages/verify-email.html?token={verify_token}"

        with get_engine_knowledge().begin() as conn:
            conn.execute(text("""
                INSERT INTO seller_profiles
                    (user_id, user_email_snapshot, display_name,
                     email_verified, email_verify_token, email_verify_expires,
                     trust_tier, apply_status,
                     tos_accepted_at, tos_version, updated_at)
                VALUES
                    (:uid, :email, :dn,
                     FALSE, :token, :expires,
                     'basic', 'auto_approved',
                     NOW(), :tos_ver, NOW())
                ON CONFLICT (user_id) DO UPDATE
                    SET display_name          = EXCLUDED.display_name,
                        user_email_snapshot   = EXCLUDED.user_email_snapshot,
                        email_verify_token    = EXCLUDED.email_verify_token,
                        email_verify_expires  = EXCLUDED.email_verify_expires,
                        tos_accepted_at       = EXCLUDED.tos_accepted_at,
                        tos_version           = EXCLUDED.tos_version,
                        updated_at            = NOW()
            """), {
                "uid":     user_id,
                "email":   email,
                "dn":      display_name,
                "token":   verify_token,
                "expires": verify_expires,
                "tos_ver": CURRENT_TOS_VERSION,
            })

        # Send verify email (best-effort)
        try:
            from services.email import send_email
            send_email(
                to=email,
                subject="Xác minh email seller — Viet Dataverse",
                template="verify",
                ctx={"display_name": display_name, "verify_url": verify_url},
            )
        except Exception as e:
            logger.warning("verify email send failed user_id=%s: %s", user_id, e)

        # Audit log
        try:
            from services import audit_log
            audit_log.log_event(
                "seller_register",
                actor_type="user",
                actor_id=user_id,
                metadata={"tos_version": CURRENT_TOS_VERSION},
            )
        except Exception as e:
            logger.warning("audit_log failed: %s", e)

        return _json_response({
            "success": True,
            "source":  "seller",
            "count":   1,
            "data": {
                "email_sent_to":    email,
                "expires_in_hours": 24,
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("seller/register error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/verify-email")
async def verify_email(token: str = Query(...)):
    """
    Public endpoint — user clicks link from email.
    Validates token, sets email_verified=true, clears token.
    """
    if not token:
        raise HTTPException(status_code=400, detail="Token hết hạn hoặc không hợp lệ")

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        with get_engine_knowledge().connect() as conn:
            row = conn.execute(text("""
                SELECT id, user_id, email_verify_expires, email_verified
                FROM seller_profiles
                WHERE email_verify_token = :token
            """), {"token": token}).fetchone()

        if not row:
            raise HTTPException(status_code=400, detail="Token hết hạn hoặc không hợp lệ")

        profile_id, user_id, expires, already_verified = row

        if already_verified:
            return _json_response({"success": True, "message": "Email đã được xác minh"})

        if expires is None or now > expires:
            raise HTTPException(status_code=400, detail="Token hết hạn hoặc không hợp lệ")

        with get_engine_knowledge().begin() as conn:
            conn.execute(text("""
                UPDATE seller_profiles
                SET email_verified       = TRUE,
                    email_verify_token   = NULL,
                    email_verify_expires = NULL,
                    updated_at           = NOW()
                WHERE id = :pid
            """), {"pid": profile_id})

        try:
            from services import audit_log
            audit_log.log_event(
                "email_verified",
                actor_type="user",
                actor_id=user_id,
                target_type="seller_profile",
                target_id=profile_id,
            )
        except Exception as e:
            logger.warning("audit_log failed: %s", e)

        return _json_response({"success": True, "message": "Email đã được xác minh"})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("verify-email error token=***")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resend-verify")
async def resend_verify(request: Request):
    """
    Re-send verification email. Rate-limited: only if last send was >= 1h ago.
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)
    email    = _resolve_user_email(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            row = conn.execute(text("""
                SELECT id, display_name, email_verified, email_verify_expires
                FROM seller_profiles
                WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Seller profile not found. Register first.")

        profile_id, display_name, already_verified, expires = row

        if already_verified:
            return _json_response({"success": True, "message": "Email đã được xác minh rồi"})

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Rate limit: only resend if expires < NOW() + 23h (i.e. at least 1h since last send)
        if expires is not None and expires > now + timedelta(hours=23):
            raise HTTPException(
                status_code=429,
                detail="Vui lòng chờ ít nhất 1 giờ trước khi gửi lại email xác minh",
            )

        verify_token   = secrets.token_urlsafe(32)
        verify_expires = now + timedelta(hours=24)
        verify_url     = f"{FRONTEND_URL}/pages/verify-email.html?token={verify_token}"

        with get_engine_knowledge().begin() as conn:
            conn.execute(text("""
                UPDATE seller_profiles
                SET email_verify_token   = :token,
                    email_verify_expires = :expires,
                    updated_at           = NOW()
                WHERE id = :pid
            """), {"token": verify_token, "expires": verify_expires, "pid": profile_id})

        try:
            from services.email import send_email
            send_email(
                to=email,
                subject="Xác minh email seller — Viet Dataverse",
                template="verify",
                ctx={"display_name": display_name or email, "verify_url": verify_url},
            )
        except Exception as e:
            logger.warning("resend verify email failed user_id=%s: %s", user_id, e)

        return _json_response({
            "success": True,
            "data": {"email_sent_to": email, "expires_in_hours": 24},
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("resend-verify error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/me")
async def get_seller_profile(request: Request):
    """
    Return seller profile + earnings + trust status.
    If not registered: {"data": null, "needs_registration": true}
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            prof_row = conn.execute(text("""
                SELECT id, display_name, apply_status, apply_note,
                       email_verified, trust_tier, tos_accepted_at,
                       violation_count, banned_at, ban_reason,
                       created_at, updated_at
                FROM seller_profiles
                WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

            if not prof_row:
                return _json_response({
                    "success":            True,
                    "source":             "seller",
                    "count":              0,
                    "data":               None,
                    "needs_registration": True,
                })

            earn_row = conn.execute(text("""
                SELECT pending_vnd, paid_vnd
                FROM seller_earnings
                WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

        return _json_response({
            "success": True,
            "source":  "seller",
            "count":   1,
            "data": {
                "profile_id":      prof_row[0],
                "display_name":    prof_row[1],
                "apply_status":    prof_row[2],
                "apply_note":      prof_row[3],
                "email_verified":  prof_row[4],
                "trust_tier":      prof_row[5],
                "tos_accepted_at": prof_row[6].isoformat() if prof_row[6] else None,
                "violation_count": prof_row[7],
                "banned_at":       prof_row[8].isoformat() if prof_row[8] else None,
                "ban_reason":      prof_row[9],
                "created_at":      prof_row[10].isoformat() if prof_row[10] else None,
                "updated_at":      prof_row[11].isoformat() if prof_row[11] else None,
                "earnings": {
                    "pending_vnd": earn_row[0] if earn_row else 0,
                    "paid_vnd":    earn_row[1] if earn_row else 0,
                },
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("seller/me error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/products")
async def seller_create_product(
    request:       Request,
    file:          UploadFile = File(...),
    title:         str   = Form(...),
    slug:          str   = Form(...),
    description:   str   = Form(""),
    category:      str   = Form(...),
    fmt:           str   = Form(..., alias="format"),
    frameworks:    str   = Form(""),
    price_usd:     float = Form(0.0),
    price_credits: int   = Form(0),   # backward-compat: ignored when price_usd provided
    preview_pct:   int   = Form(25),
    version:       str   = Form("1.0"),
):
    """
    Upload a knowledge product with instant auto-scan pipeline.

    Scan chain (fail-fast):
      1. file_scan.scan_file     — security / size / extension / secrets
      2. file_scan.check_format_validity — parse JSON/YAML/CSV
      3. file_scan.check_min_content     — min 100 bytes + desc 50 chars
      4. pii_scan.scan_pii               — CCCD / phone / email threshold

    PASS all → upload R2 → INSERT published
    ANY fail  → INSERT rejected → email seller → return 400
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    # Input validation
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Valid: {sorted(VALID_CATEGORIES)}",
        )
    if fmt not in VALID_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format. Valid: {sorted(VALID_FORMATS)}",
        )
    if not (0 <= preview_pct <= 40):
        raise HTTPException(status_code=400, detail="preview_pct must be 0-40")
    # Pricing mirror-write: price_usd is primary source of truth from this release onward
    if price_usd < 0:
        raise HTTPException(status_code=400, detail="price_usd must be >= 0")
    if price_usd > 0:
        # Client sent price_usd — compute price_credits from it (ceil to avoid underpayment)
        price_credits = math.ceil(price_usd * USD_VND_RATE / VND_PER_CREDIT)
    elif price_credits > 0:
        # Backward-compat: client sent only price_credits — derive price_usd
        price_usd = round(price_credits * VND_PER_CREDIT / USD_VND_RATE, 2)
    else:
        # Both zero or not provided → free product
        price_usd = 0.0
        price_credits = 0
    if price_credits < 0:
        raise HTTPException(status_code=400, detail="price_credits must be >= 0")
    slug = slug.strip()
    if not slug or len(slug) > 120:
        raise HTTPException(status_code=400, detail="slug must be 1-120 characters")

    # Check seller profile
    try:
        with get_engine_knowledge().connect() as conn:
            seller_row = conn.execute(text("""
                SELECT id, email_verified, trust_tier
                FROM seller_profiles
                WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not seller_row:
        raise HTTPException(
            status_code=403,
            detail="Bạn cần đăng ký tài khoản người bán trước (POST /api/v1/seller/register)",
        )

    seller_profile_id, email_verified, trust_tier = seller_row

    if not email_verified:
        raise HTTPException(
            status_code=403,
            detail="Email chưa được xác minh. Vui lòng kiểm tra hộp thư và xác minh email trước khi đăng sản phẩm.",
        )

    # Check if seller is banned (banned_at set)
    try:
        with get_engine_knowledge().connect() as conn:
            ban_row = conn.execute(text("""
                SELECT banned_at FROM seller_profiles WHERE id = :spid
            """), {"spid": seller_profile_id}).fetchone()
            if ban_row and ban_row[0] is not None:
                raise HTTPException(
                    status_code=403,
                    detail="Tài khoản người bán của bạn đã bị khóa.",
                )
    except HTTPException:
        raise
    except Exception:
        pass

    # Read file
    file_bytes = await file.read()
    filename   = file.filename or f"upload.{fmt}"
    file_size  = len(file_bytes)
    ext        = os.path.splitext(filename.lower())[1].lstrip(".")

    # ── Scan chain (fail-fast) ────────────────────────────────────────────────
    from services.file_scan import scan_file, check_format_validity, check_min_content, check_knowledge_pack_structure
    from services.pii_scan import scan_pii

    failed_checks: list[dict] = []
    rejection_reason: Optional[str] = None

    checks = [
        ("security_scan",        lambda: scan_file(file_bytes, filename)),
        ("format_validity",      lambda: check_format_validity(file_bytes, ext)),
        ("min_content",          lambda: check_min_content(file_bytes, description)),
        ("pii_scan",             lambda: scan_pii(file_bytes.decode("utf-8", errors="ignore"))),
        # Structure spec only applies to .md knowledge packs
        *([("knowledge_pack_structure", lambda: check_knowledge_pack_structure(file_bytes))]
          if ext == "md" else []),
    ]

    scan_result = None
    for check_name, check_fn in checks:
        result = check_fn()
        if check_name == "security_scan":
            scan_result = result  # keep for sha256 / scanner
        if result.get("result") == "infected":
            reason_detail = result.get("detail") or result.get("reason") or {}
            if isinstance(reason_detail, dict):
                reason_text = reason_detail.get("reason", str(reason_detail))
                # Append structured error list if present (knowledge_pack_structure check)
                sub_errors = reason_detail.get("errors")
                if sub_errors:
                    reason_text = reason_text + " | " + " | ".join(sub_errors)
            else:
                reason_text = str(reason_detail)
            failed_checks.append({"name": check_name, "detail": reason_text})
            rejection_reason = reason_text
            break  # fail-fast

    file_hash = scan_result["sha256"] if scan_result else "unknown"
    scanner   = scan_result.get("scanner", "custom_rules") if scan_result else "custom_rules"
    seller_email = _resolve_user_email(auth0_id)
    display_name = ""
    try:
        with get_engine_knowledge().connect() as conn:
            dn_row = conn.execute(text(
                "SELECT display_name FROM seller_profiles WHERE id = :spid"
            ), {"spid": seller_profile_id}).fetchone()
            display_name = dn_row[0] if dn_row else seller_email
    except Exception:
        display_name = seller_email

    # ── REJECTED path ─────────────────────────────────────────────────────────
    if failed_checks:
        product_id: Optional[int] = None
        try:
            with get_engine_knowledge().begin() as conn:
                prod_row = conn.execute(text("""
                    INSERT INTO knowledge_products
                        (seller_id, title, slug, description, category, format,
                         frameworks, price_credits, price_usd, preview_pct, version,
                         file_r2_key, file_size_bytes, file_sha256,
                         scan_status, scan_result_json, status,
                         rejection_reason, created_at, updated_at)
                    VALUES
                        (:seller_id, :title, :slug, :desc, :category, :fmt,
                         :frameworks, :price_credits, :price_usd, :preview_pct, :version,
                         NULL, :file_size, :file_hash,
                         'infected', CAST(:scan_result_json AS JSONB), 'rejected',
                         :rejection_reason, NOW(), NOW())
                    RETURNING id
                """), {
                    "seller_id":        seller_profile_id,
                    "title":            title.strip(),
                    "slug":             slug,
                    "desc":             description.strip(),
                    "category":         category,
                    "fmt":              fmt,
                    "frameworks":       frameworks.strip(),
                    "price_credits":    price_credits,
                    "price_usd":        price_usd,
                    "preview_pct":      preview_pct,
                    "version":          version.strip(),
                    "file_size":        file_size,
                    "file_hash":        file_hash,
                    "scan_result_json": json.dumps(failed_checks),
                    "rejection_reason": rejection_reason,
                }).fetchone()

                product_id = prod_row[0]

                conn.execute(text("""
                    INSERT INTO file_scan_log
                        (product_id, scanner, result, detail, file_hash, scanned_at)
                    VALUES
                        (:pid, :scanner, 'infected', CAST(:detail AS JSONB), :sha256, NOW())
                """), {
                    "pid":     product_id,
                    "scanner": scanner,
                    "detail":  json.dumps(failed_checks),
                    "sha256":  file_hash,
                })
        except Exception as db_exc:
            logger.error("Failed to save rejected product for user_id=%s: %s", user_id, db_exc)

        # Send rejection email
        try:
            from services.email import send_email
            send_email(
                to=seller_email,
                subject=f"Sản phẩm chưa được duyệt — {title.strip()}",
                template="product_rejected",
                ctx={
                    "display_name":      display_name,
                    "product_title":     title.strip(),
                    "rejection_reason":  rejection_reason,
                    "failed_checks":     failed_checks,
                    "fix_suggestion":    _fix_suggestion(rejection_reason or ""),
                },
            )
        except Exception as e:
            logger.warning("product_rejected email failed user_id=%s: %s", user_id, e)

        # Audit log
        try:
            from services import audit_log
            audit_log.log_event(
                "product_rejected",
                actor_type="system",
                actor_id=user_id,
                target_type="product",
                target_id=product_id,
                metadata={"reason": rejection_reason, "slug": slug},
            )
        except Exception as e:
            logger.warning("audit_log failed: %s", e)

        raise HTTPException(
            status_code=400,
            detail=f"File bị từ chối bởi auto-scan: {rejection_reason}",
        )

    # ── PASSED path ───────────────────────────────────────────────────────────

    # Auto-inject disclaimer footer for .md knowledge packs
    if ext == "md":
        from services.file_scan import inject_disclaimer
        file_bytes = inject_disclaimer(file_bytes)
        file_size  = len(file_bytes)

    # Upload to R2
    r2_key: Optional[str] = None
    r2_key_candidate = f"products/{slug}/v{version}/{filename}"
    content_type = CONTENT_TYPE_MAP.get(fmt, "application/octet-stream")

    try:
        from core.r2 import upload_file as r2_upload
        r2_key = r2_upload(file_bytes, r2_key_candidate, content_type)
        logger.info("R2 upload OK: key=%s", r2_key)
    except ValueError as ve:
        logger.warning("R2 not configured, skipping upload: %s", ve)
        r2_key = None
    except Exception as exc:
        logger.error("R2 upload error slug=%s: %s", slug, exc)
        raise HTTPException(status_code=502, detail=f"File upload failed: {exc}")

    product_id = None
    try:
        with get_engine_knowledge().begin() as conn:
            prod_row = conn.execute(text("""
                INSERT INTO knowledge_products
                    (seller_id, title, slug, description, category, format,
                     frameworks, price_credits, price_usd, preview_pct, version,
                     file_r2_key, file_size_bytes, file_sha256,
                     scan_status, scan_result_json, status,
                     published_at, created_at, updated_at)
                VALUES
                    (:seller_id, :title, :slug, :desc, :category, :fmt,
                     :frameworks, :price_credits, :price_usd, :preview_pct, :version,
                     :file_key, :file_size, :file_hash,
                     'clean', CAST(:scan_result_json AS JSONB), 'published',
                     NOW(), NOW(), NOW())
                RETURNING id, slug, status, created_at
            """), {
                "seller_id":        seller_profile_id,
                "title":            title.strip(),
                "slug":             slug,
                "desc":             description.strip(),
                "category":         category,
                "fmt":              fmt,
                "frameworks":       frameworks.strip(),
                "price_credits":    price_credits,
                "price_usd":        price_usd,
                "preview_pct":      preview_pct,
                "version":          version.strip(),
                "file_key":         r2_key,
                "file_size":        file_size,
                "file_hash":        file_hash,
                "scan_result_json": json.dumps({"passed": True, "checks": len(checks)}),
            }).fetchone()

            product_id = prod_row[0]

            conn.execute(text("""
                INSERT INTO file_scan_log
                    (product_id, scanner, result, detail, file_hash, scanned_at)
                VALUES
                    (:pid, :scanner, 'clean', CAST(:detail AS JSONB), :sha256, NOW())
            """), {
                "pid":     product_id,
                "scanner": scanner,
                "detail":  json.dumps({"passed_checks": [c[0] for c in checks]}),
                "sha256":  file_hash,
            })

        # Send published email
        try:
            from services.email import send_email
            product_url = f"{FRONTEND_URL}/pages/knowledge.html#{slug}"
            send_email(
                to=seller_email,
                subject=f"Sản phẩm đã được duyệt — {title.strip()}",
                template="product_published",
                ctx={
                    "display_name":  display_name,
                    "product_title": title.strip(),
                    "category":      category,
                    "format":        fmt,
                    "price_credits": price_credits,
                    "product_url":   product_url,
                },
            )
        except Exception as e:
            logger.warning("product_published email failed user_id=%s: %s", user_id, e)

        # Audit log
        try:
            from services import audit_log
            audit_log.log_event(
                "product_published",
                actor_type="system",
                actor_id=user_id,
                target_type="product",
                target_id=product_id,
                metadata={"slug": slug},
            )
        except Exception as e:
            logger.warning("audit_log failed: %s", e)

        return _json_response({
            "success": True,
            "source":  "seller",
            "count":   1,
            "data": {
                "id":           prod_row[0],
                "slug":         prod_row[1],
                "status":       prod_row[2],
                "created_at":   prod_row[3].isoformat() if prod_row[3] else None,
                "file_key":     r2_key,
                "r2_uploaded":  r2_key is not None,
                "scan_summary": {"result": "clean", "checks_passed": len(checks)},
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        if "unique" in str(exc).lower() and "slug" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"Slug '{slug}' already taken")
        logger.exception("seller/products POST error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/products")
async def list_seller_products(request: Request):
    """List all products uploaded by the authenticated seller."""
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            sp_row = conn.execute(text("""
                SELECT id, trust_tier FROM seller_profiles WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

            if not sp_row:
                return _json_response({
                    "success": True,
                    "source":  "seller",
                    "count":   0,
                    "data":    [],
                })

            seller_profile_id = sp_row[0]

            rows = conn.execute(text("""
                SELECT id, slug, title, category, format, price_credits, price_usd,
                       status, scan_status, download_count, version,
                       created_at, updated_at, published_at,
                       report_count, auto_unpublished_reason
                FROM knowledge_products
                WHERE seller_id = :spid
                ORDER BY created_at DESC
            """), {"spid": seller_profile_id}).fetchall()

        data = [{
            "id":                     r[0],
            "slug":                   r[1],
            "title":                  r[2],
            "category":               r[3],
            "format":                 r[4],
            "price_credits":          r[5],
            "price_usd":              float(r[6]) if r[6] is not None else 0.0,
            "price_vnd":              int(round(float(r[6] or 0) * USD_VND_RATE)),
            "status":                 r[7],
            "scan_status":            r[8],
            "download_count":         r[9],
            "version":                r[10],
            "created_at":             r[11].isoformat() if r[11] else None,
            "updated_at":             r[12].isoformat() if r[12] else None,
            "published_at":           r[13].isoformat() if r[13] else None,
            "report_count":           r[14],
            "auto_unpublished_reason": r[15],
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "seller",
            "count":   len(data),
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("seller/products GET error user_id=%s", user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/products/{product_id}")
async def delete_seller_product(product_id: int, request: Request):
    """
    Seller deletes own product.

    Hard delete (purchases=0 AND download_count=0):
      - DELETE FROM knowledge_products WHERE id=:pid
      - R2 object deletion attempted if file_r2_key is set
      - Returns {success: true, mode: "hard"}

    Soft delete (any purchase exists OR download_count > 0):
      - UPDATE status='deleted', unpublished_at=NOW()
      - Buyers who already purchased can still download within their 30-day window
      - Returns {success: true, mode: "soft"}

    Idempotent: calling twice returns success (second call sees status='deleted' or 404).
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            # Resolve seller_profile
            sp_row = conn.execute(text("""
                SELECT id FROM seller_profiles WHERE user_id = :uid
            """), {"uid": user_id}).fetchone()

        if not sp_row:
            raise HTTPException(status_code=403, detail="Seller profile not found")

        seller_profile_id = sp_row[0]

        with get_engine_knowledge().connect() as conn:
            prod_row = conn.execute(text("""
                SELECT id, seller_id, status, download_count, file_r2_key
                FROM knowledge_products
                WHERE id = :pid
            """), {"pid": product_id}).fetchone()

        if not prod_row:
            raise HTTPException(status_code=404, detail="Product not found")

        pid, prod_seller_id, current_status, download_count, file_r2_key = prod_row

        # Ownership check
        if prod_seller_id != seller_profile_id:
            raise HTTPException(status_code=403, detail="You do not own this product")

        # Idempotent: already deleted
        if current_status == "deleted":
            return _json_response({"success": True, "mode": "soft", "already_deleted": True})

        # Count existing purchases
        with get_engine_knowledge().connect() as conn:
            purchase_count = conn.execute(text("""
                SELECT COUNT(*) FROM knowledge_purchases WHERE product_id = :pid
            """), {"pid": pid}).scalar() or 0

        # Decide: hard delete only when 0 purchases AND 0 downloads
        if purchase_count == 0 and download_count == 0:
            # Hard delete
            with get_engine_knowledge().begin() as conn:
                conn.execute(text("""
                    DELETE FROM knowledge_products WHERE id = :pid
                """), {"pid": pid})

            # Best-effort R2 object deletion
            if file_r2_key:
                try:
                    from core.r2 import _get_client, _bucket
                    client = _get_client()
                    client.delete_object(Bucket=_bucket(), Key=file_r2_key)
                    logger.info("R2 hard delete OK: key=%s product_id=%s", file_r2_key, pid)
                except ValueError:
                    # R2 not configured — non-fatal
                    logger.info("R2 not configured, skipping object delete for product_id=%s", pid)
                except Exception as r2_err:
                    # TODO: enqueue async retry if R2 delete fails
                    logger.warning("R2 delete failed for product_id=%s key=%s: %s", pid, file_r2_key, r2_err)

            # Audit log
            try:
                from services import audit_log
                audit_log.log_event(
                    "product_hard_deleted",
                    actor_type="user",
                    actor_id=user_id,
                    target_type="product",
                    target_id=pid,
                    metadata={"slug": None},
                )
            except Exception as e:
                logger.warning("audit_log failed: %s", e)

            return _json_response({"success": True, "mode": "hard"})

        else:
            # Soft delete — keep row for active buyers
            with get_engine_knowledge().begin() as conn:
                conn.execute(text("""
                    UPDATE knowledge_products
                    SET status         = 'deleted',
                        unpublished_at = NOW(),
                        updated_at     = NOW()
                    WHERE id = :pid
                """), {"pid": pid})

            # Audit log
            try:
                from services import audit_log
                audit_log.log_event(
                    "product_soft_deleted",
                    actor_type="user",
                    actor_id=user_id,
                    target_type="product",
                    target_id=pid,
                    metadata={"purchase_count": purchase_count, "download_count": download_count},
                )
            except Exception as e:
                logger.warning("audit_log failed: %s", e)

            return _json_response({"success": True, "mode": "soft"})

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("seller/products DELETE error product_id=%s user_id=%s", product_id, user_id)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Backward compat: keep /apply alive returning 410 ─────────────────────────

@router.post("/apply")
async def apply_seller_legacy(request: Request):
    """Deprecated — use POST /api/v1/seller/register instead."""
    raise HTTPException(
        status_code=410,
        detail="This endpoint has been removed. Use POST /api/v1/seller/register",
    )
