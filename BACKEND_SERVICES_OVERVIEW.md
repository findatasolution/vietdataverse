# Backend Services Overview - Render Deployment

## 📊 Current Backend Services Running on Render

### 1. **AI Finance API** (Currently Deployed)
- **Service Name**: `nguyenphamdieuhien.online`
- **Location**: `agent_finance/back/main.py`
- **Framework**: FastAPI + Uvicorn
- **Port**: Dynamic ($PORT from Render)
- **Database**: Neon PostgreSQL
- **Purpose**: AI-powered financial analysis with Gemini API
- **URL**: https://nguyenphamdieuhien.online

**Features:**
- User authentication (JWT)
- AI chat for financial analysis
- Product/asset management
- Database integration

**Start Command:**
```bash
uvicorn back.main:app --host 0.0.0.0 --port $PORT
```

---

## 🆕 New Backend Services You Need to Deploy

### 2. **Viet Dataverse API** (NEW - Need to Deploy)
- **Location**: `api/download_data.py`
- **Framework**: Flask
- **Port**: 5000 (will be $PORT on Render)
- **Database**: Neon PostgreSQL (same as AI Finance)
- **Purpose**: CSV dataset downloads for research data

**Features:**
- Download CSV datasets (VNGold, VNSilver, SBVInterbank, etc.)
- Preview dataset data
- List all available datasets
- Direct database queries

**Start Command:**
```bash
python api/download_data.py
```

---

## 🎯 Consolidated Solution: ONE Backend for Everything

You have **two options**:

### ✅ OPTION 1: Merge into ONE Backend (RECOMMENDED)

**Merge the Dataverse API into your existing AI Finance backend**

**Advantages:**
- ✅ Only ONE Render service to manage
- ✅ Share same database connection
- ✅ Share same environment variables
- ✅ Reduced costs (one service instead of two)
- ✅ Simpler deployment and maintenance
- ✅ No CORS issues between services

**How to do it:**
Add the CSV download endpoints to your existing `agent_finance/back/main.py`

I can create a new router file: `agent_finance/back/routers/dataverse.py`

```python
# agent_finance/back/routers/dataverse.py
from fastapi import APIRouter, Response
from fastapi.responses import StreamingResponse
import pandas as pd
import io

router = APIRouter(prefix="/api/dataverse", tags=["dataverse"])

@router.get("/download/{dataset_name}")
async def download_dataset(dataset_name: str):
    # Same logic as Flask app
    # Query database, generate CSV, return as file
    pass
```

Then in your main FastAPI app, just include this router.

**Result:**
- One backend URL: `https://nguyenphamdieuhien.online`
- AI Finance endpoints: `https://nguyenphamdieuhien.online/api/auth/*`, `https://nguyenphamdieuhien.online/api/chat/*`
- Dataverse endpoints: `https://nguyenphamdieuhien.online/api/dataverse/*`

---

### ❌ OPTION 2: Deploy as Separate Service (NOT RECOMMENDED)

Keep two separate backend services on Render.

**Current:**
1. AI Finance API: https://nguyenphamdieuhien.online

**New:**
2. Dataverse API: https://viet-dataverse-api.onrender.com (or similar)

**Disadvantages:**
- ❌ Two services = 2x monitoring, 2x deployments
- ❌ Potential CORS configuration issues
- ❌ More complex infrastructure
- ❌ Duplicate database connection code
- ❌ Higher resource usage

---

## 🔄 Background Jobs (Existing)

### 3. **Daily Data Crawl** (GitHub Actions - FREE)
- **Location**: `.github/workflows/daily-crawl.yml`
- **Purpose**: Crawl gold/silver/interbank data daily
- **Schedule**: 1 AM UTC (8 AM Vietnam)
- **Platform**: GitHub Actions (not Render)
- **Status**: ✅ Already configured

This runs automatically on GitHub's infrastructure for free - no need to deploy on Render.

---

## 📋 Summary: What You Need on Render

| Service | Status | Framework | Purpose | Recommendation |
|---------|--------|-----------|---------|----------------|
| AI Finance API | ✅ Deployed | FastAPI | AI chat, auth, products | Keep as is |
| Dataverse API | 🆕 New | Flask | CSV downloads | **Merge into AI Finance** |
| Daily Crawl | ✅ Active | Python Script | Data collection | Keep on GitHub Actions |

---

## 💡 Recommended Architecture

```
┌─────────────────────────────────────────┐
│     Render Web Service (FREE TIER)      │
│  https://nguyenphamdieuhien.online      │
│                                         │
│  ┌───────────────────────────────────┐  │
│  │   FastAPI Backend (Uvicorn)       │  │
│  │                                   │  │
│  │  /api/auth/*      - Auth/Login    │  │
│  │  /api/chat/*      - AI Finance    │  │
│  │  /api/products/*  - Products      │  │
│  │  /api/dataverse/* - CSV Download  │  │ ← NEW
│  └───────────────────────────────────┘  │
│              ↓                          │
│    Neon PostgreSQL Database             │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│     GitHub Actions (FREE)               │
│  .github/workflows/daily-crawl.yml      │
│                                         │
│  Runs daily at 8 AM Vietnam time        │
│  → Crawls data → Writes to Neon DB      │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│     Static Site (GitHub Pages)          │
│  https://hiienng.github.io              │
│                                         │
│  index.html → Calls Backend APIs        │
└─────────────────────────────────────────┘
```

---

## 🚀 Implementation Steps (Recommended Approach)

### Step 1: Merge Dataverse into AI Finance Backend

I can help you:
1. Create `agent_finance/back/routers/dataverse.py` with FastAPI routes
2. Convert Flask endpoints to FastAPI
3. Update your `main.py` to include the new router
4. Test locally

### Step 2: Update Frontend

Change the API URL in `index.html`:
```javascript
// OLD
const API_BASE_URL = 'http://localhost:5000/api';

// NEW
const API_BASE_URL = 'https://nguyenphamdieuhien.online/api/dataverse';
```

### Step 3: Deploy

Push to GitHub → Render auto-deploys your updated backend

---

## 💰 Cost Analysis

### Current Setup (Option 1 - Merged):
- **1 Render Web Service** (Free Tier): $0/month
- **GitHub Actions** (Free Tier): $0/month
- **Neon PostgreSQL** (Free Tier): $0/month
- **Total: $0/month** ✅

### If You Use Option 2 (Separate):
- **2 Render Web Services** (Free Tier): $0/month initially
- But Render Free tier has limits:
  - 750 hours/month per service
  - If BOTH services are always on = 1,500 hours needed
  - **You'll need to upgrade to paid** after hitting limits

---

## ✅ My Recommendation

**Merge everything into ONE backend service.**

Benefits:
1. ✅ Simpler to manage
2. ✅ One URL to remember
3. ✅ No CORS issues
4. ✅ Stays within free tier limits
5. ✅ Shared database connection pool
6. ✅ Easier to add more features later

Would you like me to implement Option 1 (merge the dataverse API into your existing FastAPI backend)?
