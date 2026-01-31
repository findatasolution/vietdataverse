import os
from pathlib import Path
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, declarative_base
import time
import logging

# Load environment configuration
try:
    from back.config import get_config, current_env
    config = get_config()
except ImportError:
    # Fallback to manual .env loading if config.py doesn't exist
    from dotenv import load_dotenv
    # Load .env file from project root
    project_root = Path(__file__).resolve().parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        # Try loading from current working directory
        load_dotenv()
    config = None

Base = declarative_base()

# Schema handling - SIMPLIFIED
SCHEMA = (os.getenv("DB_SCHEMA") or "public").strip() or None

raw_url = (os.getenv("CRAWLING_BOT_DB") or "").strip().strip('"').strip("'")
print(f"DEBUG: CRAWLING_BOT_DB environment variable: {os.getenv('CRAWLING_BOT_DB')}")
print(f"DEBUG: raw_url after processing: {raw_url}")
if raw_url.startswith("//"):
    raw_url = "postgresql+psycopg:" + raw_url
if not raw_url:
    raise RuntimeError("CRAWLING_BOT_DB is empty or invalid")

if SCHEMA and SCHEMA.lower() != "public":
    _resolved_search_path = f"{SCHEMA},public"
else:
    _resolved_search_path = "public"

engine = create_engine(
    raw_url,
    pool_size=int(os.getenv("SQLALCHEMY_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("SQLALCHEMY_MAX_OVERFLOW", "10")),
    pool_timeout=int(os.getenv("SQLALCHEMY_POOL_TIMEOUT", "10")),
    pool_recycle=int(os.getenv("SQLALCHEMY_POOL_RECYCLE", "300")),
    pool_pre_ping=True,
    connect_args={
        # Keep connection alive at TCP level (psycopg2)
        "keepalives": 1,
        "keepalives_idle": int(os.getenv("PG_KEEPALIVES_IDLE", "30")),
        "keepalives_interval": int(os.getenv("PG_KEEPALIVES_INTERVAL", "10")),
        "keepalives_count": int(os.getenv("PG_KEEPALIVES_COUNT", "5")),
        "connect_timeout": int(os.getenv("PG_CONNECT_TIMEOUT", "10")),
    },
    echo=(os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"),
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

logger = logging.getLogger("datanlanh")
logger.info(f"Using PostgreSQL search_path: {_resolved_search_path}")

# search_path
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_connection, connection_record):
    try:
        cur = dbapi_connection.cursor()
        cur.execute(f"SET search_path TO {_resolved_search_path}")
        cur.close()
    except Exception as e:
        logger.warning(f"Could not set search_path: {e}")

# Ensure schema exists if not using public
try:
    if SCHEMA and SCHEMA.lower() != "public":
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
except Exception as _e:
    logger.warning(f"Could not ensure schema '{SCHEMA}': {_e}")

# Query logging (optional, keep if you want performance monitoring)
@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())
    logger.debug(f"Query Start: {statement[:100]}...")

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    if total > 1.0:
        logger.warning(f"SLOW QUERY ({total:.3f}s): {statement[:200]}")