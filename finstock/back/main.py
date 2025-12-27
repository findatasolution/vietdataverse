"""
FastAPI Backend for FinStock Prediction System
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from back.database import get_db, init_db, SessionLocal
from back.prediction_service import PredictionService

app = FastAPI(
    title="FinStock Prediction API",
    description="API for stock market predictions using ML",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update với domain thực tế
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize prediction service
prediction_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize database và prediction service khi khởi động"""
    global prediction_service
    print("Initializing database...")
    init_db()
    print("Loading prediction model...")
    try:
        prediction_service = PredictionService()
        print("Prediction service loaded successfully!")
    except Exception as e:
        print(f"Warning: Could not load prediction service: {e}")


# =========================
# Pydantic Models
# =========================
class PredictionResponse(BaseModel):
    ticker: str
    report_date: date
    year: int
    quarter: int
    prediction_proba: float
    label_actual: Optional[int] = None
    model_version: Optional[str] = None

class TopPredictionsRequest(BaseModel):
    year: int
    quarter: int
    top_n: int = 10

class WeeklyFeatureRequest(BaseModel):
    ticker: str
    report_date: date

class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    database_connected: bool
    total_predictions: int


# =========================
# API Routes
# =========================
@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "FinStock Prediction API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint"""
    # Check database
    db_connected = False
    total_predictions = 0

    try:
        with SessionLocal() as db:
            result = db.execute(text("SELECT COUNT(*) FROM weekly_predictions"))
            total_predictions = result.scalar()
            db_connected = True
    except Exception as e:
        print(f"Database error: {e}")

    return {
        "status": "ok",
        "model_loaded": prediction_service is not None,
        "database_connected": db_connected,
        "total_predictions": total_predictions
    }

@app.get("/predictions/top", response_model=List[PredictionResponse])
def get_top_predictions(year: int, quarter: int, top_n: int = 10):
    """
    Lấy top N predictions cho một quý

    Args:
        year: Năm
        quarter: Quý (1-4)
        top_n: Số lượng predictions (default: 10)

    Returns:
        List of predictions sorted by probability descending
    """
    if not prediction_service:
        raise HTTPException(status_code=503, detail="Prediction service not available")

    try:
        df = prediction_service.get_top_predictions(year, quarter, top_n)

        if df.empty:
            return []

        predictions = []
        for _, row in df.iterrows():
            # Handle NaN for label_actual
            label_val = row['label_actual']
            if pd.isna(label_val):
                label_val = None
            else:
                label_val = int(label_val)

            predictions.append(PredictionResponse(
                ticker=row['ticker'],
                report_date=row['report_date'],
                year=row['year'],
                quarter=row['quarter'],
                prediction_proba=row['prediction_proba'],
                label_actual=label_val,
                model_version=row.get('model_version')
            ))

        return predictions

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/predictions/ticker/{ticker}")
def get_predictions_by_ticker(ticker: str, limit: int = 10):
    """
    Lấy predictions cho một ticker cụ thể

    Args:
        ticker: Mã cổ phiếu
        limit: Số lượng records (default: 10)

    Returns:
        List of predictions
    """
    with SessionLocal() as db:
        result = db.execute(text("""
            SELECT
                ticker,
                report_date,
                year,
                quarter,
                prediction_proba,
                label_actual,
                model_version,
                created_at
            FROM weekly_predictions
            WHERE ticker = :ticker
            ORDER BY report_date DESC
            LIMIT :limit
        """), {'ticker': ticker.upper(), 'limit': limit})

        rows = result.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No predictions found for ticker {ticker}")

    predictions = []
    for row in rows:
        predictions.append({
            'ticker': row.ticker,
            'report_date': row.report_date.isoformat(),
            'year': row.year,
            'quarter': row.quarter,
            'prediction_proba': row.prediction_proba,
            'label_actual': row.label_actual,
            'model_version': row.model_version,
            'created_at': row.created_at.isoformat()
        })

    return predictions

@app.get("/predictions/latest")
def get_latest_predictions(limit: int = 20):
    """
    Lấy predictions mới nhất

    Args:
        limit: Số lượng records (default: 20)

    Returns:
        List of latest predictions
    """
    with SessionLocal() as db:
        result = db.execute(text("""
            SELECT
                ticker,
                report_date,
                year,
                quarter,
                prediction_proba,
                label_actual,
                model_version,
                created_at
            FROM weekly_predictions
            ORDER BY created_at DESC
            LIMIT :limit
        """), {'limit': limit})

        rows = result.fetchall()

    predictions = []
    for row in rows:
        predictions.append({
            'ticker': row.ticker,
            'report_date': row.report_date.isoformat(),
            'year': row.year,
            'quarter': row.quarter,
            'prediction_proba': row.prediction_proba,
            'label_actual': row.label_actual,
            'model_version': row.model_version,
            'created_at': row.created_at.isoformat()
        })

    return predictions

@app.get("/predictions/stats")
def get_prediction_stats(year: int, quarter: int):
    """
    Thống kê predictions cho một quý

    Args:
        year: Năm
        quarter: Quý

    Returns:
        Statistics
    """
    with SessionLocal() as db:
        result = db.execute(text("""
            SELECT
                COUNT(*) as total_predictions,
                AVG(prediction_proba) as avg_proba,
                MAX(prediction_proba) as max_proba,
                MIN(prediction_proba) as min_proba,
                COUNT(CASE WHEN label_actual = 1 THEN 1 END) as actual_gains,
                COUNT(CASE WHEN label_actual = 0 THEN 1 END) as actual_no_gains
            FROM weekly_predictions
            WHERE year = :year AND quarter = :quarter
        """), {'year': year, 'quarter': quarter})

        row = result.fetchone()

    if not row or row.total_predictions == 0:
        raise HTTPException(status_code=404, detail=f"No data for Q{quarter}/{year}")

    return {
        'year': year,
        'quarter': quarter,
        'total_predictions': row.total_predictions,
        'avg_probability': row.avg_proba,
        'max_probability': row.max_proba,
        'min_probability': row.min_proba,
        'actual_gains': row.actual_gains,
        'actual_no_gains': row.actual_no_gains,
        'gain_rate': row.actual_gains / row.total_predictions if row.total_predictions > 0 else 0
    }

@app.post("/predictions/run")
def run_prediction(year: int, quarter: int):
    """
    Chạy prediction cho một quý cụ thể

    Args:
        year: Năm
        quarter: Quý

    Returns:
        Prediction results
    """
    if not prediction_service:
        raise HTTPException(status_code=503, detail="Prediction service not available")

    try:
        # Predict
        predictions_df = prediction_service.predict_from_db(year, quarter)

        if predictions_df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No features found for Q{quarter}/{year}"
            )

        # Save to database
        prediction_service.save_predictions_to_db(predictions_df, model_version="xgb_v1.0")

        return {
            'message': f'Predictions completed for Q{quarter}/{year}',
            'total_predictions': len(predictions_df),
            'avg_probability': predictions_df['prediction_proba'].mean(),
            'top_10_tickers': predictions_df.nlargest(10, 'prediction_proba')['ticker'].tolist()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
