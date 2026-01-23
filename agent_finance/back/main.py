from fastapi import FastAPI, HTTPException, Depends, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
import os
import json

# Import database models and functions
from neon_database import engine, Base
from neon_models import NeonUser

from neon_auth import hash_password, verify_password, create_access_token, decode_access_token
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

# Mount static directories
app.mount("/agent_finance/front", StaticFiles(directory="../front", html=True), name="agent_finance_front")
app.mount("/vietdataverse", StaticFiles(directory="../../vietdataverse", html=True), name="vietdataverse")

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
        
        existing_user = session.query(NeonUser).filter_by(email=request.email).first()
        if existing_user:
            session.close()
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password
        password_hash = hash_password(request.password)
        
        # Create new user
        new_user = NeonUser(
            email=request.email,
            password_hash=password_hash,
            phone=request.phone
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
        user = session.query(NeonUser).filter_by(email=request.email).first()
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
                "type": user.type,
                "membership_level": user.membership_level
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
                "type": user["type"],
                "membership_level": user["membership_level"]
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
    """Get gold price data - Requires authentication"""
    try:
        # Authenticate user
        await authenticate_user(request)

        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB", 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, buy_price, sell_price
        FROM vn_gold_24h_hist
        WHERE date >= '{date_filter}'
        AND type = '{type.replace("'", "''")}'
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
    """Get silver price data - Requires authentication"""
    try:
        # Authenticate user
        await authenticate_user(request)

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB", 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, buy_price, sell_price
        FROM vn_silver_phuquy_hist
        WHERE date >= '{date_filter}'
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
    """Get SBV interbank rates - Requires authentication"""
    try:
        # Authenticate user
        await authenticate_user(request)

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB", 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, overnight, month_1, month_3, rediscount, refinancing
        FROM vn_sbv_interbankrate
        WHERE date >= '{date_filter}'
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
    """Get term deposit rates - Requires authentication"""
    try:
        # Authenticate user
        await authenticate_user(request)

        from sqlalchemy import text

        # Get crawling bot database connection
        CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB", 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

        engine_crawl = create_engine(CRAWLING_BOT_DB)

        # Build query
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, term_1m, term_3m, term_6m, term_12m, term_24m
        FROM vn_term_deposit
        WHERE date >= '{date_filter}'
        AND bank_code = '{bank.replace("'", "''")}'
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
    """Get global macro indicators - Requires authentication"""
    try:
        # Authenticate user
        await authenticate_user(request)

        from sqlalchemy import text

        # Get global indicator database connection
        GLOBAL_INDICATOR_DB = os.getenv("GLOBAL_INDICATOR_DB", 'postgresql://neondb_owner:npg_DTMVHjWIy21J@ep-frosty-forest-a19clsva-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require')

        engine_global = create_engine(GLOBAL_INDICATOR_DB)

        # Build query
        date_filter = get_date_filter(period)
        query = f"""
        SELECT date, gold_price, silver_price, nasdaq_close
        FROM global_macro_indicators
        WHERE date >= '{date_filter}'
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
