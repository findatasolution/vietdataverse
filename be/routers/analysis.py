import json
import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_argus
from middleware import authenticate_user_optional

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


@router.get("/api/v1/gold-analysis")
async def get_gold_analysis(request: Request):
    try:
        with get_engine_argus().connect() as conn:
            row = conn.execute(text("""
                SELECT date, generated_at, content
                FROM gold_analysis
                ORDER BY date DESC
                LIMIT 1
            """)).fetchone()

        if row:
            data = {
                "success": True,
                "data": {
                    "content": row[2],
                    "generated_at": row[1].isoformat() if row[1] else None,
                    "source": "AI Analysis",
                },
            }
        else:
            data = {"success": False, "data": None, "message": "No analysis available"}

        return _json_response(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold analysis: {e}")


@router.get("/api/v1/market-pulse")
async def get_market_pulse(
    request: Request,
    lang: str = Query("vi", description="Language: vi or en"),
    limit: int = Query(10, ge=1, le=50, description="Number of articles"),
    _auth: None = Depends(authenticate_user_optional),
):
    # Gate: free / unauthenticated users get only 1 article
    user = getattr(request.state, "user", None)
    user_level = (user or {}).get("user_level", "free")
    if user_level not in ("premium", "premium_developer", "admin"):
        limit = 1

    try:
        articles = []
        with get_engine_argus().connect() as conn:
            try:
                rows = conn.execute(text("""
                    SELECT id, title, brief_content, source_name, source_date,
                           url, label, mri, generated_at, lang
                    FROM mri_analysis
                    WHERE lang = :lang
                    ORDER BY generated_at DESC
                    LIMIT :limit
                """), {"lang": lang, "limit": limit}).fetchall()

                for r in rows:
                    articles.append({
                        "id": int(r[0]) if r[0] is not None else None,
                        "title": str(r[1]) if r[1] else "",
                        "brief_content": str(r[2]) if r[2] else "",
                        "source_name": str(r[3]) if r[3] else "",
                        "source_date": str(r[4]) if r[4] else None,
                        "url": str(r[5]) if r[5] else "",
                        "label": str(r[6]) if r[6] else "",
                        "mri": int(r[7]) if r[7] is not None else 0,
                        "generated_at": r[8].isoformat() if r[8] else None,
                        "lang": str(r[9]) if len(r) > 9 and r[9] else "vi",
                    })
            except Exception:
                # Fallback: table may not have lang column yet
                rows = conn.execute(text("""
                    SELECT id, title, brief_content, source_name, source_date,
                           url, label, mri, generated_at
                    FROM mri_analysis
                    ORDER BY generated_at DESC
                    LIMIT :limit
                """), {"limit": limit}).fetchall()

                for r in rows:
                    articles.append({
                        "id": int(r[0]) if r[0] is not None else None,
                        "title": str(r[1]) if r[1] else "",
                        "brief_content": str(r[2]) if r[2] else "",
                        "source_name": str(r[3]) if r[3] else "",
                        "source_date": str(r[4]) if r[4] else None,
                        "url": str(r[5]) if r[5] else "",
                        "label": str(r[6]) if r[6] else "",
                        "mri": int(r[7]) if r[7] is not None else 0,
                        "generated_at": r[8].isoformat() if r[8] else None,
                        "lang": "vi",
                    })

        return _json_response({"success": True, "data": articles, "count": len(articles)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market pulse: {e}")


@router.post("/api/v1/generate-market-pulse")
async def generate_market_pulse(request: Request):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Script lives one level up (be/), not in routers/
        script_path = os.path.join(script_dir, "..", "1s_market_pulse.py")
        script_path = os.path.normpath(script_path)

        if not os.path.exists(script_path):
            raise HTTPException(status_code=500, detail="Market pulse script not found")

        result = subprocess.run(
            ["python3", script_path],
            cwd=os.path.dirname(script_path),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            data = {
                "success": True,
                "message": "Market pulse generated successfully",
                "output": result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
            }
        else:
            data = {
                "success": False,
                "message": "Market pulse generation failed",
                "error": result.stderr[-500:] if len(result.stderr) > 500 else result.stderr,
            }

        return _json_response(data)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Market pulse generation timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate market pulse: {e}")
