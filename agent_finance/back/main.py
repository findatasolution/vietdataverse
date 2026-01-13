import os
import time
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
import shutil
import uuid

from back.database import get_db
from back.models import User
from back.auth import hash_password, verify_password, create_access_token, decode_access_token
from back.dataverse import router as dataverse_router

try:
    import google.generativeai as genai
except ImportError as e:
    genai = None
    logging.warning(f"Missing google-generativeai: {e}")

try:
    import pandas as pd
except ImportError as e:
    pd = None
    logging.warning(f"Missing pandas: {e}")

try:
    from back.file_processor import (
        validate_file,
        process_uploaded_file,
        format_file_summary_for_llm,
        get_file_data_for_analysis
    )
    FILE_UPLOAD_AVAILABLE = True
except ImportError as e:
    FILE_UPLOAD_AVAILABLE = False
    logging.warning(f"File upload features not available: {e}")

load_dotenv()

# =========================
# Logging
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("finagent")

# =========================
# Configure Gemini AI
# =========================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if genai and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("Gemini AI configured")
    except Exception as e:
        logger.error(f"Failed to configure Gemini: {e}")

# =========================
# Load Financial Data
# =========================
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Store uploaded file metadata in memory (in production, use database)
uploaded_files_store = {}

def get_db_engine():
    """Get SQLAlchemy engine for database queries"""
    from sqlalchemy import create_engine
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        return None
    return create_engine(DATABASE_URL)

def query_historical_data(query: str):
    """Query historical financial data from database"""
    if pd is None:
        return None
    try:
        engine = get_db_engine()
        if not engine:
            logger.warning("DATABASE_URL not configured")
            return None
        df = pd.read_sql(query, engine)
        return df
    except Exception as e:
        logger.error(f"Database query error: {e}")
        return None

# Database connection check
try:
    engine = get_db_engine()
    if engine:
        logger.info("Database connection configured")
    else:
        logger.warning("No database configured - using file uploads only")
except Exception as e:
    logger.error(f"Database connection error: {e}")

# Import financial knowledge base
try:
    from back.financial_knowledge import (
        FINANCIAL_GLOSSARY,
        FINANCIAL_FORMULAS,
        AI_SYSTEM_PROMPTS,
        get_financial_context,
        calculate_financial_metrics
    )
    logger.info("Financial knowledge base loaded")
except ImportError as e:
    logger.warning(f"Financial knowledge base not available: {e}")
    FINANCIAL_GLOSSARY = {}
    FINANCIAL_FORMULAS = {}
    AI_SYSTEM_PROMPTS = {}
    get_financial_context = lambda: ""
    calculate_financial_metrics = lambda x: {}

# =========================
# FastAPI App
# =========================
app = FastAPI(title="Hien's Fin Agent")

# CORS
CORS_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5500,http://127.0.0.1:5500").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(dataverse_router)

# Frontend will be mounted after API routes are defined

# =========================
# Pydantic Models
# =========================
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserInfo(BaseModel):
    email: str
    role: str
    user_id: int
    is_admin: bool

class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None
    file_ids: Optional[list[str]] = None  # List of uploaded file IDs to include in context

class ChatResponse(BaseModel):
    response: str
    model: str
    timestamp: str
    data_summary: Optional[str] = None

# =========================
# Auth Dependency
# =========================
def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    email = payload.get("sub")

    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# =========================
# Helper: Check Role Access
# =========================
def check_role_access(user: User, required_role: str):
    """
    Role hierarchy: user < accountant < cfo < admin
    """
    roles_hierarchy = ["user", "accountant", "cfo", "admin"]

    user_role_idx = roles_hierarchy.index(user.role) if user.role in roles_hierarchy else 0
    required_role_idx = roles_hierarchy.index(required_role) if required_role in roles_hierarchy else 0

    if user_role_idx < required_role_idx:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied. Required role: {required_role}, your role: {user.role}"
        )

# =========================
# Routes
# =========================
@app.post("/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    """User registration"""
    email_norm = user.email.lower().strip()

    # Check if exists
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    new_user = User(
        email=email_norm,
        password_hash=hash_password(user.password),
        role="user",
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"User registered: {email_norm}")
    return {"message": "User created successfully", "user_id": new_user.id}

@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    """User login"""
    email_norm = user.email.lower().strip()

    db_user = db.query(User).filter(User.email == email_norm).first()
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create token
    token = create_access_token({"sub": db_user.email})

    logger.info(f"User logged in: {email_norm} (role={db_user.role})")
    return {
        "message": "Login successful",
        "email": db_user.email,
        "role": db_user.role,
        "is_admin": db_user.is_admin,
        "access_token": token
    }

@app.get("/me", response_model=UserInfo)
def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserInfo(
        email=current_user.email,
        role=current_user.role,
        user_id=current_user.id,
        is_admin=current_user.is_admin
    )

@app.post("/ai/chat", response_model=ChatResponse)
def ai_chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    AI Chat with Financial Data Access
    - All authenticated users can chat
    - LLM can read financial data based on user role
    """
    if not genai or not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="AI service not configured")

    # OPTIMIZED: Minimal system prompt to save tokens
    user_bu = None
    try:
        from back.role_access import get_user_bu
        user_bu = get_user_bu(current_user.email)
    except:
        pass

    system_prompt = f"""You are a Financial Analyst AI for {current_user.role.upper()}{f' ({user_bu})' if user_bu else ''}.

Answer in SAME LANGUAGE as question. Use terms: Revenue, COGS, OpEx, EBITDA, Gross Margin.

MANDATORY FORMAT - Include ALL sections below:

**📊 Answer:**
[Direct answer with key numbers]

**💡 Details:**
• Key point 1 with number
• Key point 2 with number
• Key point 3 (if relevant)

**📁 Source:** [financial_pl / uploaded file name]

Example response:
User: "What is our OpEx?"
AI:
**📊 Answer:**
Total OpEx is $16.3M, representing 45.8% of revenue.

**💡 Details:**
• APAC region contributes largest share
• Q1-Q3 data from financial_pl table
• 3-month trend shows 5% increase

**📁 Source:** financial_pl table (APAC business unit)

"""

    # Get historical data from DATABASE (role-based)
    try:
        from back.data_service import get_all_historical_context
        historical_data = get_all_historical_context(current_user.role, current_user.email)
        system_prompt += historical_data
    except Exception as e:
        logger.error(f"Failed to load historical data: {e}")

    # Add uploaded files context
    uploaded_files_context = ""
    if request.file_ids and FILE_UPLOAD_AVAILABLE:
        for file_id in request.file_ids:
            if file_id in uploaded_files_store:
                metadata = uploaded_files_store[file_id]
                # Check file ownership
                if metadata["user_email"] == current_user.email:
                    file_summary = metadata["file_summary"]
                    file_context = format_file_summary_for_llm(file_summary, metadata["original_filename"])
                    uploaded_files_context += f"\n\n{file_context}"

    if uploaded_files_context:
        system_prompt += f"""

        UPLOADED FILES:
        {uploaded_files_context}

        The user has uploaded these files for you to analyze. Use this data to answer their questions.
        """

    # Old CSV loading removed - now using database queries via data_service.py
    # All historical data is fetched from database in lines 300-306 above

    # Build full prompt
    full_prompt = system_prompt + "\\n\\n"
    if request.context:
        full_prompt += f"Previous context: {request.context}\\n\\n"
    full_prompt += f"User question: {request.message}"

    # Call Gemini API
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            full_prompt,
            request_options={"timeout": 30}
        )

        if not response or not response.text:
            raise RuntimeError("Empty AI response")

        logger.info(f"AI chat: user={current_user.email}, role={current_user.role}")

        return ChatResponse(
            response=response.text.strip(),
            model="gemini-2.5-flash",
            timestamp=datetime.now().isoformat(),
            data_summary=data_summary if current_user.role in ["cfo", "admin", "accountant"] else None
        )

    except Exception as e:
        logger.error(f"AI chat error: {e}")
        raise HTTPException(status_code=500, detail=f"AI error: {str(e)}")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload file endpoint - supports CSV, Excel, PDF"""

    if not FILE_UPLOAD_AVAILABLE:
        raise HTTPException(status_code=503, detail="File upload feature not available")

    try:
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file
        is_valid, message = validate_file(file.filename, file_size)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)

        # Generate unique filename
        file_ext = Path(file.filename).suffix
        unique_filename = f"{current_user.email}_{uuid.uuid4().hex}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Process file
        file_summary = process_uploaded_file(str(file_path), file.filename)

        if "error" in file_summary:
            # Delete file if processing failed
            file_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=file_summary["error"])

        # Store metadata
        file_id = str(uuid.uuid4())
        uploaded_files_store[file_id] = {
            "file_id": file_id,
            "user_email": current_user.email,
            "original_filename": file.filename,
            "stored_filename": unique_filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_summary": file_summary
        }

        logger.info(f"File uploaded: {file.filename} by {current_user.email} (ID: {file_id})")

        return {
            "success": True,
            "file_id": file_id,
            "filename": file.filename,
            "file_type": file_summary.get("file_type"),
            "summary": {
                "rows": file_summary.get("rows"),
                "columns": file_summary.get("columns"),
                "sheets": file_summary.get("sheet_names"),
                "pages": file_summary.get("pages")
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/files")
def list_user_files(current_user: User = Depends(get_current_user)):
    """List uploaded files for current user"""

    user_files = [
        {
            "file_id": metadata["file_id"],
            "filename": metadata["original_filename"],
            "file_type": metadata["file_summary"].get("file_type"),
            "uploaded_at": metadata["uploaded_at"],
            "file_size": metadata["file_size"]
        }
        for file_id, metadata in uploaded_files_store.items()
        if metadata["user_email"] == current_user.email
    ]

    return {"files": user_files}


@app.delete("/files/{file_id}")
def delete_file(file_id: str, current_user: User = Depends(get_current_user)):
    """Delete uploaded file and its JSON"""

    if file_id not in uploaded_files_store:
        raise HTTPException(status_code=404, detail="File not found")

    metadata = uploaded_files_store[file_id]

    # Check ownership
    if metadata["user_email"] != current_user.email:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")

    # Delete physical file
    file_path = Path(metadata["file_path"])
    file_path.unlink(missing_ok=True)

    # Delete JSON file(s) if exists
    file_summary = metadata.get("file_summary", {})
    if file_summary.get("file_type") == "CSV":
        json_path = file_summary.get("json_file_path")
        if json_path:
            Path(json_path).unlink(missing_ok=True)
    elif file_summary.get("file_type") == "Excel":
        for sheet_data in file_summary.get("sheets", {}).values():
            json_path = sheet_data.get("json_file_path")
            if json_path:
                Path(json_path).unlink(missing_ok=True)

    # Remove from store
    del uploaded_files_store[file_id]

    logger.info(f"File deleted: {metadata['original_filename']} by {current_user.email}")

    return {"success": True, "message": "File deleted"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    # Check database connectivity
    db_connected = False
    db_row_count = 0
    try:
        engine = get_db_engine()
        if engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM financial_pl"))
                db_row_count = result.fetchone()[0]
                db_connected = True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")

    return {
        "status": "ok",
        "ai_configured": bool(genai and GEMINI_API_KEY),
        "database_connected": db_connected,
        "historical_data_rows": db_row_count,
        "file_upload_enabled": FILE_UPLOAD_AVAILABLE
    }

# =========================
# Startup
# =========================
@app.on_event("startup")
def startup():
    logger.info("Hien's Fin Agent started")
    logger.info(f"AI configured: {bool(genai and GEMINI_API_KEY)}")

    # Check database connection
    try:
        engine = get_db_engine()
        if engine:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM financial_pl"))
                row_count = result.fetchone()[0]
                logger.info(f"Database connected: {row_count} historical records available")
        else:
            logger.warning("Database not configured")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")

# =========================
# Historical Data API Endpoints for Charts
# =========================
from datetime import timedelta

def get_date_filter(period: str):
    """Calculate start date based on period filter"""
    today = datetime.now()
    if period == '7d':
        return today - timedelta(days=7)
    elif period == '1m':
        return today - timedelta(days=30)
    elif period == '1y':
        return today - timedelta(days=365)
    else:  # 'all'
        return datetime(2000, 1, 1)

@app.get("/api/v1/gold")
def get_gold_data(period: str = '1m'):
    """Get gold price historical data"""
    if pd is None:
        raise HTTPException(status_code=503, detail="Pandas not available")

    try:
        engine = get_db_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Database not configured")

        start_date = get_date_filter(period)

        query = text("""
            SELECT date, buy_price, sell_price
            FROM vn_gold_24h_dojihn_hist
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        # Check if DataFrame is empty
        if df.empty:
            return {
                'success': True,
                'data': {
                    'dates': [],
                    'buy_prices': [],
                    'sell_prices': [],
                    'count': 0
                },
                'period': period
            }

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Convert to JSON-friendly format
        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'buy_prices': df['buy_price'].tolist(),
            'sell_prices': df['sell_price'].tolist(),
            'count': len(df)
        }

        return {
            'success': True,
            'data': data,
            'period': period
        }

    except Exception as e:
        logger.error(f"Gold data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/silver")
def get_silver_data(period: str = '1m'):
    """Get silver price historical data"""
    if pd is None:
        raise HTTPException(status_code=503, detail="Pandas not available")

    try:
        engine = get_db_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Database not configured")

        start_date = get_date_filter(period)

        query = text("""
            SELECT date, buy_price, sell_price
            FROM vn_silver_phuquy_hist
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        # Check if DataFrame is empty
        if df.empty:
            return {
                'success': True,
                'data': {
                    'dates': [],
                    'buy_prices': [],
                    'sell_prices': [],
                    'count': 0
                },
                'period': period
            }

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'buy_prices': df['buy_price'].tolist(),
            'sell_prices': df['sell_price'].tolist(),
            'count': len(df)
        }

        return {
            'success': True,
            'data': data,
            'period': period
        }

    except Exception as e:
        logger.error(f"Silver data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/sbv-interbank")
def get_sbv_data(period: str = '1m'):
    """Get SBV interbank rate historical data"""
    if pd is None:
        raise HTTPException(status_code=503, detail="Pandas not available")

    try:
        engine = get_db_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Database not configured")

        start_date = get_date_filter(period)

        query = text("""
            SELECT date, ls_quadem, ls_1w, ls_2w, ls_1m, ls_3m, ls_6m, ls_9m
            FROM vn_sbv_interbankrate
            WHERE date >= :start_date
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date})

        # Check if DataFrame is empty
        if df.empty:
            return {
                'success': True,
                'data': {
                    'dates': [],
                    'overnight': [],
                    'week_1': [],
                    'week_2': [],
                    'month_1': [],
                    'month_3': [],
                    'month_6': [],
                    'month_9': [],
                    'count': 0
                },
                'period': period
            }

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'overnight': df['ls_quadem'].tolist(),
            'week_1': df['ls_1w'].tolist(),
            'week_2': df['ls_2w'].tolist(),
            'month_1': df['ls_1m'].tolist(),
            'month_3': df['ls_3m'].tolist(),
            'month_6': df['ls_6m'].tolist(),
            'month_9': df['ls_9m'].tolist(),
            'count': len(df)
        }

        return {
            'success': True,
            'data': data,
            'period': period
        }

    except Exception as e:
        logger.error(f"SBV data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/bank-termdepo")
def get_termdepo_data(period: str = '1m', bank: str = 'ACB'):
    """Get bank term deposit rates historical data"""
    if pd is None:
        raise HTTPException(status_code=503, detail="Pandas not available")

    try:
        engine = get_db_engine()
        if not engine:
            raise HTTPException(status_code=503, detail="Database not configured")

        start_date = get_date_filter(period)

        query = text("""
            SELECT date, term_1m, term_2m, term_3m, term_6m, term_9m,
                   term_12m, term_13m, term_18m, term_24m, term_36m
            FROM vn_bank_termdepo
            WHERE date >= :start_date AND bank_code = :bank_code
            ORDER BY date ASC
        """)

        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'start_date': start_date, 'bank_code': bank})

        # Check if DataFrame is empty
        if df.empty:
            return {
                'success': True,
                'data': {
                    'dates': [],
                    'term_1m': [],
                    'term_3m': [],
                    'term_6m': [],
                    'term_12m': [],
                    'count': 0
                },
                'period': period,
                'bank': bank
            }

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'term_1m': df['term_1m'].tolist(),
            'term_3m': df['term_3m'].tolist(),
            'term_6m': df['term_6m'].tolist(),
            'term_12m': df['term_12m'].tolist(),
            'count': len(df)
        }

        return {
            'success': True,
            'data': data,
            'period': period,
            'bank': bank
        }

    except Exception as e:
        logger.error(f"Term deposit data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# Serve Frontend (mounted last to not interfere with API routes)
# =========================
try:
    app.mount("/", StaticFiles(directory="front", html=True), name="front")
except Exception as e:
    logger.warning(f"Could not mount frontend: {e}")
