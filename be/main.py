from fastapi import FastAPI, HTTPException, Depends, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os
import json
import requests
from urllib.parse import urlencode
import gzip
import time
from functools import lru_cache

# Import existing database models and functions
# Using absolute imports for local development compatibility
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, get_db
from models import User
from auth import verify_auth0_token, get_user_role, get_user_business_unit, get_user_is_admin, get_auth0_user_info, create_local_user_from_auth0, exchange_code_for_tokens
from middleware import authenticate_user, get_current_user

# Create tables
Base.metadata.create_all(bind=engine)

# ============================================================================
# SHARED DATABASE ENGINES (reuse connections instead of creating per-request)
# ============================================================================
_engine_crawl = None
_engine_global = None
_engine_argus = None

def get_engine_crawl():
    global _engine_crawl
    if _engine_crawl is None:
        db_url = os.getenv("CRAWLING_BOT_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="CRAWLING_BOT_DB not set")
        _engine_crawl = create_engine(db_url, pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=300)
    return _engine_crawl

def get_engine_global():
    global _engine_global
    if _engine_global is None:
        db_url = os.getenv("GLOBAL_INDICATOR_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="GLOBAL_INDICATOR_DB not set")
        _engine_global = create_engine(db_url, pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=300)
    return _engine_global

def get_engine_argus():
    global _engine_argus
    if _engine_argus is None:
        db_url = os.getenv("ARGUS_FINTEL_DB")
        if not db_url:
            raise HTTPException(status_code=500, detail="ARGUS_FINTEL_DB not set")
        _engine_argus = create_engine(db_url, pool_pre_ping=True, pool_size=3, max_overflow=5, pool_recycle=300)
    return _engine_argus

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

# Add response compression middleware
@app.middleware("http")
async def add_compression(request: Request, call_next):
    """Add gzip compression to responses"""
    response = await call_next(request)
    
    # Only compress if response is large enough and content type is appropriate
    if response.status_code == 200:
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > 1024:
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type or "text/" in content_type:
                # Read response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                # Compress if beneficial
                compressed_body = gzip.compress(body)
                if len(compressed_body) < len(body):
                    response.body = compressed_body
                    response.headers["Content-Encoding"] = "gzip"
                    response.headers["Content-Length"] = str(len(compressed_body))
    
    return response

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

# Only mount static directories if they exist
if os.path.exists(front_path):
    app.mount("/agent_finance/front", StaticFiles(directory=front_path, html=True), name="agent_finance_front")
    print(f"✅ Mounted front static files from: {front_path}")
else:
    print(f"⚠️  Front static directory not found: {front_path}")

if os.path.exists(vietdataverse_path):
    app.mount("/vietdataverse", StaticFiles(directory=vietdataverse_path, html=True), name="vietdataverse")
    print(f"✅ Mounted vietdataverse static files from: {vietdataverse_path}")
else:
    print(f"⚠️  VietDataverse static directory not found: {vietdataverse_path}")


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
    """Initiate Auth0 login flow"""
    try:
        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "https://api.vietdataverse.online/callback")
        
        if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID]):
            raise HTTPException(status_code=500, detail="Auth0 configuration missing")
        
        # Build Auth0 login URL
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "redirect_uri": AUTH0_CALLBACK_URL,
            "response_type": "code",
            "scope": "openid profile email"
        }
        
        auth_url = f"https://{AUTH0_DOMAIN}/authorize?{urlencode(params)}"
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/callback")
async def auth0_callback(request: Request, code: str = None, error: str = None):
    """Handle Auth0 callback"""
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"Auth0 error: {error}")
        
        if not code:
            raise HTTPException(status_code=400, detail="No authorization code provided")
        
        # Exchange code for tokens using auth module function
        tokens = exchange_code_for_tokens(code)
        id_token = tokens.get("id_token")
        
        # Get user info from ID token
        user_info = get_auth0_user_info(id_token)
        
        # Get or create user in database
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if user exists by auth0_id
        user = session.query(User).filter_by(auth0_id=user_info["auth0_id"]).first()
        
        if not user:
            # Create new user using auth module helper
            user_data = create_local_user_from_auth0(user_info)
            user = User(**user_data)
            session.add(user)
            session.commit()
        else:
            # Update user info
            user.name = user_info.get("name")
            user.picture = user_info.get("picture")
            user.email_verified = user_info.get("email_verified", False)
            session.commit()
        
        session.close()
        
        # Create JWT token for our system (using Auth0 token as access token)
        # For now, we'll return the Auth0 tokens directly
        return {
            "message": "Auth0 login successful",
            "access_token": tokens.get("access_token"),
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": tokens.get("expires_in"),
            "user": {
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "user_id": user.id,
                "auth0_id": user.auth0_id,
                "email_verified": user.email_verified
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/logout")
async def auth0_logout():
    """Logout from Auth0"""
    try:
        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        LOGOUT_URL = os.getenv("LOGOUT_URL", "https://vietdataverse.online")
        
        if not AUTH0_DOMAIN:
            raise HTTPException(status_code=500, detail="Auth0 configuration missing")
        
        # Build Auth0 logout URL
        params = {
            "client_id": AUTH0_CLIENT_ID,
            "returnTo": LOGOUT_URL
        }
        
        logout_url = f"https://{AUTH0_DOMAIN}/v2/logout?{urlencode(params)}"
        return RedirectResponse(url=logout_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/me")
async def get_current_user_info(request: Request):
    """Get current user information from Auth0 token claims + DB"""
    try:
        # Authenticate user via Auth0 token
        await authenticate_user(request)
        user = request.state.user
        auth0_id = user.get("auth0_id")

        if not auth0_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing auth0_id")

        # Look up user in DB by auth0_id, auto-create if not found
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()

        db_user = session.query(User).filter_by(auth0_id=auth0_id).first()

        if not db_user:
            # Auto-create user from Auth0 token claims (SPA flow)
            db_user = User(
                auth0_id=auth0_id,
                email=user.get("email", ""),
                role=user.get("role", "user"),
                business_unit=user.get("business_unit"),
                is_admin=user.get("is_admin", False),
            )
            session.add(db_user)
            session.commit()
            session.refresh(db_user)

        result = {
            "email": db_user.email,
            "name": db_user.name,
            "picture": db_user.picture,
            "user_id": db_user.id,
            "role": db_user.role,
            "is_admin": db_user.is_admin,
            "auth0_id": db_user.auth0_id,
            "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
            "updated_at": db_user.updated_at.isoformat() if db_user.updated_at else None,
        }
        session.close()
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

        engine_crawl = get_engine_crawl()

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

        engine_crawl = get_engine_crawl()

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

        engine_crawl = get_engine_crawl()

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

        engine_crawl = get_engine_crawl()

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

        engine_global = get_engine_global()

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

        engine_crawl = get_engine_crawl()

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

        engine_crawl = get_engine_crawl()

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
        engine_argus = get_engine_argus()

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