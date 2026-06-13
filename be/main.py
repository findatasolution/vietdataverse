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
from routers import market_data, analysis, auth_routes, interest, admin, developer, vn30_data, student_verify, referral, knowledge, wallet, seller, reports, takedown, webhooks

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

# ── API metering gate ─────────────────────────────────────────────────────────
# Open Data endpoints require a (free or paid) API key so mọi lời gọi đều đi qua
# quota + api_call_log → trả lời được "ai gọi endpoint gì, bao nhiêu, lúc nào".
# Ẩn danh (không key) → 401, đẩy user đăng nhập lấy free API key.
# Chỉ gate đúng các prefix dữ liệu; KM/wallet/seller/auth/admin không đụng tới.
# Đăng ký TRƯỚC CORS để CORS bọc ngoài → response short-circuit (401/429) vẫn có
# CORS headers (nếu không, browser/Excel sẽ thấy lỗi CORS thay vì lỗi 401 sạch).
METERED_PREFIXES = (
    "/api/v1/gold",            # gold + gold/types  (KHÔNG gồm gold-analysis)
    "/api/v1/silver",
    "/api/v1/sbv-interbank",
    "/api/v1/sbv-rate",
    "/api/v1/sbv-centralrate",
    "/api/v1/termdepo",        # termdepo + termdepo/banks
    "/api/v1/global",          # global + global-macro
    "/api/v1/vn30",            # vn30 data
    # KHÔNG gate /api/v1/macro: biểu đồ CPI công khai (app.js) gọi trực tiếp
    # /api/v1/macro/cpi cho khách vãng lai (hook), chưa có bản static JSON.
    # Các chart gold/silver/sbv/termdepo/global đọc fe/data/*.json nên gate
    # các endpoint live đó chỉ ảnh hưởng API/Excel consumer — đúng đối tượng cần đo.
)


def _is_metered(path: str) -> bool:
    if path.startswith("/api/v1/gold-analysis"):
        return False  # teaser công khai — giữ mở
    return any(path.startswith(p) for p in METERED_PREFIXES)


@app.middleware("http")
async def meter_open_data(request, call_next):
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from middleware import _auth_via_api_key, _auth_via_bearer

    path = request.url.path
    if request.method == "GET" and _is_metered(path):
        api_key = request.headers.get("X-API-Key")
        auth_header = request.headers.get("Authorization", "")
        try:
            if api_key:
                # API consumer / Excel add-in
                ok = await _auth_via_api_key(request, api_key)
            elif auth_header.startswith("Bearer "):
                # FE đã đăng nhập (download CSV, chart cần dữ liệu live)
                ok = await _auth_via_bearer(request, auth_header[7:])
            else:
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "detail": "Cần đăng nhập. Tài khoản miễn phí được 1.000 request/tháng — "
                                  "đăng nhập hoặc lấy API key tại /pages/developer.html.",
                    },
                )
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "detail": exc.detail},
                headers=getattr(exc, "headers", None),
            )
        if not ok:
            return JSONResponse(
                status_code=401,
                content={"success": False, "detail": "Thông tin xác thực không hợp lệ hoặc đã bị thu hồi."},
            )

    return await call_next(request)


# CORS + GZip added AFTER meter → wrap nó (last-added = outermost trong Starlette).
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
app.include_router(webhooks.router)

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

# Excel Add-in static files — served at /excel-addin/
_excel_addin = os.path.join(_root, "fe", "excel-addin")
if os.path.exists(_excel_addin):
    app.mount("/excel-addin", StaticFiles(directory=_excel_addin), name="excel_addin")


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
