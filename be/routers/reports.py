"""
Reports router — buyer reports and admin moderation.

PUBLIC / AUTH OPTIONAL:
  POST /api/v1/knowledge/products/{id}/report  — submit a report

ADMIN:
  GET   /api/v1/admin/reports                  — list reports
  PATCH /api/v1/admin/reports/{id}             — dismiss or action

Auto-unpublish logic:
  report_count >= 3 → unpublish product, +1 violation_count on seller
  violation_count >= 3 → ban seller (banned_at=NOW())
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_knowledge, get_engine_user
from middleware import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

VALID_REASON_CODES = {"copyright", "pii", "malware", "misleading", "spam", "other"}
VALID_REPORT_STATUSES = {"open", "reviewed", "dismissed"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(
        content=raw,
        media_type="application/json",
        headers={"Content-Length": str(len(raw))},
    )


def _require_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user or not (user.get("is_admin") or user.get("user_level") == "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _resolve_user_id_optional(auth0_id: Optional[str]) -> Optional[int]:
    if not auth0_id:
        return None
    try:
        with get_engine_user().connect() as conn:
            row = conn.execute(
                text("SELECT user_id FROM users WHERE auth0_id = :aid"),
                {"aid": auth0_id},
            ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _resolve_user_email_optional(auth0_id: Optional[str]) -> Optional[str]:
    if not auth0_id:
        return None
    try:
        with get_engine_user().connect() as conn:
            row = conn.execute(
                text("SELECT email FROM users WHERE auth0_id = :aid"),
                {"aid": auth0_id},
            ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ── Schemas ───────────────────────────────────────────────────────────────────

class ReportBody(BaseModel):
    reason_code:    str
    reason_text:    str = ""
    reporter_email: Optional[str] = None


class AdminReportPatch(BaseModel):
    status:     str
    admin_note: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/v1/knowledge/products/{product_id}/report")
async def report_product(product_id: int, body: ReportBody, request: Request):
    """
    Submit a report on a product. Auth optional — anonymous OK with reporter_email.

    Auto-unpublish when report_count >= 3:
      - product status → 'unpublished'
      - seller violation_count += 1
      - seller banned_at set if violation_count >= 3
    """
    if body.reason_code not in VALID_REASON_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason_code. Valid: {sorted(VALID_REASON_CODES)}",
        )

    # Auth optional
    user = getattr(request.state, "user", None)
    user_id: Optional[int] = None
    if user:
        auth0_id = user.get("auth0_id")
        if auth0_id:
            user_id = _resolve_user_id_optional(auth0_id)

    # Anonymous reporters need an email
    if user_id is None and not (body.reporter_email or "").strip():
        raise HTTPException(
            status_code=400,
            detail="reporter_email là bắt buộc cho báo cáo ẩn danh",
        )

    try:
        with get_engine_knowledge().connect() as conn:
            prod_row = conn.execute(text("""
                SELECT id, status, seller_id FROM knowledge_products WHERE id = :pid
            """), {"pid": product_id}).fetchone()

        if not prod_row:
            raise HTTPException(status_code=404, detail="Product not found")

        # Use a synthetic negative reporter_id for anonymous so the unique constraint works
        # listing_reports.UNIQUE(product_id, reporter_id) — use -1 as fallback for anonymous
        # but anonymous can report once per product globally (use 0 for anonymous, 1 per email)
        effective_reporter_id = user_id if user_id is not None else 0

        with get_engine_knowledge().begin() as conn:
            # Insert report — ignore duplicate (same user reporting same product)
            conn.execute(text("""
                INSERT INTO listing_reports
                    (product_id, reporter_id, reason, detail, status, created_at)
                VALUES
                    (:pid, :rid, :reason, :detail, 'open', NOW())
                ON CONFLICT (product_id, reporter_id) DO NOTHING
            """), {
                "pid":    product_id,
                "rid":    effective_reporter_id,
                "reason": body.reason_code,
                "detail": body.reason_text.strip() or None,
            })

            # Recount open reports (distinct reporters)
            count_row = conn.execute(text("""
                SELECT COUNT(DISTINCT reporter_id)
                FROM listing_reports
                WHERE product_id = :pid AND status = 'open'
            """), {"pid": product_id}).fetchone()
            report_count = count_row[0] if count_row else 0

            # Update product report_count
            conn.execute(text("""
                UPDATE knowledge_products
                SET report_count = :rc, updated_at = NOW()
                WHERE id = :pid
            """), {"rc": report_count, "pid": product_id})

            seller_id = prod_row[2]
            auto_unpublished = False

            if report_count >= 3 and prod_row[1] not in ("unpublished", "rejected", "disabled"):
                # Auto-unpublish product
                conn.execute(text("""
                    UPDATE knowledge_products
                    SET status                   = 'unpublished',
                        auto_unpublished_reason  = '3+ buyer reports',
                        unpublished_at           = NOW(),
                        updated_at               = NOW()
                    WHERE id = :pid
                """), {"pid": product_id})

                # Increment seller violation count
                viol_row = conn.execute(text("""
                    UPDATE seller_profiles
                    SET violation_count = violation_count + 1,
                        updated_at      = NOW()
                    WHERE id = :sid
                    RETURNING violation_count, display_name, user_id
                """), {"sid": seller_id}).fetchone()

                auto_unpublished = True

                if viol_row and viol_row[0] >= 3:
                    # Ban seller
                    conn.execute(text("""
                        UPDATE seller_profiles
                        SET banned_at   = NOW(),
                            ban_reason  = '3+ violations',
                            updated_at  = NOW()
                        WHERE id = :sid AND banned_at IS NULL
                    """), {"sid": seller_id})

            # Audit log
            try:
                from services import audit_log
                audit_log.log_event(
                    "auto_unpublish" if auto_unpublished else "product_report",
                    actor_type="user" if user_id else "system",
                    actor_id=user_id,
                    target_type="product",
                    target_id=product_id,
                    metadata={"reason_code": body.reason_code, "report_count": report_count},
                )
            except Exception as e:
                logger.warning("audit_log failed: %s", e)

        # Send email to seller if auto-unpublished
        if auto_unpublished and seller_id is not None:
            try:
                with get_engine_knowledge().connect() as conn:
                    sp_row = conn.execute(text("""
                        SELECT display_name, user_id, user_email_snapshot
                        FROM seller_profiles WHERE id = :sid
                    """), {"sid": seller_id}).fetchone()

                if sp_row:
                    with get_engine_knowledge().connect() as conn:
                        title_row = conn.execute(text("""
                            SELECT title FROM knowledge_products WHERE id = :pid
                        """), {"pid": product_id}).fetchone()
                    product_title = title_row[0] if title_row else f"Product #{product_id}"

                    try:
                        from services.email import send_email
                        send_email(
                            to=sp_row[2],
                            subject=f"Sản phẩm bị tạm gỡ — {product_title}",
                            template="product_rejected",
                            ctx={
                                "display_name":     sp_row[0] or sp_row[2],
                                "product_title":    product_title,
                                "rejection_reason": "Sản phẩm nhận được 3+ báo cáo từ người mua và đã bị tạm gỡ tự động.",
                            },
                        )
                    except Exception as e:
                        logger.warning("auto_unpublish email failed seller_id=%s: %s", seller_id, e)
            except Exception as e:
                logger.warning("seller lookup for unpublish email failed: %s", e)

        return _json_response({
            "success": True,
            "source":  "reports",
            "count":   1,
            "data": {"reported": True, "product_id": product_id},
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("report_product error product_id=%s", product_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/v1/admin/reports")
async def admin_list_reports(
    request: Request,
    status:  Optional[str] = Query("open"),
    limit:   int = Query(50, ge=1, le=200),
    offset:  int = Query(0, ge=0),
):
    """Admin: list reports, filterable by status."""
    await authenticate_user(request)
    _require_admin(request)

    if status and status not in VALID_REPORT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(VALID_REPORT_STATUSES)}",
        )

    try:
        with get_engine_knowledge().connect() as conn:
            where_sql = "WHERE lr.status = :status" if status else ""
            params: dict = {"limit": limit, "offset": offset}
            if status:
                params["status"] = status

            rows = conn.execute(text(f"""
                SELECT lr.id, lr.product_id, lr.reporter_id, lr.reason,
                       lr.detail, lr.status, lr.admin_note,
                       lr.created_at, lr.resolved_at,
                       kp.title AS product_title, kp.slug AS product_slug
                FROM listing_reports lr
                LEFT JOIN knowledge_products kp ON kp.id = lr.product_id
                {where_sql}
                ORDER BY lr.created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM listing_reports lr {where_sql}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        data = [{
            "id":            r[0],
            "product_id":    r[1],
            "reporter_id":   r[2],
            "reason":        r[3],
            "detail":        r[4],
            "status":        r[5],
            "admin_note":    r[6],
            "created_at":    r[7].isoformat() if r[7] else None,
            "resolved_at":   r[8].isoformat() if r[8] else None,
            "product_title": r[9],
            "product_slug":  r[10],
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "reports",
            "count":   total,
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/api/v1/admin/reports/{report_id}")
async def admin_patch_report(
    report_id: int,
    body:      AdminReportPatch,
    request:   Request,
):
    """Admin: dismiss or action a report."""
    await authenticate_user(request)
    _require_admin(request)

    valid_patch_statuses = {"dismissed", "actioned", "reviewed"}
    if body.status not in valid_patch_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(valid_patch_statuses)}",
        )

    try:
        with get_engine_knowledge().begin() as conn:
            row = conn.execute(text("""
                UPDATE listing_reports
                SET status      = :status,
                    admin_note  = :note,
                    resolved_at = NOW()
                WHERE id = :rid
                RETURNING id, product_id, status
            """), {"status": body.status, "note": body.admin_note, "rid": report_id}).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Report not found")

        return _json_response({
            "success": True,
            "source":  "reports",
            "count":   1,
            "data": {"id": row[0], "product_id": row[1], "status": row[2]},
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
