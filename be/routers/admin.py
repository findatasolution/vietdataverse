import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_user

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


@router.get("/api/v1/admin/users")
async def get_all_users(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    try:
        with get_engine_user().connect() as conn:
            rows = conn.execute(text("""
                SELECT user_id, email, auth0_id, name, email_verified, is_admin,
                       user_level, registration_type, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """), {"limit": limit, "offset": offset}).fetchall()

            total = conn.execute(text("SELECT COUNT(*) FROM users")).fetchone()[0]

        users = [{
            "user_id":           r[0],
            "email":             r[1],
            "auth0_id":          r[2][:20] + "..." if r[2] and len(r[2]) > 20 else r[2],
            "name":              r[3],
            "email_verified":    r[4],
            "is_admin":          r[5],
            "user_level":        r[6],
            "registration_type": r[7],
            "created_at":        r[8].isoformat() if r[8] else None,
        } for r in rows]

        return _json_response({
            "success": True, "data": users,
            "total": total, "limit": limit, "offset": offset,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users: {e}")
