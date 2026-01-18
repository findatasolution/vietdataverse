# Environment Variables Setup Guide

## Required Environment Variables

Để hệ thống hoạt động đúng, bạn cần setup các environment variables sau:

### 1. Local Development (.env file)

Tạo file `.env` trong **root directory** (nguyenphamdieuhien/):

```env
# Gemini AI
GEMINI_API_KEY=your_gemini_api_key_here

# Database Connections
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
GLOBAL_INDICATOR_DB=postgresql://user:pass@host/db?sslmode=require&channel_binding=require
ARGUS_FINTEL_DB=postgresql://user:pass@host/db?sslmode=require&channel_binding=require

# CORS (optional for local dev)
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:5500
```

### 2. GitHub Actions Secrets

Vào **Settings → Secrets and variables → Actions** và thêm các secrets sau:

- `DATABASE_URL` - Old DB connection string (cho domestic data)
- `GLOBAL_INDICATOR_DB` - Global indicator DB connection string
- `ARGUS_FINTEL_DB` - Argus Fintel DB connection string
- `GEMINI_API_KEY` - Gemini API key

### 3. Render.com Environment Variables

Trong Render dashboard, thêm các environment variables sau:

- `DATABASE_URL` - Old DB (sync: false)
- `GLOBAL_INDICATOR_DB` - Global indicator DB (sync: false)
- `ARGUS_FINTEL_DB` - Argus Fintel DB (sync: false)
- `GEMINI_API_KEY` - API key (sync: false)
- `SECRET_KEY` - Auth secret (sync: false)
- `ALGORITHM` - HS256
- `ACCESS_TOKEN_EXPIRE_MINUTES` - 30
- `CORS_ALLOW_ORIGINS` - Production domains

## Database Architecture

```
DATABASE_URL (old macro_crawling DB):
- vn_gold_24h_hist
- vn_silver_phuquy_hist
- vn_sbv_interbankrate
- vn_bank_termdepo

GLOBAL_INDICATOR_DB:
- global_macro (gold futures, silver, NASDAQ)

ARGUS_FINTEL_DB:
- gold_analysis (AI generated analysis)
```

## Files That Use Environment Variables

1. **crawl_tools/crawl_bot.py**
   - DATABASE_URL (fallback hardcoded for GitHub Actions)
   - GLOBAL_INDICATOR_DB (fallback hardcoded for GitHub Actions)

2. **agent_finance/gold_analysis_agent.py**
   - DATABASE_URL (required)
   - GLOBAL_INDICATOR_DB (required)
   - ARGUS_FINTEL_DB (required)
   - GEMINI_API_KEY (required)

3. **agent_finance/back/main.py**
   - DATABASE_URL (required)
   - GLOBAL_INDICATOR_DB (required)
   - ARGUS_FINTEL_DB (required)
   - GEMINI_API_KEY (required)
   - SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ALLOW_ORIGINS

## Verification

Test local setup:
```bash
cd agent_finance
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('DATABASE_URL:', os.getenv('DATABASE_URL')[:50]); print('GLOBAL_INDICATOR_DB:', os.getenv('GLOBAL_INDICATOR_DB')[:50]); print('ARGUS_FINTEL_DB:', os.getenv('ARGUS_FINTEL_DB')[:50])"
```
