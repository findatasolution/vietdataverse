from fastapi import FastAPI, HTTPException, Depends, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi import status
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os
import json
import requests
from urllib.parse import urlencode
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

# Add gzip compression (compresses responses > 1000 bytes)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Mount static directories - adjust paths for both local and Render deployment
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

# For Render deployment 
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

        response_data = {
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

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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

        response_data = {
            "success": True,
            "data": {
                "dates": dates[::-1],  # Reverse to chronological order
                "buy_prices": buy_prices[::-1],
                "sell_prices": sell_prices[::-1]
            },
            "period": period,
            "count": len(dates)
        }

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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

        response_data = {
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

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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

        response_data = {
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

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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

        response_data = {
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

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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

        response_data = {
            "success": True,
            "types": types
        }

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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
        FROM vn_bank_termdepo
        WHERE bank_code IS NOT NULL
        ORDER BY bank_code
        """

        with engine_crawl.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()

        banks = [row[0] for row in rows if row[0]]

        response_data = {
            "success": True,
            "banks": banks
        }

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

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
            response_data = {
                "success": True,
                "data": {
                    "content": row[2],
                    "generated_at": row[1].isoformat() if row[1] else None,
                    "source": "AI Analysis"
                }
            }
        else:
            response_data = {
                "success": False,
                "data": None,
                "message": "No analysis available"
            }

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold analysis: {str(e)}")

@app.get("/api/v1/market-pulse")
async def get_market_pulse(
    request: Request,
    lang: str = Query("vi", description="Language: vi or en"),
    limit: int = Query(10, ge=1, le=50, description="Number of articles")
):
    """Get latest market pulse news articles"""
    try:
        engine_argus = get_engine_argus()

        articles = []
        with engine_argus.connect() as conn:
            # Check if lang column exists
            try:
                result = conn.execute(text("""
                    SELECT id, title, brief_content, source_name, source_date, url, label, mri, generated_at, lang
                    FROM mri_analysis
                    WHERE lang = :lang
                    ORDER BY generated_at DESC
                    LIMIT :limit
                """), {"lang": lang, "limit": limit})

                rows = result.fetchall()

                # Process all data inside the connection context
                for row in rows:
                    article = {
                        "id": int(row[0]) if row[0] is not None else None,
                        "title": str(row[1]) if row[1] else "",
                        "brief_content": str(row[2]) if row[2] else "",
                        "source_name": str(row[3]) if row[3] else "",
                        "source_date": str(row[4]) if row[4] else None,
                        "url": str(row[5]) if row[5] else "",
                        "label": str(row[6]) if row[6] else "",
                        "mri": int(row[7]) if row[7] is not None else 0,
                        "generated_at": row[8].isoformat() if row[8] else None,
                        "lang": str(row[9]) if len(row) > 9 and row[9] else "vi"
                    }
                    articles.append(article)

            except Exception as e:
                # Fallback if lang column doesn't exist
                print(f"Error with lang query: {e}")
                result = conn.execute(text("""
                    SELECT id, title, brief_content, source_name, source_date, url, label, mri, generated_at
                    FROM mri_analysis
                    ORDER BY generated_at DESC
                    LIMIT :limit
                """), {"limit": limit})

                rows = result.fetchall()

                for row in rows:
                    article = {
                        "id": int(row[0]) if row[0] is not None else None,
                        "title": str(row[1]) if row[1] else "",
                        "brief_content": str(row[2]) if row[2] else "",
                        "source_name": str(row[3]) if row[3] else "",
                        "source_date": str(row[4]) if row[4] else None,
                        "url": str(row[5]) if row[5] else "",
                        "label": str(row[6]) if row[6] else "",
                        "mri": int(row[7]) if row[7] is not None else 0,
                        "generated_at": row[8].isoformat() if row[8] else None,
                        "lang": "vi"
                    }
                    articles.append(article)

        # Prepare response data
        response_data = {
            "success": True,
            "data": articles,
            "count": len(articles)
        }

        # Explicitly encode JSON and set Content-Length
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch market pulse: {str(e)}")

# ============================================================================
# USER INTEREST TRACKING ENDPOINTS
# ============================================================================

class InterestRequest(BaseModel):
    fingerprint: str = Field(..., min_length=8, max_length=64)
    source: str = Field(default="web", max_length=32)
    timestamp: Optional[str] = None
    user_agent: Optional[str] = Field(default=None, max_length=512)
    language: Optional[str] = Field(default=None, max_length=16)

@app.post("/api/v1/interest/{interest_type}")
async def save_user_interest(request: Request, interest_type: str, data: InterestRequest):
    """Save user interest in a specific item/service for admin tracking"""
    try:
        # Validate interest_type (alphanumeric + hyphen, max 64 chars)
        import re
        if not re.match(r'^[a-zA-Z0-9-]+$', interest_type) or len(interest_type) > 64:
            raise HTTPException(status_code=400, detail="Invalid interest_type")

        engine_argus = get_engine_argus()

        with engine_argus.connect() as conn:
            # Create table if not exists
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_interest (
                    id SERIAL PRIMARY KEY,
                    fingerprint VARCHAR(64) NOT NULL,
                    interest_type VARCHAR(64) NOT NULL,
                    source VARCHAR(32),
                    user_agent VARCHAR(512),
                    language VARCHAR(16),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()

            # Check for duplicate (same fingerprint + interest_type)
            result = conn.execute(text("""
                SELECT id FROM user_interest
                WHERE fingerprint = :fp
                AND interest_type = :itype
            """), {"fp": data.fingerprint, "itype": interest_type})

            if result.fetchone():
                response_data = {
                    "success": True,
                    "message": "Interest already recorded",
                    "interest_type": interest_type,
                    "duplicate": True
                }
            else:
                # Insert new interest
                conn.execute(text("""
                    INSERT INTO user_interest (fingerprint, interest_type, source, user_agent, language)
                    VALUES (:fp, :itype, :source, :ua, :lang)
                """), {
                    "fp": data.fingerprint,
                    "itype": interest_type,
                    "source": data.source,
                    "ua": data.user_agent[:512] if data.user_agent else None,
                    "lang": data.language
                })
                conn.commit()

                response_data = {
                    "success": True,
                    "message": "Interest saved successfully",
                    "interest_type": interest_type,
                    "duplicate": False
                }

        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save interest: {str(e)}")

@app.get("/api/v1/interest/stats")
async def get_interest_stats(request: Request):
    """Get interest statistics summary by type"""
    try:
        engine_argus = get_engine_argus()

        with engine_argus.connect() as conn:
            # Get total count by type
            result = conn.execute(text("""
                SELECT interest_type, COUNT(DISTINCT fingerprint) as unique_users, COUNT(*) as total
                FROM user_interest
                GROUP BY interest_type
                ORDER BY unique_users DESC
            """))
            rows = result.fetchall()

        stats = {}
        for row in rows:
            stats[row[0]] = {
                "unique_users": row[1],
                "total_records": row[2]
            }

        response_data = {
            "success": True,
            "data": stats
        }

        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")

@app.get("/api/v1/interest/details")
async def get_interest_details(
    request: Request,
    interest_type: Optional[str] = Query(None, description="Filter by interest type"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Get detailed interest records for admin tracking"""
    try:
        engine_argus = get_engine_argus()

        with engine_argus.connect() as conn:
            # Build query with optional filter
            if interest_type:
                result = conn.execute(text("""
                    SELECT id, fingerprint, interest_type, source, user_agent, language, created_at
                    FROM user_interest
                    WHERE interest_type = :itype
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {"itype": interest_type, "limit": limit, "offset": offset})
            else:
                result = conn.execute(text("""
                    SELECT id, fingerprint, interest_type, source, user_agent, language, created_at
                    FROM user_interest
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """), {"limit": limit, "offset": offset})

            rows = result.fetchall()

            # Get total count
            if interest_type:
                count_result = conn.execute(text("""
                    SELECT COUNT(*) FROM user_interest WHERE interest_type = :itype
                """), {"itype": interest_type})
            else:
                count_result = conn.execute(text("SELECT COUNT(*) FROM user_interest"))
            total = count_result.fetchone()[0]

        records = []
        for row in rows:
            records.append({
                "id": row[0],
                "fingerprint": row[1][:8] + "..." if row[1] else None,  # Truncate for privacy
                "interest_type": row[2],
                "source": row[3],
                "user_agent": row[4][:100] + "..." if row[4] and len(row[4]) > 100 else row[4],
                "language": row[5],
                "created_at": row[6].isoformat() if row[6] else None
            })

        response_data = {
            "success": True,
            "data": records,
            "total": total,
            "limit": limit,
            "offset": offset
        }

        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get details: {str(e)}")

@app.post("/api/v1/generate-market-pulse")
async def generate_market_pulse(request: Request):
    """Trigger 1s Market Pulse generation (crawl RSS, filter with AI, save to DB)"""
    try:
        import subprocess
        import os

        # Get the directory where main.py is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        market_pulse_script = os.path.join(script_dir, "1s_market_pulse.py")

        # Check if script exists
        if not os.path.exists(market_pulse_script):
            raise HTTPException(status_code=500, detail="Market pulse script not found")

        # Run the script
        result = subprocess.run(
            ["python3", market_pulse_script],
            cwd=script_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            response_data = {
                "success": True,
                "message": "Market pulse generated successfully",
                "output": result.stdout[-500:] if len(result.stdout) > 500 else result.stdout
            }
        else:
            response_data = {
                "success": False,
                "message": "Market pulse generation failed",
                "error": result.stderr[-500:] if len(result.stderr) > 500 else result.stderr
            }

        # Convert to JSON bytes with explicit encoding
        json_str = json.dumps(response_data, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')

        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Length": str(len(json_bytes))}
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Market pulse generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate market pulse: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)