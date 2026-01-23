import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
import logging

# Load environment variables
from dotenv import load_dotenv
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

# Neon database configuration
NEON_DB_URL = os.getenv("NEON_DB_URL", "postgresql://neondb_owner:npg_TCmnA52VNvHt@ep-withered-mouse-a14fjjxh-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

# Create base for models
Base = declarative_base()

# Create engine with connection pooling
engine = create_engine(
    NEON_DB_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False  # Set to True for debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_neon_db():
    """Get Neon database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_neon_db_engine():
    """Get Neon database engine for direct queries"""
    return engine

def test_neon_connection():
    """Test connection to Neon database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
            logging.info("Neon database connection successful")
            return True
    except Exception as e:
        logging.error(f"Neon database connection failed: {e}")
        return False

# Test connection on import
if __name__ == "__main__":
    test_neon_connection()
