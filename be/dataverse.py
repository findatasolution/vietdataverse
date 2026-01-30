"""
Viet Dataverse API Router
Provides CSV download endpoints for research datasets
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
import pandas as pd
import io
from datetime import datetime
import logging
import os

# Initialize router
router = APIRouter(prefix="/api/dataverse", tags=["dataverse"])

# Get database connection from environment
CRAWLING_BOT_DB = os.getenv("CRAWLING_BOT_DB")
if not CRAWLING_BOT_DB:
    logging.warning("CRAWLING_BOT_DB not found, using default connection")
    CRAWLING_BOT_DB = 'postgresql://neondb_owner:npg_HYEChe05ayJQ@ep-square-boat-a1v539wy-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

# Use NullPool to avoid connection state issues
engine = create_engine(CRAWLING_BOT_DB, poolclass=NullPool)

# Dataset configuration
DATASET_CONFIG = {
    'VNGold': {
        'table': 'vn_gold_24h_hist',
        'query': "SELECT * FROM vn_gold_24h_hist WHERE type IN ('DOJI HN', 'BTTMC SJC') ORDER BY date DESC",
        'filename': 'vn_gold_prices.csv',
        'description': 'Vietnamese Gold Prices (DOJI HN 24k)'
    },
    'VNSilver': {
        'table': 'vn_silver_phuquy_hist',
        'query': 'SELECT * FROM vn_silver_phuquy_hist ORDER BY date DESC',
        'filename': 'vn_silver_prices.csv',
        'description': 'Vietnamese Silver Prices (Phu Quy)'
    },
    'SBVInterbank': {
        'table': 'vn_sbv_interbankrate',
        'query': 'SELECT * FROM vn_sbv_interbankrate ORDER BY date DESC',
        'filename': 'vn_sbv_interbank_rates.csv',
        'description': 'State Bank of Vietnam Interbank Rates'
    },
    'VNTermDeposit': {
        'table': 'vn_term_deposit',
        'query': 'SELECT bank_code, date, term_1m, term_6m, term_12m, term_24m, term_noterm FROM vn_term_deposit GROUP BY  bank_code, date ORDER BY date DESC',
        'filename': 'vn_term_deposit_rates.csv',
        'description': 'Vietnamese Term Deposit Rates'
    },
    'VN30FSBS': {
        'table': 'vn30_fsbs',
        'query': 'SELECT * FROM vn30_fsbs ORDER BY date DESC',
        'filename': 'vn30_financial_statements.csv',
        'description': 'VN30 Financial Statements'
    },
    'NewsSentiment': {
        'table': 'news_sentiment',
        'query': 'SELECT * FROM news_sentiment ORDER BY date DESC',
        'filename': 'news_sentiment.csv',
        'description': 'News Sentiment Analysis Data'
    }
}


@router.get("/datasets")
async def list_datasets():
    """
    List all available datasets with metadata

    Returns:
        JSON with list of datasets including record counts and availability
    """
    datasets = []

    for key, config in DATASET_CONFIG.items():
        try:
            # Get row count for each dataset
            with engine.connect() as conn:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {config['table']}"))
                count = result.scalar()

            datasets.append({
                'id': key,
                'name': key,
                'description': config['description'],
                'filename': config['filename'],
                'record_count': count,
                'available': True
            })
        except Exception as e:
            # If table doesn't exist, mark as unavailable
            logging.warning(f"Dataset {key} not available: {e}")
            datasets.append({
                'id': key,
                'name': key,
                'description': config['description'],
                'filename': config['filename'],
                'record_count': 0,
                'available': False,
                'error': str(e)
            })

    return {'datasets': datasets}


@router.get("/download/{dataset_name}")
async def download_csv(dataset_name: str):
    """
    Download dataset as CSV file

    Args:
        dataset_name: Name of the dataset (e.g., 'VNGold', 'VNSilver')

    Returns:
        CSV file download
    """

    if dataset_name not in DATASET_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_name}' not found. Available datasets: {', '.join(DATASET_CONFIG.keys())}"
        )

    config = DATASET_CONFIG[dataset_name]

    try:
        # Query database
        df = pd.read_sql(config['query'], engine)

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for dataset '{dataset_name}'"
            )

        # Convert DataFrame to CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{config['filename'].replace('.csv', '')}_{timestamp}.csv"

        # Return as streaming response
        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error downloading {dataset_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to download dataset: {str(e)}"
        )


@router.get("/preview/{dataset_name}")
async def preview_data(dataset_name: str, limit: int = 10):
    """
    Preview first N rows of a dataset

    Args:
        dataset_name: Name of the dataset
        limit: Number of rows to preview (default: 10, max: 100)

    Returns:
        JSON with preview data and metadata
    """

    if dataset_name not in DATASET_CONFIG:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_name}' not found"
        )

    # Limit the preview to reasonable size
    limit = min(limit, 100)

    config = DATASET_CONFIG[dataset_name]

    try:
        # Query database with limit
        query = config['query'] + f' LIMIT {limit}'
        df = pd.read_sql(query, engine)

        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for dataset '{dataset_name}'"
            )

        # Get total count
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {config['table']}"))
            total_count = result.scalar()

        # Convert DataFrame to JSON-serializable format
        # Handle datetime objects by converting to string
        data = df.to_dict(orient='records')
        for record in data:
            for key, value in record.items():
                if pd.isna(value):
                    record[key] = None
                elif isinstance(value, (pd.Timestamp, datetime)):
                    record[key] = value.strftime('%Y-%m-%d')

        return {
            'dataset': dataset_name,
            'description': config['description'],
            'total_records': total_count,
            'preview_records': len(data),
            'data': data,
            'columns': list(df.columns)
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error previewing {dataset_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview dataset: {str(e)}"
        )
