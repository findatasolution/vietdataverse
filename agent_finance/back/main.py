from fastapi import FastAPI, HTTPException, Depends, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import status
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os
import json
import requests
from urllib.parse import urlencode

# Import existing database models and functions
# Using absolute imports for local development compatibility
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, get_db
from models import User
from auth import verify_auth0_token
from middleware import authenticate_user, get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Agent Finance API",
    description="API for Agent Finance application with Neon database",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories - adjust paths for both local and Render deployment
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# For Render deployment (running from agent_finance/back/)
front_path = os.path.join(current_dir, "../front")
vietdataverse_path = os.path.join(project_root, "vietdataverse")

# Fallback for local development
if not os.path.exists(front_path):
    front_path = "../front"
if not os.path.exists(vietdataverse_path):
    vietdataverse_path = "../../vietdataverse"

app.mount("/agent_finance/front", StaticFiles(directory=front_path, html=True), name="agent_finance_front")
app.mount("/vietdataverse", StaticFiles(directory=vietdataverse_path, html=True), name="vietdataverse")


# ============================================================================
# LOCAL REGISTER/LOGIN REMOVED — All auth now via Auth0 Universal Login
# ============================================================================

@app.get("/")
async def root():
    return {"message": "Agent Finance API is running"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check_root():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/api/protected")
async def protected_endpoint(request: Request):
    """Protected endpoint that requires authentication"""
    try:
        # This will automatically authenticate the user
        await authenticate_user(request)
        
        # Get user info from request state
        user = request.state.user
        
        return {
            "message": "This is a protected endpoint",
            "user": user,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard")
async def dashboard_data(request: Request):
    """Dashboard endpoint with user-specific data"""
    try:
        # Authenticate user
        await authenticate_user(request)
        user = request.state.user

        # Return mock dashboard data
        return {
            "user": {
                "email": user["email"],
                "role": user["role"],
                "is_admin": user["is_admin"]
            },
            "dashboard_data": {
                "total_users": 1000,
                "active_sessions": 50,
                "last_login": datetime.now().isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# AUTH0 AUTHENTICATION ENDPOINTS
# ============================================================================

@app.get("/auth/login")
async def auth0_login():
    """Initiate Auth0 login flow — redirects to Auth0 Universal Login"""
    try:
        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "https://api.nguyenphamdieuhien.online/callback")
        AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE", "https://api.nguyenphamdieuhien.online")

        if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID]):
            raise HTTPException(status_code=500, detail="Auth0 configuration missing")

        params = {
            "client_id": AUTH0_CLIENT_ID,
            "redirect_uri": AUTH0_CALLBACK_URL,
            "response_type": "code",
            "scope": "openid profile email",
            "audience": AUTH0_API_AUDIENCE,
        }

        auth_url = f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"
        return RedirectResponse(url=auth_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/callback")
async def auth0_callback(request: Request, code: str = None, error: str = None):
    """Handle Auth0 callback — exchange code for tokens, sync user to DB, redirect to frontend"""
    FRONTEND_URL = "https://nguyenphamdieuhien.online/vietdataverse/index.html"

    try:
        if error:
            return RedirectResponse(url=f"{FRONTEND_URL}?auth_error={error}")

        if not code:
            return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=no_code")

        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
        AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "https://api.nguyenphamdieuhien.online/callback")
        AUTH0_API_AUDIENCE = os.getenv("AUTH0_API_AUDIENCE", "https://api.nguyenphamdieuhien.online")

        if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET]):
            return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=config_missing")

        # Exchange authorization code for tokens
        token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "code": code,
            "redirect_uri": AUTH0_CALLBACK_URL,
            "audience": AUTH0_API_AUDIENCE,
        }

        token_response = requests.post(token_url, json=token_data)
        if token_response.status_code != 200:
            return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=token_exchange_failed")

        tokens = token_response.json()
        access_token = tokens.get("access_token")

        # Get user info from Auth0 /userinfo endpoint
        userinfo_url = f"https://{AUTH0_DOMAIN}/userinfo"
        userinfo_response = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"}
        )

        if userinfo_response.status_code == 200:
            user_info = userinfo_response.json()

            # Sync user to local database
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=engine)
            session = Session()

            try:
                auth0_id = user_info.get("sub")
                user = session.query(User).filter_by(auth0_id=auth0_id).first()

                if not user:
                    # Check if user exists by email (legacy local user)
                    user = session.query(User).filter_by(email=user_info.get("email")).first()
                    if user:
                        # Link existing local user to Auth0
                        user.auth0_id = auth0_id
                        user.name = user_info.get("name")
                        user.picture = user_info.get("picture")
                    else:
                        # Create new user
                        user = User(
                            email=user_info.get("email"),
                            auth0_id=auth0_id,
                            name=user_info.get("name"),
                            picture=user_info.get("picture"),
                            role="user",
                            is_admin=False,
                        )
                        session.add(user)
                else:
                    # Update existing Auth0 user profile
                    user.name = user_info.get("name")
                    user.picture = user_info.get("picture")

                session.commit()
            finally:
                session.close()

        # Redirect to frontend — auth0-spa-js on the frontend will handle
        # token acquisition via getTokenSilently() after this redirect
        return RedirectResponse(url=FRONTEND_URL)

    except Exception:
        return RedirectResponse(url=f"{FRONTEND_URL}?auth_error=unexpected")

@app.get("/auth/logout")
async def auth0_logout():
    """Logout from Auth0 — clears Auth0 session and redirects to frontend"""
    try:
        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        LOGOUT_URL = os.getenv("LOGOUT_URL", "https://nguyenphamdieuhien.online/vietdataverse/index.html")

        if not AUTH0_DOMAIN:
            raise HTTPException(status_code=500, detail="Auth0 configuration missing")

        params = {
            "client_id": AUTH0_CLIENT_ID,
            "returnTo": LOGOUT_URL,
        }

        logout_url = f"https://{AUTH0_DOMAIN}/v2/logout?{urlencode(params)}"
        return RedirectResponse(url=logout_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/me")
async def get_current_user_info(request: Request):
    """Get current user information from Auth0 token + local DB"""
    try:
        await authenticate_user(request)
        user = request.state.user

        # Optionally enrich with DB profile data
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()

        db_user = session.query(User).filter_by(auth0_id=user.get("auth0_id")).first()
        session.close()

        result = {
            "auth0_id": user.get("auth0_id"),
            "email": user.get("email"),
            "role": user.get("role"),
            "business_unit": user.get("business_unit"),
            "is_admin": user.get("is_admin"),
        }

        if db_user:
            result.update({
                "user_id": db_user.id,
                "name": db_user.name,
                "picture": db_user.picture,
                "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
                "updated_at": db_user.updated_at.isoformat() if db_user.updated_at else None,
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# DATA API ENDPOINTS (Require Authentication)
# ============================================================================

def get_date_filter(period: str):
    """Convert period to date filter"""
    now = datetime.now()
    if period == '7d':
        return (now - timedelta(days=7)).strftime('%Y-%m-%d')
    elif period == '1m':
        return (now - timedelta(days=30)).strftime('%Y-%m-%d')
    elif period == '1y':
        return (now - timedelta(days=365)).strftime('%Y-%m-%d')
    else:  # 'all'
        return '2000-01-01'  # Very old date to get all data

@app.get("/api/v1/gold")
async def get_gold_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
    type: str = Query("DOJI HN", description="Gold type: DOJI HN, SJC, etc.")
):
    """Get gold price data - Public endpoint"""
    try:

        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query - Get latest crawl_time per day
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, buy_price, sell_price
        FROM (
            SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
            FROM vn_gold_24h_hist
            WHERE date >= '{date_filter}'
            AND type = '{type.replace("'", "''")}'
            ORDER BY date, crawl_time DESC
        ) subquery
        ORDER BY date DESC
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        # Format data
        dates = []
        buy_prices = []
        sell_prices = []

        for row in rows:
            dates.append(row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]))
            buy_prices.append(float(row[1]) if row[1] else 0)
            sell_prices.append(float(row[2]) if row[2] else 0)

        return {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "buy_prices": buy_prices[::-1],
                "sell_prices": sell_prices[::-1]
            },
            "type": type,
            "period": period,
            "count": len(dates)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold data: {str(e)}")

@app.get("/api/v1/silver")
async def get_silver_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all")
):
    """Get silver price data - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query - Get latest crawl_time per day
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, buy_price, sell_price
        FROM (
            SELECT DISTINCT ON (date) date, buy_price, sell_price, crawl_time
            FROM vn_silver_phuquy_hist
            WHERE date >= '{date_filter}'
            ORDER BY date, crawl_time DESC
        ) subquery
        ORDER BY date DESC
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        # Format data
        dates = []
        buy_prices = []
        sell_prices = []

        for row in rows:
            dates.append(row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]))
            buy_prices.append(float(row[1]) if row[1] else 0)
            sell_prices.append(float(row[2]) if row[2] else 0)

        return {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "buy_prices": buy_prices[::-1],
                "sell_prices": sell_prices[::-1]
            },
            "period": period,
            "count": len(dates)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch silver data: {str(e)}")

@app.get("/api/v1/sbv-interbank")
async def get_sbv_interbank_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all")
):
    """Get SBV interbank rates - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query - Get latest crawl_time per day
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, ls_quadem, ls_1m, ls_3m, rediscount_rate, refinancing_rate
        FROM (
            SELECT DISTINCT ON (date) date, ls_quadem, ls_1m, ls_3m, rediscount_rate, refinancing_rate, crawl_time
            FROM vn_sbv_interbankrate
            WHERE date >= '{date_filter}'
            ORDER BY date, crawl_time DESC
        ) subquery
        ORDER BY date DESC
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        # Format data
        dates = []
        overnight = []
        month_1 = []
        month_3 = []
        rediscount = []
        refinancing = []

        for row in rows:
            dates.append(row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]))
            overnight.append(float(row[1]) if row[1] else 0)
            month_1.append(float(row[2]) if row[2] else 0)
            month_3.append(float(row[3]) if row[3] else 0)
            rediscount.append(float(row[4]) if row[4] else 0)
            refinancing.append(float(row[5]) if row[5] else 0)

        return {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "overnight": overnight[::-1],
                "month_1": month_1[::-1],
                "month_3": month_3[::-1],
                "rediscount": rediscount[::-1],
                "refinancing": refinancing[::-1]
            },
            "period": period,
            "count": len(dates)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch SBV data: {str(e)}")

@app.get("/api/v1/termdepo")
async def get_term_deposit_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all"),
    bank: str = Query("ACB", description="Bank code: ACB, VCB, etc.")
):
    """Get term deposit rates - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query - Get latest data point per month
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, term_1m, term_3m, term_6m, term_12m, term_24m
        FROM (
            SELECT DISTINCT ON (date_trunc('month', date))
                   date, term_1m, term_3m, term_6m, term_12m, term_24m, crawl_time
            FROM vn_bank_termdepo
            WHERE date >= '{date_filter}'
            AND bank_code = '{bank.replace("'", "''")}'
            ORDER BY date_trunc('month', date), date DESC, crawl_time DESC
        ) subquery
        ORDER BY date DESC
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        # Format data
        dates = []
        term_1m = []
        term_3m = []
        term_6m = []
        term_12m = []
        term_24m = []

        for row in rows:
            dates.append(row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]))
            term_1m.append(float(row[1]) if row[1] else 0)
            term_3m.append(float(row[2]) if row[2] else 0)
            term_6m.append(float(row[3]) if row[3] else 0)
            term_12m.append(float(row[4]) if row[4] else 0)
            term_24m.append(float(row[5]) if row[5] else 0)

        return {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "term_1m": term_1m[::-1],
                "term_3m": term_3m[::-1],
                "term_6m": term_6m[::-1],
                "term_12m": term_12m[::-1],
                "term_24m": term_24m[::-1]
            },
            "bank": bank,
            "period": period,
            "count": len(dates)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch term deposit data: {str(e)}")

@app.get("/api/v1/global-macro")
async def get_global_macro_data(
    request: Request,
    period: str = Query("1m", description="Time period: 7d, 1m, 1y, all")
):
    """Get global macro indicators - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get global indicator database connection
        GLOBAL_INDICATOR_DB = os.getenv("GLOBAL_INDICATOR_DB")
        if not GLOBAL_INDICATOR_DB:
            raise HTTPException(status_code=500, detail="GLOBAL_INDICATOR_DB environment variable not set")

        engine_global = create_engine(GLOBAL_INDICATOR_DB)

        # Build query - Get latest crawl_time per day
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, gold_price, silver_price, nasdaq_price
        FROM (
            SELECT DISTINCT ON (date) date, gold_price, silver_price, nasdaq_price, crawl_time
            FROM global_macro
            WHERE date >= '{date_filter}'
            ORDER BY date, crawl_time DESC
        ) subquery
        ORDER BY date DESC
        """

        with engine_global.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        # Format data
        dates = []
        gold_prices = []
        silver_prices = []
        nasdaq_prices = []

        for row in rows:
            dates.append(row[0].strftime('%Y-%m-%d') if hasattr(row[0], 'strftime') else str(row[0]))
            gold_prices.append(float(row[1]) if row[1] else 0)
            silver_prices.append(float(row[2]) if row[2] else 0)
            nasdaq_prices.append(float(row[3]) if row[3] else 0)

        return {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "gold_prices": gold_prices[::-1],
                "silver_prices": silver_prices[::-1],
                "nasdaq_prices": nasdaq_prices[::-1]
            },
            "period": period,
            "count": len(dates)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch global macro data: {str(e)}")

# ============================================================================
# MISSING ENDPOINTS FOR FRONTEND COMPATIBILITY
# ============================================================================

@app.get("/api/v1/gold/types")
async def get_gold_types(request: Request):
    """Get available gold types - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Get unique gold types
        query = """
        SELECT DISTINCT type
        FROM vn_gold_24h_hist
        WHERE type IS NOT NULL
        ORDER BY type
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        types = [row[0] for row in rows if row[0]]

        return {
            "success": True,
            "types": types
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold types: {str(e)}")

@app.get("/api/v1/termdepo/banks")
async def get_bank_types(request: Request):
    """Get available bank codes - Public endpoint"""
    try:

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
        if not CRAWLING_BOT_DB:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB environment variable not set")

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Get unique bank codes
        query = """
        SELECT DISTINCT bank_code
        FROM vn_term_deposit
        WHERE bank_code IS NOT NULL
        ORDER BY bank_code
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        banks = [row[0] for row in rows if row[0]]

        return {
            "success": True,
            "banks": banks
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bank types: {str(e)}")

@app.get("/api/v1/gold-analysis")
async def get_gold_analysis(request: Request):
    """Get AI-generated gold analysis from ARGUS_FINTEL DB"""
    try:
        ARGUS_FINTEL_DB = os.getenv("ARGUS_FINTEL_DB")
        if not ARGUS_FINTEL_DB:
            raise HTTPException(status_code=500, detail="ARGUS_FINTEL_DB not configured")

        engine_argus = create_engine(ARGUS_FINTEL_DB)

        with engine_argus.connect() as conn:
            result = conn.execute(text("""
                SELECT date, generated_at, content
                FROM gold_analysis
                ORDER BY date DESC
                LIMIT 1
            """))
            row = result.fetchone()

        if row:
            return {
                "success": True,
                "data": {
                    "content": row[2],
                    "generated_at": row[1].isoformat() if row[1] else None,
                    "source": "AI Analysis"
                }
            }
        else:
            return {
                "success": False,
                "data": None,
                "message": "No analysis available"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold analysis: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
