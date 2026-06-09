"""
Knowledge Marketplace router — Phase 1.

PUBLIC  (no auth)
  GET  /api/v1/knowledge/categories                      static list
  GET  /api/v1/knowledge/products                        list approved products
  GET  /api/v1/knowledge/products/{slug}                 detail + preview

BUYER  (requires auth)
  POST /api/v1/knowledge/products/{id}/purchase          debit credits, get license
  GET  /api/v1/knowledge/my-library                      list own active purchases
  GET  /api/v1/knowledge/download/{license_key}          presigned R2 URL (15 min)
  POST /api/v1/knowledge/purchases/{id}/refund           1-hour refund window

ADMIN  (requires is_admin or user_level='admin')
  GET   /api/v1/knowledge/admin/seller-applications      list seller profiles
  PATCH /api/v1/knowledge/admin/seller/{user_id}/approve approve / reject seller
  GET   /api/v1/knowledge/admin/products/queue           products pending_review
  PATCH /api/v1/knowledge/admin/products/{id}/status     approve / reject product
  GET   /api/v1/knowledge/admin/payouts/pending          sellers eligible for payout
  POST  /api/v1/knowledge/admin/payouts/create/{seller_user_id}   create payout
  PATCH /api/v1/knowledge/admin/payouts/{payout_id}/mark-paid     mark bank transfer done

Legacy sprint-0 admin endpoints (kept for backward compat):
  GET   /api/v1/knowledge/admin/products                 all products (any status)
  POST  /api/v1/knowledge/admin/products                 admin direct upload
  PATCH /api/v1/knowledge/admin/products/{id}/status     (same as new, merged)
"""

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel
from sqlalchemy import text

from core.config import USD_VND_RATE
from core.engines import get_engine_knowledge, get_engine_user
from middleware import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# ── Constants ─────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"accounting", "trading", "macro", "policy", "sentiment"}
VALID_FORMATS    = {"md", "json", "yaml"}

# pending_review removed — zero-admin pipeline publishes or rejects instantly.
# archived removed — replaced by disabled/unpublished in migration 005.
# VALID_STATUSES used only for admin force-override endpoints.
VALID_STATUSES   = {"published", "rejected", "unpublished", "archived", "disabled"}

# If ENABLE_ZERO_ADMIN=true (default), old admin approve-flow endpoints return 410 Gone.
_ZERO_ADMIN = os.getenv("ENABLE_ZERO_ADMIN", "true").lower() not in ("false", "0", "no")

CONTENT_TYPE_MAP = {
    "md":   "text/markdown",
    "json": "application/json",
    "yaml": "text/yaml",
}

DOWNLOAD_PRESIGN_TTL = 900  # 15 minutes

# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(
        content=raw,
        media_type="application/json",
        headers={"Content-Length": str(len(raw))},
    )


def _require_admin(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not (user.get("is_admin") or user.get("user_level") == "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _require_auth(request: Request):
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


def _row_to_list_item(row) -> dict:
    price_usd = float(row[6]) if row[6] is not None else 0.0
    return {
        "id":             row[0],
        "slug":           row[1],
        "title":          row[2],
        "category":       row[3],
        "format":         row[4],
        "frameworks":     row[5],
        "price_usd":      price_usd,
        "price_vnd":      int(round(price_usd * USD_VND_RATE)),
        "price_credits":  row[7],
        "rating_avg":     float(row[8]) if row[8] is not None else 0.0,
        "rating_count":   row[9],
        "download_count": row[10],
        "is_vd_owned":    row[11],
        "version":        row[12],
        "created_at":     row[13].isoformat() if row[13] else None,
        "description":    row[14],
        "seller_name":    row[15],
    }


def _row_to_admin_item(row) -> dict:
    price_usd = float(row[6]) if row[6] is not None else 0.0
    return {
        "id":              row[0],
        "slug":            row[1],
        "title":           row[2],
        "category":        row[3],
        "format":          row[4],
        "frameworks":      row[5],
        "price_usd":       price_usd,
        "price_vnd":       int(round(price_usd * USD_VND_RATE)),
        "price_credits":   row[7],                                                # backward-compat
        "rating_avg":      float(row[8]) if row[8] is not None else 0.0,
        "rating_count":    row[9],
        "download_count":  row[10],
        "is_vd_owned":     row[11],
        "version":         row[12],
        "created_at":      row[13].isoformat() if row[13] else None,
        "status":          row[14],
        "seller_id":       row[15],
        "file_r2_key":     row[16],
        "file_size_bytes": row[17],
    }


# ── PUBLIC endpoints ──────────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories():
    """Static list of knowledge product categories."""
    return _json_response({
        "success": True,
        "source":  "knowledge_marketplace",
        "count":   len(VALID_CATEGORIES),
        "data": [
            {"value": "accounting", "label": "Ke toan & Tai chinh doanh nghiep"},
            {"value": "trading",    "label": "Trading & Phan tich ky thuat"},
            {"value": "macro",      "label": "Vi mo Viet Nam & Toan cau"},
            {"value": "policy",     "label": "Chinh sach & Phap ly"},
            {"value": "sentiment",  "label": "Tam ly thi truong & Sentiment"},
        ],
    })


@router.get("/products")
async def list_products(
    category: Optional[str] = Query(None),
    fmt:      Optional[str] = Query(None, alias="format"),
    limit:    int = Query(20, ge=1, le=100),
    offset:   int = Query(0, ge=0),
):
    """List approved knowledge products. Optional filters: category, format."""
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Valid: {sorted(VALID_CATEGORIES)}")
    if fmt and fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format. Valid: {sorted(VALID_FORMATS)}")

    try:
        with get_engine_knowledge().connect() as conn:
            where_parts = ["kp.status IN ('approved', 'published')"]
            params: dict = {"limit": limit, "offset": offset}

            if category:
                where_parts.append("kp.category = :category")
                params["category"] = category
            if fmt:
                where_parts.append("kp.format = :fmt")
                params["fmt"] = fmt

            where_sql = "WHERE " + " AND ".join(where_parts)

            rows = conn.execute(text(f"""
                SELECT kp.id, kp.slug, kp.title, kp.category, kp.format, kp.frameworks,
                       kp.price_usd, kp.price_credits, kp.rating_avg, kp.rating_count, kp.download_count,
                       kp.is_vd_owned, kp.version, kp.created_at,
                       kp.description, sp.display_name
                FROM knowledge_products kp
                LEFT JOIN seller_profiles sp ON sp.id = kp.seller_id
                {where_sql}
                ORDER BY kp.is_vd_owned DESC, kp.rating_avg DESC, kp.created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM knowledge_products kp {where_sql}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   total,
            "data":    [_row_to_list_item(r) for r in rows],
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/products/{slug}")
async def get_product(slug: str):
    """
    Product detail + seller info + preview content from R2.
    Preview is omitted gracefully if R2 is not configured.
    """
    try:
        with get_engine_knowledge().connect() as conn:
            row = conn.execute(text("""
                SELECT kp.id, kp.slug, kp.title, kp.category, kp.format, kp.frameworks,
                       kp.price_usd, kp.price_credits, kp.rating_avg, kp.rating_count, kp.download_count,
                       kp.is_vd_owned, kp.version, kp.created_at,
                       kp.description, kp.preview_pct, kp.file_r2_key, kp.status,
                       sp.display_name, sp.linkedin_url
                FROM knowledge_products kp
                LEFT JOIN seller_profiles sp ON sp.id = kp.seller_id
                WHERE kp.slug = :slug AND kp.status IN ('approved', 'published')
            """), {"slug": slug}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Product not found")

        (pid, pslug, title, category, fmt, frameworks,
         price_usd_raw, price_credits, rating_avg, rating_count, download_count,
         is_vd_owned, version, created_at,
         description, preview_pct, file_r2_key, status,
         seller_display_name, seller_linkedin) = row
        price_usd = float(price_usd_raw) if price_usd_raw is not None else 0.0
        price_vnd = int(round(price_usd * USD_VND_RATE))

        preview = ""
        if file_r2_key and preview_pct and preview_pct > 0:
            try:
                from core.r2 import generate_preview
                preview = generate_preview(file_r2_key, preview_pct, fmt)
            except ValueError as ve:
                logger.warning("R2 preview skipped: %s", ve)
            except Exception as exc:
                logger.warning("R2 preview failed key=%s: %s", file_r2_key, exc)

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data": [{
                "id":             pid,
                "slug":           pslug,
                "title":          title,
                "category":       category,
                "format":         fmt,
                "frameworks":     frameworks,
                "price_usd":      price_usd,
                "price_vnd":      price_vnd,
                "price_credits":  price_credits,                                  # backward-compat
                "rating_avg":     float(rating_avg) if rating_avg is not None else 0.0,
                "rating_count":   rating_count,
                "download_count": download_count,
                "is_vd_owned":    is_vd_owned,
                "version":        version,
                "created_at":     created_at.isoformat() if created_at else None,
                "description":    description,
                "preview":        preview,
                "seller": {
                    "display_name": seller_display_name,
                    "linkedin_url": seller_linkedin,
                },
            }],
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── BUYER endpoints ───────────────────────────────────────────────────────────

@router.post("/products/{product_id}/purchase")
async def purchase_product(product_id: int, request: Request):
    """
    Purchase a knowledge product with credits.

    Errors:
      402 InsufficientCredits
      409 DuplicateTransaction (already purchased)
      400 ValueError (product unavailable, etc.)
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)
    email    = _resolve_user_email(auth0_id)

    try:
        from services.credit import purchase_product as _purchase
        from services.credit import InsufficientCredits, DuplicateTransaction
        result = _purchase(buyer_id=user_id, buyer_email=email, product_id=product_id)
    except InsufficientCredits as exc:
        raise HTTPException(status_code=402, detail=str(exc))
    except DuplicateTransaction as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("purchase_product error user_id=%s product_id=%s", user_id, product_id)
        raise HTTPException(status_code=500, detail=str(exc))

    # Fetch price_usd for display in purchase confirmation
    _price_usd = 0.0
    try:
        with get_engine_knowledge().connect() as _conn:
            _prow = _conn.execute(text(
                "SELECT price_usd FROM knowledge_products WHERE id = :pid"
            ), {"pid": product_id}).fetchone()
            if _prow:
                _price_usd = float(_prow[0]) if _prow[0] is not None else 0.0
    except Exception:
        pass  # non-critical; omit price fields if unavailable

    return _json_response({
        "success": True,
        "source":  "knowledge_marketplace",
        "count":   1,
        "data": {
            "purchase_id":   result["purchase_id"],
            "license_key":   result["license_key"],
            "balance_after": result["balance_after"],
            "price_usd":     _price_usd,
            "price_vnd":     int(round(_price_usd * USD_VND_RATE)),
            "credits_paid":  result.get("credits_paid", 0),
        },
    })


@router.get("/my-library")
async def my_library(request: Request):
    """List buyer's active (non-refunded) purchases with product info."""
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            rows = conn.execute(text("""
                SELECT kpu.id, kpu.license_key, kpu.status, kpu.refund_deadline,
                       kpu.credits_paid, kpu.purchased_at,
                       kp.id AS product_id, kp.slug, kp.title,
                       kp.category, kp.format, kp.version
                FROM knowledge_purchases kpu
                JOIN knowledge_products kp ON kpu.product_id = kp.id
                WHERE kpu.buyer_id = :uid AND kpu.status = 'active'
                ORDER BY kpu.purchased_at DESC
            """), {"uid": user_id}).fetchall()

        data = [{
            "purchase_id":     r[0],
            "license_key":     r[1],
            "status":          r[2],
            "refund_deadline": r[3].isoformat() if r[3] else None,
            "credits_paid":    r[4],
            "purchased_at":    r[5].isoformat() if r[5] else None,
            "product": {
                "id":       r[6],
                "slug":     r[7],
                "title":    r[8],
                "category": r[9],
                "format":   r[10],
                "version":  r[11],
            },
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   len(data),
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/download/{license_key}")
async def download_product(license_key: str, request: Request):
    """
    Verify license, log the download, increment download_count, return presigned URL.

    Checks:
      1. license_key belongs to current user
      2. purchase status = 'active'
      3. NOW() < purchased_at + 30 days (re-download window)
      4. product status = 'approved'
      5. file_r2_key must exist
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            row = conn.execute(text("""
                SELECT kpu.id, kpu.buyer_id, kpu.status, kpu.purchased_at,
                       kp.id AS product_id, kp.file_r2_key, kp.status AS product_status,
                       kp.title
                FROM knowledge_purchases kpu
                JOIN knowledge_products kp ON kpu.product_id = kp.id
                WHERE kpu.license_key = :lk
                LIMIT 1
            """), {"lk": license_key}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="License key not found")

        (purchase_id, buyer_id, purchase_status, purchased_at,
         product_id, file_r2_key, product_status, product_title) = row

        if buyer_id != user_id:
            raise HTTPException(status_code=403, detail="This license does not belong to your account")

        if purchase_status != "active":
            raise HTTPException(status_code=403, detail=f"License is {purchase_status}, not active")

        # 30-day re-download window
        if purchased_at is not None:
            now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
            window_end = purchased_at + timedelta(days=30)
            if now_utc > window_end:
                raise HTTPException(
                    status_code=403,
                    detail="Re-download window has expired (30 days from purchase)",
                )

        # Admin block — buyer cannot download while product is disabled or under takedown
        if product_status in ("disabled", "takedown"):
            raise HTTPException(
                status_code=403,
                detail="Sản phẩm này tạm thời bị chặn bởi hệ thống. Liên hệ buyer support để được hỗ trợ.",
            )

        # 'deleted' by seller — existing buyers retain download rights within 30-day window
        # All other non-visible statuses are considered unavailable
        if product_status not in ("approved", "published", "live", "deleted"):
            raise HTTPException(status_code=404, detail="Product is no longer available")

        if not file_r2_key:
            # Mock/seed data without R2 — return graceful message
            raise HTTPException(
                status_code=503,
                detail="File chưa được upload lên storage. (Mock data — chờ admin setup R2 bucket.)",
            )

        # Generate presigned URL
        from core.r2 import generate_download_url
        try:
            url = generate_download_url(file_r2_key, expiry_secs=DOWNLOAD_PRESIGN_TTL)
        except ValueError as ve:
            logger.error("R2 not configured for download: %s", ve)
            raise HTTPException(status_code=503, detail="Storage backend not configured")

        # Log download + increment counter (best-effort, in same transaction)
        try:
            with get_engine_knowledge().begin() as conn:
                conn.execute(text("""
                    INSERT INTO knowledge_download_log
                        (purchase_id, product_id, buyer_id, downloaded_at)
                    VALUES (:pid, :product_id, :uid, NOW())
                """), {"pid": purchase_id, "product_id": product_id, "uid": user_id})

                conn.execute(text("""
                    UPDATE knowledge_products
                    SET download_count = download_count + 1
                    WHERE id = :product_id
                """), {"product_id": product_id})
        except Exception as log_exc:
            logger.warning("download_log insert failed (non-fatal): %s", log_exc)

        return _json_response({
            "success":    True,
            "source":     "knowledge_marketplace",
            "count":      1,
            "data": {
                "download_url": url,
                "expires_in":   DOWNLOAD_PRESIGN_TTL,
            },
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("download error license_key=%s user_id=%s", license_key, user_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/purchases/{purchase_id}/refund")
async def refund_purchase(purchase_id: int, request: Request):
    """
    Refund a purchase within the 1-hour window (before any download).
    Credits are restored to buyer's balance.
    """
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        from services.credit import refund_purchase as _refund
        result = _refund(purchase_id=purchase_id, buyer_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("refund error purchase_id=%s user_id=%s", purchase_id, user_id)
        raise HTTPException(status_code=500, detail=str(exc))

    return _json_response({
        "success": True,
        "source":  "knowledge_marketplace",
        "count":   1,
        "data": {
            "refunded_credits": result["refunded_credits"],
        },
    })


# Keep legacy endpoint name for backward compatibility
@router.get("/my-purchases")
async def my_purchases(request: Request):
    """Legacy alias — returns all purchases (any status). Prefer /my-library for active only."""
    await authenticate_user(request)
    user = _require_auth(request)
    auth0_id = user.get("auth0_id")
    user_id  = _resolve_user_id(auth0_id)

    try:
        with get_engine_knowledge().connect() as conn:
            rows = conn.execute(text("""
                SELECT kpu.id, kpu.license_key, kpu.status, kpu.refund_deadline,
                       kpu.credits_paid, kpu.purchased_at,
                       kp.slug, kp.title, kp.category, kp.format, kp.version
                FROM knowledge_purchases kpu
                JOIN knowledge_products kp ON kpu.product_id = kp.id
                WHERE kpu.buyer_id = :uid
                ORDER BY kpu.purchased_at DESC
            """), {"uid": user_id}).fetchall()

        data = [{
            "purchase_id":     r[0],
            "license_key":     r[1],
            "status":          r[2],
            "refund_deadline": r[3].isoformat() if r[3] else None,
            "credits_paid":    r[4],
            "purchased_at":    r[5].isoformat() if r[5] else None,
            "product": {
                "slug":     r[6],
                "title":    r[7],
                "category": r[8],
                "format":   r[9],
                "version":  r[10],
            },
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   len(data),
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── ADMIN — seller management ─────────────────────────────────────────────────

@router.get("/admin/seller-applications")
async def admin_list_seller_applications(
    request: Request,
    status:  Optional[str] = Query(None),
    limit:   int = Query(50, ge=1, le=200),
    offset:  int = Query(0, ge=0),
):
    """Admin: list seller profiles, optionally filtered by apply_status."""
    await authenticate_user(request)
    _require_admin(request)

    valid_apply_statuses = {"pending", "approved", "rejected"}
    if status and status not in valid_apply_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(valid_apply_statuses)}",
        )

    try:
        with get_engine_knowledge().connect() as conn:
            where_sql = "WHERE apply_status = :status" if status else ""
            params: dict = {"limit": limit, "offset": offset}
            if status:
                params["status"] = status

            rows = conn.execute(text(f"""
                SELECT id, user_id, user_email_snapshot, display_name, bio,
                       linkedin_url, apply_status, admin_note, created_at, updated_at
                FROM seller_profiles
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM seller_profiles {where_sql}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        data = [{
            "id":           r[0],
            "user_id":      r[1],
            "email":        r[2],
            "display_name": r[3],
            "bio":          r[4],
            "linkedin_url": r[5],
            "apply_status": r[6],
            "admin_note":   r[7],
            "created_at":   r[8].isoformat() if r[8] else None,
            "updated_at":   r[9].isoformat() if r[9] else None,
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   total,
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class SellerApproveBody(BaseModel):
    approved: bool
    note:     str = ""


@router.patch("/admin/seller/{seller_user_id}/approve")
async def admin_approve_seller(
    seller_user_id: int,
    body:           SellerApproveBody,
    request:        Request,
):
    """Admin: approve or reject a seller application. Disabled in zero-admin mode."""
    await authenticate_user(request)
    _require_admin(request)

    if _ZERO_ADMIN:
        raise HTTPException(
            status_code=410,
            detail="Endpoint disabled: zero-admin mode is active. Sellers are auto-approved on register.",
        )

    new_status = "approved" if body.approved else "rejected"

    try:
        with get_engine_knowledge().begin() as conn:
            row = conn.execute(text("""
                UPDATE seller_profiles
                SET apply_status = :status,
                    admin_note   = :note,
                    updated_at   = NOW()
                WHERE user_id = :uid
                RETURNING id, display_name, apply_status
            """), {"status": new_status, "note": body.note, "uid": seller_user_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Seller profile not found")

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data": {
                "id":           row[0],
                "display_name": row[1],
                "apply_status": row[2],
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── ADMIN — product review queue ──────────────────────────────────────────────

@router.get("/admin/products/queue")
async def admin_product_queue(
    request: Request,
    limit:   int = Query(50, ge=1, le=200),
    offset:  int = Query(0, ge=0),
):
    """Admin: list products with status='pending_review'. Returns empty in zero-admin mode."""
    await authenticate_user(request)
    _require_admin(request)

    if _ZERO_ADMIN:
        raise HTTPException(
            status_code=410,
            detail="Endpoint disabled: zero-admin mode is active. Products are auto-published or rejected instantly.",
        )

    try:
        with get_engine_knowledge().connect() as conn:
            rows = conn.execute(text("""
                SELECT kp.id, kp.slug, kp.title, kp.category, kp.format, kp.frameworks,
                       kp.price_usd, kp.price_credits, kp.rating_avg, kp.rating_count, kp.download_count,
                       kp.is_vd_owned, kp.version, kp.created_at,
                       kp.status, kp.seller_id, kp.file_r2_key, kp.file_size_bytes,
                       kp.scan_status, sp.display_name
                FROM knowledge_products kp
                LEFT JOIN seller_profiles sp ON sp.id = kp.seller_id
                WHERE kp.status = 'pending_review'
                ORDER BY kp.created_at ASC
                LIMIT :limit OFFSET :offset
            """), {"limit": limit, "offset": offset}).fetchall()

            total = conn.execute(text("""
                SELECT COUNT(*) FROM knowledge_products WHERE status = 'pending_review'
            """)).scalar()

        data = [{
            "id":              r[0],
            "slug":            r[1],
            "title":           r[2],
            "category":        r[3],
            "format":          r[4],
            "frameworks":      r[5],
            "price_usd":       float(r[6]) if r[6] is not None else 0.0,
            "price_vnd":       int(round(float(r[6] or 0) * USD_VND_RATE)),
            "price_credits":   r[7],
            "rating_avg":      float(r[8]) if r[8] is not None else 0.0,
            "rating_count":    r[9],
            "download_count":  r[10],
            "is_vd_owned":     r[11],
            "version":         r[12],
            "created_at":      r[13].isoformat() if r[13] else None,
            "status":          r[14],
            "seller_id":       r[15],
            "file_r2_key":     r[16],
            "file_size_bytes": r[17],
            "scan_status":     r[18],
            "seller_name":     r[19],
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   total,
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class ProductStatusBody(BaseModel):
    status: str
    reason: str = ""


@router.patch("/admin/products/{product_id}/status")
async def admin_patch_product_status(
    product_id: int,
    body:       ProductStatusBody,
    request:    Request,
):
    """
    Admin: force-set product status (unpublish, disable, reject, archive).
    In zero-admin mode, 'approved' and 'pending_review' are blocked — use this only for takedowns.
    """
    await authenticate_user(request)
    _require_admin(request)

    # In zero-admin mode, block any attempt to set 'approved' (products self-approve on upload)
    zero_admin_blocked = {"approved", "pending_review"}
    if _ZERO_ADMIN and body.status in zero_admin_blocked:
        raise HTTPException(
            status_code=410,
            detail=f"Cannot set status='{body.status}' in zero-admin mode. Products are auto-published on upload.",
        )

    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(VALID_STATUSES)}",
        )

    try:
        with get_engine_knowledge().begin() as conn:
            row = conn.execute(text("""
                UPDATE knowledge_products
                SET status     = :status,
                    admin_note = :reason,
                    updated_at = NOW()
                WHERE id = :pid
                RETURNING id, slug, status, published_at, updated_at
            """), {"status": body.status, "reason": body.reason, "pid": product_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Product not found")

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data": {
                "id":           row[0],
                "slug":         row[1],
                "status":       row[2],
                "published_at": row[3].isoformat() if row[3] else None,
                "updated_at":   row[4].isoformat() if row[4] else None,
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── ADMIN — payout management ─────────────────────────────────────────────────

@router.get("/admin/payouts/pending")
async def admin_list_pending_payouts(request: Request):
    """Admin: list sellers eligible for payout (pending_vnd >= 500,000)."""
    await authenticate_user(request)
    _require_admin(request)

    try:
        from services.payout import list_pending_payouts
        payouts = list_pending_payouts()
        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   len(payouts),
            "data":    payouts,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/admin/payouts/create/{seller_user_id}")
async def admin_create_payout(seller_user_id: int, request: Request):
    """Admin: create a payout row for seller and reset their pending_vnd to 0."""
    await authenticate_user(request)
    _require_admin(request)

    try:
        from services.payout import create_payout
        payout_id = create_payout(seller_user_id)
        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data":    {"payout_id": payout_id},
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class MarkPaidBody(BaseModel):
    note: str = ""


@router.patch("/admin/payouts/{payout_id}/mark-paid")
async def admin_mark_payout_paid(
    payout_id: int,
    body:      MarkPaidBody,
    request:   Request,
):
    """Admin: mark a payout as paid after bank transfer is complete."""
    await authenticate_user(request)
    _require_admin(request)

    try:
        from services.payout import mark_paid
        result = mark_paid(payout_id=payout_id, admin_note=body.note or None)
        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data":    result,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Legacy admin endpoints (Sprint 0 backward compat) ────────────────────────

@router.get("/admin/products")
async def admin_list_products(
    request:  Request,
    status:   Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit:    int = Query(50, ge=1, le=200),
    offset:   int = Query(0, ge=0),
):
    """Admin: list ALL products including pending_review. Filterable by status and category."""
    await authenticate_user(request)
    _require_admin(request)

    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {sorted(VALID_STATUSES)}")
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Valid: {sorted(VALID_CATEGORIES)}")

    try:
        with get_engine_knowledge().connect() as conn:
            where_parts: list[str] = []
            params: dict = {"limit": limit, "offset": offset}

            if status:
                where_parts.append("status = :status")
                params["status"] = status
            if category:
                where_parts.append("category = :category")
                params["category"] = category

            where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

            rows = conn.execute(text(f"""
                SELECT id, slug, title, category, format, frameworks,
                       price_usd, price_credits, rating_avg, rating_count, download_count,
                       is_vd_owned, version, created_at,
                       status, seller_id, file_r2_key, file_size_bytes
                FROM knowledge_products
                {where_sql}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM knowledge_products {where_sql}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   total,
            "data":    [_row_to_admin_item(r) for r in rows],
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/admin/products")
async def admin_create_product(
    request:     Request,
    file:        UploadFile = File(...),
    title:       str  = Form(...),
    slug:        str  = Form(...),
    category:    str  = Form(...),
    fmt:         str  = Form(..., alias="format"),
    price_credits: int = Form(0),
    preview_pct: int  = Form(25),
    description: str  = Form(""),
    frameworks:  str  = Form(""),
    is_vd_owned: bool = Form(True),
):
    """
    Admin: direct product creation (sprint-0 path).
    Uses USER_DB for seller resolution (admin's auth0_id).
    """
    await authenticate_user(request)
    admin = _require_admin(request)

    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Valid: {sorted(VALID_CATEGORIES)}")
    if fmt not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Invalid format. Valid: {sorted(VALID_FORMATS)}")
    if not (0 <= preview_pct <= 40):
        raise HTTPException(status_code=400, detail="preview_pct must be 0-40")
    if price_credits < 0:
        raise HTTPException(status_code=400, detail="price_credits must be >= 0")
    slug = slug.strip()
    if not slug or len(slug) > 120:
        raise HTTPException(status_code=400, detail="slug must be 1-120 characters")

    file_bytes = await file.read()
    file_size  = len(file_bytes)
    file_hash  = hashlib.sha256(file_bytes).hexdigest()

    auth0_id = admin.get("auth0_id")
    try:
        with get_engine_user().connect() as conn:
            uid_row = conn.execute(text(
                "SELECT user_id FROM users WHERE auth0_id = :aid"
            ), {"aid": auth0_id}).fetchone()
        seller_id: Optional[int] = uid_row[0] if uid_row else None
    except Exception:
        seller_id = None

    file_r2_key: Optional[str] = None
    r2_object_key = f"knowledge/{slug}-{file_hash[:8]}.{fmt}"

    try:
        from core.r2 import upload_file
        content_type = CONTENT_TYPE_MAP.get(fmt, "application/octet-stream")
        file_r2_key = upload_file(file_bytes, r2_object_key, content_type)
    except ValueError as ve:
        logger.warning("R2 not configured, skipping upload: %s", ve)
        file_r2_key = None
    except Exception as exc:
        logger.error("R2 upload error slug=%s: %s", slug, exc)
        raise HTTPException(status_code=502, detail=f"File upload failed: {exc}")

    try:
        with get_engine_knowledge().begin() as conn:
            row = conn.execute(text("""
                INSERT INTO knowledge_products
                    (slug, seller_id, title, description, category, format, frameworks,
                     price_credits, preview_pct, file_r2_key, file_size_bytes, file_sha256,
                     is_vd_owned, status, created_at, updated_at)
                VALUES
                    (:slug, :seller_id, :title, :description, :category, :fmt, :frameworks,
                     :price_credits, :preview_pct, :file_r2_key, :file_size, :file_hash,
                     :is_vd_owned, 'pending_review', NOW(), NOW())
                RETURNING id, slug, status, created_at
            """), {
                "slug":          slug,
                "seller_id":     seller_id,
                "title":         title,
                "description":   description,
                "category":      category,
                "fmt":           fmt,
                "frameworks":    frameworks,
                "price_credits": price_credits,
                "preview_pct":   preview_pct,
                "file_r2_key":      file_r2_key,
                "file_size":     file_size,
                "file_hash":     file_hash,
                "is_vd_owned":   is_vd_owned,
            }).fetchone()

        return _json_response({
            "success": True,
            "source":  "knowledge_marketplace",
            "count":   1,
            "data": [{
                "id":          row[0],
                "slug":        row[1],
                "status":      row[2],
                "created_at":  row[3].isoformat() if row[3] else None,
                "file_r2_key":    file_r2_key,
                "r2_uploaded": file_r2_key is not None,
            }],
        })
    except HTTPException:
        raise
    except Exception as exc:
        if "unique" in str(exc).lower() and "slug" in str(exc).lower():
            raise HTTPException(status_code=409, detail=f"Slug '{slug}' is already taken")
        raise HTTPException(status_code=500, detail=str(exc))
