"""
Fuel Forecast router — gated by platform subscription 'fuel-forecast-advanced'.

  GET /api/v1/fuel-forecast/{fuel}   fuel in {RON95, E5RON92, DO005S}

Auth optional. Without an active subscription: history + base scenario only,
breakdown stripped to the disclaimer. With one: full response including the
low/high scenarios and the model breakdown (k, resid_std, sigma_world).
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import get_engine_fuel, get_engine_user
from middleware import authenticate_user_optional
from services.subscription import has_active_subscription

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/fuel-forecast", tags=["fuel-forecast"])

VALID_FUELS = {"RON95", "E5RON92", "DO005S"}
PRODUCT_CODE = "fuel-forecast-advanced"


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


def _resolve_user_id_optional(auth0_id: Optional[str]) -> Optional[int]:
    if not auth0_id:
        return None
    try:
        with get_engine_user().connect() as conn:
            row = conn.execute(text(
                "SELECT user_id FROM users WHERE auth0_id = :aid"
            ), {"aid": auth0_id}).fetchone()
        return row[0] if row else None
    except Exception:
        return None


@router.get("/{fuel}")
async def get_forecast(fuel: str, request: Request, _auth: None = Depends(authenticate_user_optional)):
    if fuel not in VALID_FUELS:
        raise HTTPException(status_code=404, detail=f"Unknown fuel. Valid: {sorted(VALID_FUELS)}")

    user = getattr(request.state, "user", None)
    user_id = _resolve_user_id_optional(user.get("auth0_id")) if user else None
    # Fail soft to the free tier, same as _resolve_user_id_optional above: a
    # KNOWLEDGE_MARKET_DB hiccup (missing env var → RuntimeError, connect/pool
    # error) must not 500 a page that anonymous visitors get a clean 200 on.
    # Logged, not swallowed silently — a subscriber wrongly downgraded to free
    # needs to be visible in the logs.
    try:
        is_advanced = has_active_subscription(user_id, PRODUCT_CODE)
    except Exception:
        logger.exception("fuel-forecast: subscription check failed for user_id=%s; "
                         "falling back to free tier", user_id)
        is_advanced = False

    engine = get_engine_fuel()
    with engine.connect() as conn:
        hist = conn.execute(text("""
            SELECT period, retail_price FROM fuel_price_cycle
            WHERE fuel = :f ORDER BY period
        """), {"f": fuel}).fetchall()

        run_ts = conn.execute(text(
            "SELECT max(run_ts) FROM fuel_forecast WHERE fuel = :f"
        ), {"f": fuel}).scalar()

        fc_rows = []
        if run_ts is not None:
            fc_rows = conn.execute(text("""
                SELECT horizon, scenario, target_cycle, point, breakdown
                FROM fuel_forecast WHERE fuel = :f AND run_ts = :rt
                ORDER BY horizon
            """), {"f": fuel, "rt": run_ts}).fetchall()

    history = [{"period": str(p), "retail_price": float(r)} for p, r in hist]

    forecast = []
    for horizon, scenario, target_cycle, point, breakdown in fc_rows:
        if not is_advanced and scenario != "base":
            continue
        bd = breakdown if isinstance(breakdown, dict) else json.loads(breakdown)
        row = {
            "horizon": horizon, "scenario": scenario,
            "target_cycle": str(target_cycle), "point": float(point),
        }
        if is_advanced:
            row["breakdown"] = bd
        else:
            row["breakdown"] = {"disclaimer": bd.get("disclaimer")}
        forecast.append(row)

    return _json_response({
        "success": True, "source": "fuel-forecast", "count": len(history) + len(forecast),
        "data": {
            "fuel": fuel, "tier": "advanced" if is_advanced else "free",
            "history": history, "forecast": forecast,
        },
    })
