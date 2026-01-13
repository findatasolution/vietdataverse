# Global Macro Data Integration

## Overview
This module integrates global financial market data from Yahoo Finance into the `global_macro` table in Neon PostgreSQL database.

## Data Points
- **Gold Price**: Gold Futures (GC=F) in $/oz
- **Silver Price**: Silver Futures (SI=F) in $/oz
- **NASDAQ**: NASDAQ Composite Index (^IXIC)

## Database Schema
```sql
CREATE TABLE global_macro (
    date DATE PRIMARY KEY,
    crawl_time TIMESTAMP NOT NULL,
    gold_price NUMERIC(10, 2),
    silver_price NUMERIC(10, 2),
    nasdaq_price NUMERIC(10, 2)
)
```

## Files

### 1. init_global_macro_table.py
**Purpose**: Initialize the global_macro table
**Usage**: Run once before first use
```bash
cd crawl_tools
python init_global_macro_table.py
```

### 2. backfill_global_macro.py
**Purpose**: Backfill 1 year of historical data
**Usage**: Run once to populate historical data (252 trading days)
```bash
cd crawl_tools
python backfill_global_macro.py
```
**Output**:
- Fetches 1 year of historical data for all 3 tickers
- Inserts ~252 records (1 year of trading days)
- Includes retry logic with exponential backoff
- Skips existing records to avoid duplicates

### 3. crawl_bot.py
**Purpose**: Daily automated crawler (lines 287-403)
**Integration**:
- Fetches today's data from Yahoo Finance
- Uses exponential backoff retry (3 attempts, 2s initial delay)
- 1-second delays between ticker requests to avoid rate limiting
- Automatically runs via GitHub Actions daily

**Logic Flow**:
1. Fetch Gold Futures (GC=F) with retry
2. Wait 1 second
3. Fetch Silver Futures (SI=F) with retry
4. Wait 1 second
5. Fetch NASDAQ (^IXIC) with retry
6. Check if today's data already exists
7. Insert if new, skip if exists

## API Endpoint

### GET /api/v1/global-macro
**Location**: agent_finance/back/main.py (lines 826-882)
**Query Parameters**:
- `period` (optional): '7d' | '1m' | '1y' | 'all' (default: '1m')

**Response Format**:
```json
{
    "success": true,
    "data": {
        "dates": ["2025-01-14", "2025-01-15", ...],
        "gold_prices": [2677.5, 2712.5, ...],
        "silver_prices": [30.12, 30.45, ...],
        "nasdaq_prices": [19044.39, 19511.23, ...],
        "count": 252
    },
    "period": "1m"
}
```

**Example**:
```bash
curl http://localhost:8000/api/v1/global-macro?period=1y
```

## Automated Daily Updates

The daily crawling is automated via GitHub Actions:
1. `.github/workflows/crawl_daily.yml` runs crawl_bot.py every day
2. crawl_bot.py fetches today's data from Yahoo Finance (lines 287-403)
3. Data is inserted into global_macro table if not exists
4. Retry logic handles rate limiting automatically

## Rate Limiting Protection

All scripts include:
- **Exponential backoff**: 2s → 4s → 8s delays on rate limit
- **Inter-request delays**: 1-2 second pauses between tickers
- **Retry logic**: 3 attempts per ticker before failing
- **Polite crawling**: Follows Yahoo Finance rate limits

## Setup Instructions

1. **Initial Setup** (one-time):
```bash
cd crawl_tools
python init_global_macro_table.py
python backfill_global_macro.py
```

2. **Daily Automation** (GitHub Actions):
Already configured - runs automatically via crawl_bot.py

3. **Backend API** (production):
```bash
cd agent_finance
uvicorn back.main:app --host 0.0.0.0 --port 8000
```

## Verification

Check data in database:
```sql
-- Count records
SELECT COUNT(*) FROM global_macro;

-- Latest data
SELECT * FROM global_macro ORDER BY date DESC LIMIT 5;

-- Date range
SELECT MIN(date), MAX(date) FROM global_macro;
```

## Current Status
- Table created: ✅
- Historical data backfilled: ✅ (252 records from 2025-01-14 to 2026-01-13)
- Daily automation: ✅ (integrated in crawl_bot.py)
- API endpoint: ✅ (GET /api/v1/global-macro)
- Rate limiting protection: ✅

## Dependencies
```
yfinance
pandas
sqlalchemy
psycopg2-binary
```

All dependencies already in crawl_tools/requirements.txt