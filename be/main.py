import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import engine, Base
from payment import router as payment_router
from core.config import ALLOW_ORIGINS
from core.startup import migrate_crawl_db
from routers import market_data, analysis, auth_routes, interest, admin, developer, vn30_data, student_verify, referral, knowledge, wallet, seller, reports, takedown

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
app.include_router(vn30_data.router)
app.include_router(student_verify.router)
app.include_router(referral.router)
app.include_router(knowledge.router)
app.include_router(wallet.router)
app.include_router(seller.router)
app.include_router(reports.router)
app.include_router(takedown.router)

# ── Static files ──────────────────────────────────────────────────────────────
_cur  = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_cur)

_fe = os.path.join(_root, "fe")

_fe_pages = os.path.join(_root, "fe", "pages")

if os.path.exists(_fe):
    app.mount("/fe", StaticFiles(directory=_fe, html=True), name="fe")

# Alias /pages/* and /index.html → fe/ so standalone pages' internal links work
if os.path.exists(_fe_pages):
    app.mount("/pages", StaticFiles(directory=_fe_pages, html=True), name="fe_pages")

# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/fe/")

@app.get("/index.html")
async def index_html():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/fe/")

@app.get("/api/health")
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
