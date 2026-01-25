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

# Import existing database models and functions
# Using absolute imports for local development compatibility
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, Base, get_db
from models import User
from auth import hash_password, verify_password, create_access_token, decode_access_token
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

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=6, max_length=72)
    phone: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/api/register")
async def register_user(request: RegisterRequest):
    """Register a new user"""
    try:
        # Check if user already exists
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        existing_user = session.query(User).filter_by(email=request.email).first()
        if existing_user:
            session.close()
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password
        password_hash = hash_password(request.password)

        # Create new user
        new_user = User(
            email=request.email,
            password_hash=password_hash
        )
        
        # Add to database
        session.add(new_user)
        session.commit()
        session.close()
        
        return {"message": "User registered successfully"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login")
async def login_user(request: LoginRequest):
    """Login user and return JWT token"""
    try:
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Find user by email
        user = session.query(User).filter_by(email=request.email).first()
        session.close()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Verify password
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Create JWT token
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "role": user.role,
                "is_admin": user.is_admin
            }
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "email": user.email,
            "user_id": user.id
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "https://nguyenphamdieuhien.online/callback")
        
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
        
        # Exchange code for tokens
        AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
        AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
        AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
        AUTH0_CALLBACK_URL = os.getenv("AUTH0_CALLBACK_URL", "https://nguyenphamdieuhien.online/callback")
        
        if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET]):
            raise HTTPException(status_code=500, detail="Auth0 configuration missing")
        
        # Exchange code for tokens
        token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
        token_data = {
            "grant_type": "authorization_code",
            "client_id": AUTH0_CLIENT_ID,
            "client_secret": AUTH0_CLIENT_SECRET,
            "code": code,
            "redirect_uri": AUTH0_CALLBACK_URL
        }
        
        token_response = requests.post(token_url, json=token_data)
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange code for tokens")
        
        tokens = token_response.json()
        id_token = tokens.get("id_token")
        
        # Decode ID token to get user info
        from auth import decode_access_token
        user_info = decode_access_token(id_token)
        
        # Get or create user in database
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Check if user exists by auth0_id
        user = session.query(User).filter_by(auth0_id=user_info.get("sub")).first()
        
        if not user:
            # Create new user
            user = User(
                email=user_info.get("email"),
                auth0_id=user_info.get("sub"),
                name=user_info.get("name"),
                picture=user_info.get("picture"),
                role="user",
                is_admin=False
            )
            session.add(user)
            session.commit()
        else:
            # Update user info
            user.name = user_info.get("name")
            user.picture = user_info.get("picture")
            session.commit()
        
        session.close()
        
        # Create JWT token for our system
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "role": user.role,
                "is_admin": user.is_admin,
                "auth0_id": user.auth0_id
            }
        )
        
        # Return success response
        return {
            "message": "Auth0 login successful",
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "user_id": user.id
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
        LOGOUT_URL = os.getenv("LOGOUT_URL", "https://nguyenphamdieuhien.online")
        
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
    """Get current user information"""
    try:
        # Authenticate user
        await authenticate_user(request)
        user = request.state.user
        
        # Get full user info from database
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        db_user = session.query(User).filter_by(id=user["user_id"]).first()
        session.close()
        
        if not db_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "email": db_user.email,
            "name": db_user.name,
            "picture": db_user.picture,
            "user_id": db_user.id,
            "role": db_user.role,
            "is_admin": db_user.is_admin,
            "auth0_id": db_user.auth0_id,
            "created_at": db_user.created_at.isoformat(),
            "updated_at": db_user.updated_at.isoformat()
        }
        
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

        # Build query - Get latest crawl_time per day
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, term_1m, term_3m, term_6m, term_12m, term_24m
        FROM (
            SELECT DISTINCT ON (date) date, term_1m, term_3m, term_6m, term_12m, term_24m, crawl_time
            FROM vn_bank_termdepo
            WHERE date >= '{date_filter}'
            AND bank_code = '{bank.replace("'", "''")}'
            ORDER BY date, crawl_time DESC
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
    """Get AI-generated gold analysis - Public endpoint"""
    try:

        # For now, return a mock analysis
        # In a real implementation, this would call your AI agent
        analysis = {
            "content": """
                <h3>Diễn biến thị trường vàng toàn cầu</h3>
                <p>
                    Giá vàng tương lai trên sàn COMEX đạt <strong>$2,690/oz</strong>, tăng 1.2% so với phiên giao dịch trước đó, phản ánh tâm lý lo ngại về lạm phát toàn cầu và căng thẳng địa chính trị gia tăng.
                    Chỉ số NASDAQ Composite ghi nhận mức <strong>19,630 điểm</strong>, giảm 0.8% trong tuần qua, khiến dòng vốn chuyển hướng sang tài sản trú ẩn an toàn như vàng và trái phiếu chính phủ.
                    Giá bạc giao ngay tại thị trường quốc tế đạt <strong>$31.2/oz</strong>, tăng 2.1% theo xu hướng của vàng, cho thấy kim loại quý đang được ưa chuộng trong bối cảnh bất ổn kinh tế.
                </p>

                <h3>Thị trường vàng trong nước</h3>
                <p>
                    Vàng SJC tại Hà Nội hôm nay giao dịch ở mức <strong>160.0 - 160.0 triệu đồng/lượng</strong> (mua vào - bán ra), tăng 2.2 triệu đồng (+1.4%) so với phiên trước, đạt mức cao nhất trong 3 tháng qua theo dữ liệu từ DOJI.
                    Chênh lệch giá mua-bán thu hẹp xuống còn 0 đồng, phản ánh thanh khoản tốt và nhu cầu mua vào mạnh mẽ từ nhà đầu tư cá nhân và tổ chức.
                    Khối lượng giao dịch vàng miếng SJC tăng 35% so với tuần trước, cho thấy dòng tiền đang đổ mạnh vào kênh đầu tư vàng vật chất khi thị trường chứng khoán biến động.
                </p>

                <h3>Dự báo tuần tới (13-19/01/2026)</h3>
                <p>
                    Giá vàng trong nước dự kiến <strong>tiếp tục xu hướng tăng</strong> trong tuần tới với biên độ 1-3 triệu đồng/lượng, chạm mốc 162-163 triệu đồng, do áp lực từ giá vàng thế giới tăng mạnh và tâm lý trú ẩn an toàn tăng cao.
                    Yếu tố chính hỗ trợ đà tăng là cuộc họp Fed ngày 29/01 sắp tới, thị trường kỳ vọng Fed sẽ giữ nguyên lãi suất ở mức 5.25-5.50%, tạo áp lực giảm lên đồng USD và đẩy giá vàng lên cao.
                    Rủi ro điều chỉnh giảm có thể xảy ra nếu số liệu CPI tháng 1 của Mỹ (công bố 15/01) thấp hơn dự báo, làm giảm kỳ vọng lạm phát và giảm sức hấp dẫn của vàng như công cụ phòng ngừa rủi ro.
                </p>

                <p class="article-disclaimer">
                    <em>Lưu ý: Đây là phân tích dựa trên dữ liệu lịch sử và xu hướng thị trường. Nhà đầu tư nên tham khảo ý kiến chuyên gia trước khi đưa ra quyết định đầu tư.</em>
                </p>
            """,
            "generated_at": datetime.now().isoformat(),
            "source": "AI Analysis"
        }

        return {
            "success": True,
            "data": analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch gold analysis: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
