import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_u2JfE3mIDMLU@ep-muddy-bread-adyayss2-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=10,
    pool_recycle=300,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for FastAPI routes"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database tables"""
    with engine.begin() as conn:
        # Create tables for weekly features
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weekly_features (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                report_date DATE NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                features JSONB NOT NULL,
                label_willgain_ov5pct INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(ticker, report_date)
            );

            CREATE INDEX IF NOT EXISTS idx_weekly_features_ticker ON weekly_features(ticker);
            CREATE INDEX IF NOT EXISTS idx_weekly_features_date ON weekly_features(report_date);
            CREATE INDEX IF NOT EXISTS idx_weekly_features_year_quarter ON weekly_features(year, quarter);
        """))

        # Create table for predictions
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weekly_predictions (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL,
                report_date DATE NOT NULL,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                prediction_proba FLOAT NOT NULL,
                label_actual INTEGER,
                model_version VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(ticker, report_date)
            );

            CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON weekly_predictions(ticker);
            CREATE INDEX IF NOT EXISTS idx_predictions_date ON weekly_predictions(report_date);
            CREATE INDEX IF NOT EXISTS idx_predictions_proba ON weekly_predictions(prediction_proba DESC);
        """))

        # Create table for model metadata
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_metadata (
                id SERIAL PRIMARY KEY,
                model_version VARCHAR(50) UNIQUE NOT NULL,
                model_path VARCHAR(255) NOT NULL,
                auc_score FLOAT,
                train_date DATE NOT NULL,
                features_used TEXT[],
                hyperparameters JSONB,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """))

    print("Database tables initialized successfully!")

if __name__ == "__main__":
    init_db()
