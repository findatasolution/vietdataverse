import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from payment import router as payment_router
from core.config import ALLOW_ORIGINS
from core.startup import migrate_crawl_db
from routers import market_data, analysis, auth_routes, interest, admin, developer, vn30_score, vn30_data

# ── DB schema migrations ──────────────────────────────────────────────────────
# USER_DB schema (users, payment_orders, user_interest) → Alembic (buildCommand).
# CRAWLING_BOT_DB ALTER TABLE → vẫn cần thủ công vì không dùng Alembic.
migrate_crawl_db()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Agent Finance API",
    description="API for Agent Finance application with Neon database",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-API-Key"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(payment_router)
app.include_router(market_data.router)
app.include_router(analysis.router)
app.include_router(auth_routes.router)
app.include_router(interest.router)
app.include_router(admin.router)
app.include_router(developer.router)
app.include_router(vn30_score.router)
app.include_router(vn30_data.router)

# ── Static files ──────────────────────────────────────────────────────────────
_cur  = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_cur))

_front = os.path.join(_cur, "../front")
_vdv   = os.path.join(_root, "vietdataverse")
if not os.path.exists(_front):
    _front = "../front"
if not os.path.exists(_vdv):
    _vdv = "../../vietdataverse"

if os.path.exists(_front):
    app.mount("/agent_finance/front", StaticFiles(directory=_front, html=True), name="agent_finance_front")
if os.path.exists(_vdv):
    app.mount("/vietdataverse", StaticFiles(directory=_vdv, html=True), name="vietdataverse")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"message": "Agent Finance API is running"}

@app.get("/api/health")
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
