"""
Admin panel API.
Mọi endpoint yêu cầu user_level='admin' hoặc is_admin=True.
"""

import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from core.engines import get_engine_user
from middleware import authenticate_user
from payment import SUBSCRIPTION_PLANS, _query_payos_order

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _require_admin(request: Request):
    user = getattr(request.state, "user", None)
    if not user or not (user.get("is_admin") or user.get("user_level") == "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def _log_audit(conn, admin_user_id: int, target_user_id: Optional[int],
               action: str, payload: dict):
    conn.execute(text("""
        INSERT INTO admin_audit_log (admin_user_id, target_user_id, action, payload)
        VALUES (:aid, :tid, :act, :payload::json)
    """), {
        "aid": admin_user_id,
        "tid": target_user_id,
        "act": action,
        "payload": json.dumps(payload, default=str),
    })


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/users")
async def get_all_users(
    request: Request,
    limit: int  = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="Search by email"),
    level: Optional[str] = Query(None, description="Filter by user_level"),
    expired: Optional[bool] = Query(None, description="Filter expired subscriptions"),
):
    await authenticate_user(request)
    _require_admin(request)
    try:
        with get_engine_user().connect() as conn:
            where_clauses = []
            params: dict = {"limit": limit, "offset": offset}
            if q:
                where_clauses.append("email ILIKE :q")
                params["q"] = f"%{q}%"
            if level:
                where_clauses.append("user_level = :level")
                params["level"] = level
            if expired is True:
                where_clauses.append("premium_expiry < NOW()")
            elif expired is False:
                where_clauses.append("(premium_expiry IS NULL OR premium_expiry >= NOW())")
            where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            rows = conn.execute(text(f"""
                SELECT user_id, email, auth0_id, name, email_verified, is_admin,
                       user_level, registration_type, current_plan,
                       is_premium, premium_expiry, api_request_count, created_at, updated_at,
                       last_login_at, login_count
                FROM users
                {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM users {where}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).fetchone()[0]

        users = [{
            "user_id":           r[0],
            "email":             r[1],
            "auth0_id_short":    (r[2][:20] + "...") if r[2] and len(r[2]) > 20 else r[2],
            "name":              r[3],
            "email_verified":    r[4],
            "is_admin":          r[5],
            "user_level":        r[6],
            "registration_type": r[7],
            "current_plan":      r[8],
            "is_premium":        r[9],
            "premium_expiry":    r[10].isoformat() if r[10] else None,
            "api_request_count": r[11],
            "created_at":        r[12].isoformat() if r[12] else None,
            "updated_at":        r[13].isoformat() if r[13] else None,
            "last_login_at":     r[14].isoformat() if r[14] else None,
            "login_count":       r[15] or 0,
        } for r in rows]

        return _json_response({"success": True, "data": users, "total": total,
                               "limit": limit, "offset": offset})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users: {e}")


class UserPatchBody(BaseModel):
    user_level:     Optional[str] = None
    premium_expiry: Optional[str] = None   # ISO 8601 string or null
    is_admin:       Optional[bool] = None
    current_plan:   Optional[str] = None


@router.patch("/api/v1/admin/users/{user_id}")
async def patch_user(user_id: int, body: UserPatchBody, request: Request):
    """Manual override: user_level, premium_expiry, is_admin, current_plan."""
    await authenticate_user(request)
    admin = _require_admin(request)

    updates = {}
    if body.user_level is not None:
        updates["user_level"] = body.user_level
    if body.is_admin is not None:
        updates["is_admin"] = body.is_admin
    if body.current_plan is not None:
        updates["current_plan"] = body.current_plan
    if body.premium_expiry is not None:
        try:
            updates["premium_expiry"] = datetime.fromisoformat(body.premium_expiry)
        except ValueError:
            raise HTTPException(status_code=400, detail="premium_expiry must be ISO 8601")
    elif hasattr(body, "premium_expiry") and body.premium_expiry is None:
        updates["premium_expiry"] = None

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    params = {**updates, "uid": user_id}

    try:
        with get_engine_user().begin() as conn:
            result = conn.execute(text(f"""
                UPDATE users SET {set_clauses}, updated_at = NOW()
                WHERE user_id = :uid
                RETURNING user_id, email, user_level, premium_expiry, is_admin, current_plan
            """), params).fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="User not found")

            _log_audit(conn,
                       admin_user_id=admin["user_id"],
                       target_user_id=user_id,
                       action="patch_user",
                       payload=updates)

        return _json_response({
            "success": True,
            "user_id":        result[0],
            "email":          result[1],
            "user_level":     result[2],
            "premium_expiry": result[3].isoformat() if result[3] else None,
            "is_admin":       result[4],
            "current_plan":   result[5],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Payment orders
# ---------------------------------------------------------------------------

@router.get("/api/v1/admin/payment-orders")
async def get_payment_orders(
    request: Request,
    limit:   int = Query(50, ge=1, le=200),
    offset:  int = Query(0, ge=0),
    user_id: Optional[int] = None,
    status:  Optional[str] = None,
    plan:    Optional[str] = None,
):
    await authenticate_user(request)
    _require_admin(request)
    try:
        with get_engine_user().connect() as conn:
            where_clauses = []
            params: dict = {"limit": limit, "offset": offset}
            if user_id:
                where_clauses.append("po.user_id = :user_id")
                params["user_id"] = user_id
            if status:
                where_clauses.append("po.status = :status")
                params["status"] = status
            if plan:
                where_clauses.append("po.plan = :plan")
                params["plan"] = plan
            where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            rows = conn.execute(text(f"""
                SELECT po.order_code, po.user_id, u.email, po.plan, po.amount,
                       po.status, po.gateway, po.payos_ref, po.created_at, po.updated_at
                FROM payment_orders po
                LEFT JOIN users u ON po.user_id = u.user_id
                {where}
                ORDER BY po.created_at DESC
                LIMIT :limit OFFSET :offset
            """), params).fetchall()

            total = conn.execute(text(f"""
                SELECT COUNT(*) FROM payment_orders po {where}
            """), {k: v for k, v in params.items() if k not in ("limit", "offset")}).fetchone()[0]

        orders = [{
            "order_code":  r[0],
            "user_id":     r[1],
            "email":       r[2],
            "plan":        r[3],
            "amount":      r[4],
            "status":      r[5],
            "gateway":     r[6],
            "payos_ref":   r[7],
            "created_at":  r[8].isoformat() if r[8] else None,
            "updated_at":  r[9].isoformat() if r[9] else None,
        } for r in rows]

        return _json_response({"success": True, "data": orders,
                               "total": total, "limit": limit, "offset": offset})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/admin/payment-orders/{order_code}/reverify")
async def reverify_order(order_code: int, request: Request):
    """Re-call PayOS API để sync status cho order đang pending."""
    await authenticate_user(request)
    admin = _require_admin(request)
    try:
        payos_data = _query_payos_order(order_code)
        status = payos_data.get("data", {}).get("status", "")
        order_status = "paid" if status == "PAID" else ("cancelled" if status in ("CANCELLED", "EXPIRED") else "pending")

        with get_engine_user().begin() as conn:
            conn.execute(text("""
                UPDATE payment_orders SET status = :st, updated_at = NOW()
                WHERE order_code = :oc
            """), {"st": order_status, "oc": order_code})

            _log_audit(conn,
                       admin_user_id=admin["user_id"],
                       target_user_id=None,
                       action="reverify_order",
                       payload={"order_code": order_code, "payos_status": status, "db_status": order_status})

        return _json_response({"success": True, "order_code": order_code,
                               "payos_status": status, "db_status": order_status})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Revenue & usage dashboard
# ---------------------------------------------------------------------------

_REPORT_PERIODS = {
    "24h": {
        "label": "24 giờ qua",
        "since_sql": "NOW() - INTERVAL '24 hours'",
        "bucket_sql": "DATE_TRUNC('hour', created_at)",
        "granularity": "hour",
    },
    "7d": {
        "label": "7 ngày qua",
        "since_sql": "NOW() - INTERVAL '7 days'",
        "bucket_sql": "DATE(created_at)",
        "granularity": "day",
    },
    "ytd": {
        "label": "Từ đầu năm",
        "since_sql": "DATE_TRUNC('year', NOW())",
        "bucket_sql": "DATE_TRUNC('month', created_at)",
        "granularity": "month",
    },
}

@router.get("/api/v1/admin/dashboard")
async def admin_dashboard(
    request: Request,
    period: str = Query("24h", pattern="^(24h|7d|ytd)$"),
):
    """Revenue, engagement, API activity, and feedback for one report period."""
    await authenticate_user(request)
    _require_admin(request)
    try:
        period_config = _REPORT_PERIODS[period]
        since_sql = period_config["since_sql"]

        with get_engine_user().connect() as conn:
            # Revenue this month
            rev_this = conn.execute(text("""
                SELECT COALESCE(SUM(amount), 0)
                FROM payment_orders
                WHERE status = 'paid'
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
            """)).fetchone()[0]

            # Revenue last month
            rev_last = conn.execute(text("""
                SELECT COALESCE(SUM(amount), 0)
                FROM payment_orders
                WHERE status = 'paid'
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW() - INTERVAL '1 month')
            """)).fetchone()[0]

            # Revenue YTD
            rev_ytd = conn.execute(text("""
                SELECT COALESCE(SUM(amount), 0)
                FROM payment_orders
                WHERE status = 'paid'
                  AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW())
            """)).fetchone()[0]

            # Active subscribers by tier
            tier_rows = conn.execute(text("""
                SELECT user_level, COUNT(*) as cnt
                FROM users
                WHERE is_premium = TRUE AND (premium_expiry IS NULL OR premium_expiry >= NOW())
                GROUP BY user_level
                ORDER BY cnt DESC
            """)).fetchall()
            active_by_tier = {r[0]: r[1] for r in tier_rows}

            # Total users
            total_users = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]

            # New users today / this week / this month
            new_today = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= CURRENT_DATE
            """)).fetchone()[0]

            new_week = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= DATE_TRUNC('week', NOW())
            """)).fetchone()[0]

            new_month = conn.execute(text("""
                SELECT COUNT(*) FROM users
                WHERE created_at >= DATE_TRUNC('month', NOW())
            """)).fetchone()[0]

            # Login engagement — unique user đã từng đăng nhập + DAU/WAU/MAU
            ever_logged_in = conn.execute(text("""
                SELECT COUNT(*) FROM users WHERE login_count > 0
            """)).fetchone()[0]
            dau = conn.execute(text("""
                SELECT COUNT(DISTINCT user_id) FROM login_events
                WHERE at >= CURRENT_DATE
            """)).fetchone()[0]
            wau = conn.execute(text("""
                SELECT COUNT(DISTINCT user_id) FROM login_events
                WHERE at >= DATE_TRUNC('week', NOW())
            """)).fetchone()[0]
            mau = conn.execute(text("""
                SELECT COUNT(DISTINCT user_id) FROM login_events
                WHERE at >= DATE_TRUNC('month', NOW())
            """)).fetchone()[0]

            # Period-specific performance report. since_sql comes exclusively
            # from the allowlisted _REPORT_PERIODS mapping above.
            period_revenue = conn.execute(text(f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM payment_orders
                WHERE status = 'paid' AND created_at >= {since_sql}
            """)).fetchone()[0]
            period_new_users = conn.execute(text(f"""
                SELECT COUNT(*) FROM users WHERE created_at >= {since_sql}
            """)).fetchone()[0]
            period_unique_logins = conn.execute(text(f"""
                SELECT COUNT(DISTINCT user_id)
                FROM login_events WHERE at >= {since_sql}
            """)).fetchone()[0]
            api_row = conn.execute(text(f"""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 400) AS successful,
                    COUNT(*) FILTER (WHERE status_code >= 400) AS rejected,
                    COUNT(*) FILTER (WHERE user_id IS NOT NULL) AS recognized,
                    COUNT(*) FILTER (
                        WHERE user_id IS NULL AND status_code >= 200 AND status_code < 400
                    ) AS public_anonymous,
                    COUNT(*) FILTER (
                        WHERE user_id IS NULL AND status_code >= 400
                    ) AS anonymous_or_invalid,
                    COUNT(*) FILTER (WHERE user_id IS NOT NULL AND api_key_id IS NOT NULL) AS api_key_calls,
                    COUNT(*) FILTER (WHERE user_id IS NOT NULL AND api_key_id IS NULL) AS bearer_calls,
                    COUNT(DISTINCT user_id) AS unique_users
                FROM api_call_log
                WHERE at >= {since_sql}
            """)).fetchone()
            period_top_endpoints = conn.execute(text(f"""
                SELECT endpoint,
                       COUNT(*) AS calls,
                       COUNT(*) FILTER (WHERE status_code >= 200 AND status_code < 400) AS successful,
                       COUNT(*) FILTER (WHERE status_code >= 400) AS rejected,
                       COUNT(*) FILTER (
                           WHERE user_id IS NULL AND status_code >= 200 AND status_code < 400
                       ) AS public_anonymous,
                       COUNT(*) FILTER (
                           WHERE user_id IS NULL AND status_code >= 400
                       ) AS anonymous_or_invalid,
                       COUNT(DISTINCT user_id) AS users
                FROM api_call_log
                WHERE at >= {since_sql}
                GROUP BY endpoint
                ORDER BY calls DESC
                LIMIT 10
            """)).fetchall()
            period_top_keys = conn.execute(text(f"""
                SELECT u.email, COUNT(*) AS calls
                FROM api_call_log acl
                JOIN users u ON u.user_id = acl.user_id
                WHERE acl.at >= {since_sql} AND acl.api_key_id IS NOT NULL
                GROUP BY u.user_id, u.email
                ORDER BY calls DESC
                LIMIT 10
            """)).fetchall()

            # Anonymous experience feedback. Keep the dashboard usable on a
            # fresh database where the feedback table has not been created yet.
            feedback = {
                "total": 0,
                "avg_rating": None,
                "with_text": 0,
                "ratings": [],
                "groups": [],
                "recent": [],
            }
            feedback_exists = conn.execute(text(
                "SELECT to_regclass('public.experience_feedback') IS NOT NULL"
            )).fetchone()[0]
            if feedback_exists:
                feedback_summary = conn.execute(text(f"""
                    SELECT
                        COUNT(*) AS total,
                        ROUND(AVG(rating)::numeric, 2) AS avg_rating,
                        COUNT(*) FILTER (
                            WHERE NULLIF(TRIM(looking_for), '') IS NOT NULL
                               OR NULLIF(TRIM(improvement), '') IS NOT NULL
                        ) AS with_text
                    FROM experience_feedback
                    WHERE created_at >= {since_sql}
                """)).fetchone()
                rating_rows = conn.execute(text(f"""
                    SELECT rating, COUNT(*) AS count
                    FROM experience_feedback
                    WHERE rating IS NOT NULL AND created_at >= {since_sql}
                    GROUP BY rating
                    ORDER BY rating DESC
                """)).fetchall()
                group_rows = conn.execute(text(f"""
                    SELECT COALESCE(user_group, '(không chọn)') AS user_group,
                           COUNT(*) AS count
                    FROM experience_feedback
                    WHERE created_at >= {since_sql}
                    GROUP BY user_group
                    ORDER BY count DESC
                """)).fetchall()
                recent_rows = conn.execute(text(f"""
                    SELECT created_at, rating, user_group, looking_for,
                           improvement, page_url
                    FROM experience_feedback
                    WHERE created_at >= {since_sql}
                    ORDER BY created_at DESC
                    LIMIT 40
                """)).fetchall()
                feedback = {
                    "total": int(feedback_summary[0]),
                    "avg_rating": (
                        float(feedback_summary[1])
                        if feedback_summary[1] is not None else None
                    ),
                    "with_text": int(feedback_summary[2]),
                    "ratings": [
                        {"rating": int(r[0]), "count": int(r[1])}
                        for r in rating_rows
                    ],
                    "groups": [
                        {"user_group": r[0], "count": int(r[1])}
                        for r in group_rows
                    ],
                    "recent": [
                        {
                            "created_at": r[0],
                            "rating": r[1],
                            "user_group": r[2],
                            "looking_for": r[3],
                            "improvement": r[4],
                            "page_url": r[5],
                        }
                        for r in recent_rows
                    ],
                }

        return _json_response({
            "success": True,
            "period": {
                "key": period,
                "label": period_config["label"],
            },
            "revenue": {
                "this_month": int(rev_this),
                "last_month": int(rev_last),
                "ytd":        int(rev_ytd),
                "period_total": int(period_revenue),
            },
            "subscribers": {
                "active_by_tier": active_by_tier,
                "total_users":    int(total_users),
                "new_today":      int(new_today),
                "new_week":       int(new_week),
                "new_month":      int(new_month),
                "new_in_period":  int(period_new_users),
            },
            "logins": {
                "ever_logged_in": int(ever_logged_in),
                "dau":            int(dau),
                "wau":            int(wau),
                "mau":            int(mau),
                "unique_in_period": int(period_unique_logins),
            },
            "api_activity": {
                "total": int(api_row[0]),
                "successful": int(api_row[1]),
                "rejected": int(api_row[2]),
                "recognized": int(api_row[3]),
                "public_anonymous": int(api_row[4]),
                "anonymous_or_invalid": int(api_row[5]),
                "api_key_calls": int(api_row[6]),
                "bearer_calls": int(api_row[7]),
                "unique_users": int(api_row[8]),
                "anonymous_tracking_started_at": "2026-07-05",
            },
            "feedback": feedback,
            "top_endpoints": [
                {
                    "endpoint": r[0],
                    "calls": int(r[1]),
                    "successful": int(r[2]),
                    "rejected": int(r[3]),
                    "public_anonymous": int(r[4]),
                    "anonymous_or_invalid": int(r[5]),
                    "unique_users": int(r[6]),
                }
                for r in period_top_endpoints
            ],
            "top_api_keys": [
                {"email": r[0], "requests": int(r[1])}
                for r in period_top_keys
            ],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/admin/signup-trend")
async def signup_trend(
    request: Request,
    period: str = Query("24h", pattern="^(24h|7d|ytd)$"),
):
    """New-user trend bucketed by hour, day, or month for the report period."""
    await authenticate_user(request)
    _require_admin(request)
    try:
        config = _REPORT_PERIODS[period]
        bucket_sql = config["bucket_sql"]
        since_sql = config["since_sql"]
        with get_engine_user().connect() as conn:
            rows = conn.execute(text(f"""
                SELECT {bucket_sql} AS bucket, COUNT(*) AS count
                FROM users
                WHERE created_at >= {since_sql}
                GROUP BY 1
                ORDER BY 1
            """)).fetchall()

        return _json_response({
            "success": True,
            "period": period,
            "label": config["label"],
            "granularity": config["granularity"],
            "data": [{"bucket": str(r[0]), "count": int(r[1])} for r in rows],
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/v1/admin/users/export")
async def export_users_csv(
    request: Request,
    level: Optional[str] = Query(None, description="Filter by user_level"),
    q: Optional[str] = Query(None, description="Search by email"),
):
    """Export user list as CSV. Admin only."""
    await authenticate_user(request)
    _require_admin(request)
    try:
        with get_engine_user().connect() as conn:
            where_clauses = []
            params: dict = {}
            if q:
                where_clauses.append("email ILIKE :q")
                params["q"] = f"%{q}%"
            if level:
                where_clauses.append("user_level = :level")
                params["level"] = level
            where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            rows = conn.execute(text(f"""
                SELECT email, name, user_level, current_plan,
                       is_premium, premium_expiry, api_request_count,
                       created_at, updated_at
                FROM users
                {where}
                ORDER BY created_at DESC
            """), params).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["email", "name", "user_level", "current_plan",
                         "is_premium", "premium_expiry", "api_calls",
                         "created_at", "updated_at"])
        for r in rows:
            writer.writerow([
                r[0], r[1], r[2], r[3], r[4],
                r[5].isoformat() if r[5] else "",
                r[6],
                r[7].isoformat() if r[7] else "",
                r[8].isoformat() if r[8] else "",
            ])

        filename = f"vd_users_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.csv"
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
