"""
Takedown router — DMCA notices and admin moderation.

PUBLIC:
  POST /api/v1/takedown                    — submit DMCA notice

ADMIN:
  GET   /api/v1/admin/takedown             — list notices
  PATCH /api/v1/admin/takedown/{id}        — update status; if 'valid' → unpublish product + ban seller if needed
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_knowledge
from middleware import authenticate_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["takedown"])

VALID_TAKEDOWN_STATUSES = {"received", "under_review", "actioned", "dismissed"}


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


def _lookup_product_id_from_url(product_url: str) -> Optional[int]:
    """Parse product slug from URL and look up product_id."""
    # Expected formats:
    #   https://vietdataverse.online/pages/knowledge.html#some-slug
    #   https://vietdataverse.online/products/some-slug
    #   some-slug (plain slug)
    import re
    slug = None
    # Try fragment
    m = re.search(r"#([a-z0-9\-_]+)$", product_url.strip(), re.I)
    if m:
        slug = m.group(1)
    else:
        # Try last path segment
        m = re.search(r"/([a-z0-9\-_]+)/?$", product_url.strip(), re.I)
        if m:
            slug = m.group(1)
        else:
            # Treat entire value as slug
            slug = product_url.strip()

    if not slug:
        return None

    try:
        with get_engine_knowledge().connect() as conn:
            row = conn.execute(
                text("SELECT id FROM knowledge_products WHERE slug = :slug"),
                {"slug": slug},
            ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


# ── Schemas ───────────────────────────────────────────────────────────────────

class TakedownBody(BaseModel):
    product_url:      str
    claimant_name:    str
    claimant_email:   str
    claimant_org:     Optional[str] = None
    copyright_proof:  str
    sworn_statement:  bool


class AdminTakedownPatch(BaseModel):
    status:     str
    admin_note: str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/v1/takedown")
async def submit_takedown(body: TakedownBody, request: Request):
    """
    Public — submit a DMCA takedown notice.
    sworn_statement must be true. Sends confirmation email to claimant.
    """
    if not body.sworn_statement:
        raise HTTPException(
            status_code=400,
            detail="sworn_statement phải là true — bạn cần xác nhận tuyên bố chính thức",
        )

    if not body.claimant_name.strip():
        raise HTTPException(status_code=400, detail="claimant_name là bắt buộc")
    if not body.claimant_email.strip():
        raise HTTPException(status_code=400, detail="claimant_email là bắt buộc")
    if not body.copyright_proof.strip():
        raise HTTPException(status_code=400, detail="copyright_proof là bắt buộc")
    if not body.product_url.strip():
        raise HTTPException(status_code=400, detail="product_url là bắt buộc")

    # Try to resolve product_id from URL
    product_id = _lookup_product_id_from_url(body.product_url)
    if product_id is None:
        raise HTTPException(
            status_code=404,
            detail="Không tìm thấy sản phẩm từ URL cung cấp. Vui lòng kiểm tra lại product_url.",
        )

    try:
        with get_engine_knowledge().begin() as conn:
            row = conn.execute(text("""
                INSERT INTO dmca_notices
                    (product_id, claimant_name, claimant_email,
                     description, original_url, status, received_at)
                VALUES
                    (:pid, :name, :email,
                     :desc, :orig_url, 'received', NOW())
                RETURNING id, received_at
            """), {
                "pid":      product_id,
                "name":     body.claimant_name.strip(),
                "email":    body.claimant_email.strip(),
                "desc":     body.copyright_proof.strip(),
                "orig_url": body.product_url.strip(),
            }).fetchone()

        notice_id   = row[0]
        received_at = row[1]

        # Audit log
        try:
            from services import audit_log
            audit_log.log_event(
                "dmca_received",
                actor_type="system",
                actor_id=None,
                target_type="product",
                target_id=product_id,
                metadata={
                    "notice_id":     notice_id,
                    "claimant_email": body.claimant_email.strip(),
                },
            )
        except Exception as e:
            logger.warning("audit_log failed: %s", e)

        # Send confirmation email to claimant
        try:
            with get_engine_knowledge().connect() as conn:
                title_row = conn.execute(
                    text("SELECT title FROM knowledge_products WHERE id = :pid"),
                    {"pid": product_id},
                ).fetchone()
            product_title = title_row[0] if title_row else f"Product #{product_id}"

            from services.email import send_email
            send_email(
                to=body.claimant_email.strip(),
                subject=f"Khiếu nại DMCA đã nhận — #{notice_id}",
                template="takedown_received",
                ctx={
                    "display_name":  body.claimant_name.strip(),
                    "product_title": product_title,
                    "notice_id":     notice_id,
                    "received_at":   received_at.strftime("%d/%m/%Y %H:%M UTC") if received_at else "N/A",
                },
            )
        except Exception as e:
            logger.warning("takedown confirmation email failed notice_id=%s: %s", notice_id, e)

        return _json_response({
            "success":      True,
            "source":       "takedown",
            "count":        1,
            "data": {
                "reference_id": notice_id,
                "message":      "Khiếu nại đã được ghi nhận. Chúng tôi sẽ xử lý trong vòng 48 giờ.",
            },
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("submit_takedown error product_id=%s", product_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/v1/admin/takedown")
async def admin_list_takedowns(
    request: Request,
    status:  Optional[str] = Query("received"),
    limit:   int = Query(50, ge=1, le=200),
    offset:  int = Query(0, ge=0),
):
    """Admin: list DMCA notices, optionally filtered by status."""
    await authenticate_user(request)
    _require_admin(request)

    if status and status not in VALID_TAKEDOWN_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(VALID_TAKEDOWN_STATUSES)}",
        )

    try:
        with get_engine_knowledge().connect() as conn:
            where_sql = "WHERE dn.status = :status" if status else ""
            params: dict = {"limit": limit, "offset": offset}
            if status:
                params["status"] = status

            rows = conn.execute(text(f"""
                SELECT dn.id, dn.product_id, dn.claimant_name, dn.claimant_email,
                       dn.description, dn.original_url, dn.status, dn.admin_note,
                       dn.received_at, dn.actioned_at,
                       kp.title AS product_title, kp.slug AS product_slug
                FROM dmca_notices dn
                LEFT JOIN knowledge_products kp ON kp.id = dn.product_id
                {where_sql}
                ORDER BY dn.received_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM dmca_notices dn {where_sql}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).scalar()

        data = [{
            "id":             r[0],
            "product_id":     r[1],
            "claimant_name":  r[2],
            "claimant_email": r[3],
            "description":    r[4],
            "original_url":   r[5],
            "status":         r[6],
            "admin_note":     r[7],
            "received_at":    r[8].isoformat() if r[8] else None,
            "actioned_at":    r[9].isoformat() if r[9] else None,
            "product_title":  r[10],
            "product_slug":   r[11],
        } for r in rows]

        return _json_response({
            "success": True,
            "source":  "takedown",
            "count":   total,
            "data":    data,
        })
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/api/v1/admin/takedown/{notice_id}")
async def admin_patch_takedown(
    notice_id: int,
    body:      AdminTakedownPatch,
    request:   Request,
):
    """
    Admin: update DMCA notice status.
    If status='actioned' (valid claim):
      - unpublish the product
      - +1 violation_count on seller; ban if >= 3
    """
    await authenticate_user(request)
    _require_admin(request)

    valid_patch_statuses = {"under_review", "actioned", "dismissed"}
    if body.status not in valid_patch_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Valid: {sorted(valid_patch_statuses)}",
        )

    try:
        with get_engine_knowledge().begin() as conn:
            notice_row = conn.execute(text("""
                UPDATE dmca_notices
                SET status      = :status,
                    admin_note  = :note,
                    actioned_at = CASE WHEN :status IN ('actioned','dismissed') THEN NOW() ELSE actioned_at END
                WHERE id = :nid
                RETURNING id, product_id, status
            """), {"status": body.status, "note": body.admin_note, "nid": notice_id}).fetchone()

            if not notice_row:
                raise HTTPException(status_code=404, detail="DMCA notice not found")

            product_id = notice_row[1]

            if body.status == "actioned" and product_id:
                # Unpublish product
                conn.execute(text("""
                    UPDATE knowledge_products
                    SET status                  = 'unpublished',
                        auto_unpublished_reason = 'DMCA notice actioned',
                        unpublished_at          = NOW(),
                        updated_at              = NOW()
                    WHERE id = :pid
                      AND status NOT IN ('disabled')
                """), {"pid": product_id})

                # Get seller_id from product
                sp_row = conn.execute(text("""
                    SELECT seller_id FROM knowledge_products WHERE id = :pid
                """), {"pid": product_id}).fetchone()

                if sp_row and sp_row[0]:
                    seller_id = sp_row[0]
                    viol_row = conn.execute(text("""
                        UPDATE seller_profiles
                        SET violation_count = violation_count + 1,
                            updated_at      = NOW()
                        WHERE id = :sid
                        RETURNING violation_count
                    """), {"sid": seller_id}).fetchone()

                    if viol_row and viol_row[0] >= 3:
                        conn.execute(text("""
                            UPDATE seller_profiles
                            SET banned_at  = NOW(),
                                ban_reason = '3+ violations',
                                updated_at = NOW()
                            WHERE id = :sid AND banned_at IS NULL
                        """), {"sid": seller_id})

                # Audit log
                try:
                    from services import audit_log
                    audit_log.log_event(
                        "dmca_actioned",
                        actor_type="admin",
                        target_type="product",
                        target_id=product_id,
                        metadata={"notice_id": notice_id},
                    )
                except Exception as e:
                    logger.warning("audit_log failed: %s", e)

        return _json_response({
            "success": True,
            "source":  "takedown",
            "count":   1,
            "data": {
                "id":         notice_row[0],
                "product_id": notice_row[1],
                "status":     notice_row[2],
            },
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("admin_patch_takedown error notice_id=%s", notice_id)
        raise HTTPException(status_code=500, detail=str(exc))
