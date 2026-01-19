# Viet Dataverse - Technical Documentation

## Project Overview

**Viet Dataverse** is an open data platform providing free access to Vietnam's economic and financial data, including historical gold prices, silver prices, SBV interbank rates, and bank term deposit rates. The platform features automated daily data crawling, AI-powered market analysis, and CSV download capabilities for researchers and analysts.

**Live URL:** [https://hiienng.github.io/nguyenphamdieuhien.online/vietdataverse/](https://hiienng.github.io/nguyenphamdieuhien.online/vietdataverse/)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VIET DATAVERSE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │   Frontend   │    │   Backend    │    │  Data Layer  │                   │
│  │  (GitHub     │◄──►│  (Render)    │◄──►│  (Neon       │                   │
│  │   Pages)     │    │  FastAPI     │    │   PostgreSQL)│                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│         │                   ▲                    ▲                           │
│         │                   │                    │                           │
│         ▼                   │                    │                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │    User      │    │  Crawl Bot   │    │  AI Analysis │                   │
│  │  Interface   │    │  (GitHub     │    │  Agent       │                   │
│  │  Chart.js    │    │   Actions)   │    │  (Gemini AI) │                   │
│  └──────────────┘    └──────────────┘    └──────────────┘                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| **HTML5/CSS3** | Structure and styling |
| **Vanilla JavaScript** | DOM manipulation, API calls |
| **Chart.js 4.4.0** | Interactive data visualization |
| **Font Awesome 6.0** | Icons |
| **GitHub Pages** | Static hosting |

### Backend
| Technology | Purpose |
|------------|---------|
| **Python 3.11** | Core programming language |
| **FastAPI** | REST API framework |
| **SQLAlchemy** | ORM and database operations |
| **Uvicorn** | ASGI server |
| **Render.com** | Backend hosting (Free tier) |

### Data Pipeline
| Technology | Purpose |
|------------|---------|
| **GitHub Actions** | Scheduled automation (cron jobs) |
| **Selenium** | Dynamic web scraping |
| **BeautifulSoup4** | HTML parsing |
| **Requests** | HTTP client |
| **yfinance** | Global market data (Yahoo Finance) |
| **Pandas** | Data manipulation |

### AI/ML
| Technology | Purpose |
|------------|---------|
| **Google Gemini 2.5 Flash** | Market analysis generation |
| **google-generativeai SDK** | Gemini API integration |

### Database
| Database | Purpose | Tables |
|----------|---------|--------|
| **CRAWLING_BOT_DB** | Domestic market data | `vn_gold_24h_hist`, `vn_silver_phuquy_hist`, `vn_sbv_interbankrate`, `vn_bank_termdepo` |
| **GLOBAL_INDICATOR_DB** | Global market data | `global_macro` |
| **ARGUS_FINTEL_DB** | AI analysis storage | `gold_analysis` |

All databases are hosted on **Neon PostgreSQL** (serverless).

---

## Data Sources

| Data Type | Source | Frequency | Method |
|-----------|--------|-----------|--------|
| Vietnam Gold Prices (SJC, DOJI, PNJ) | 24h.com.vn | Daily | HTTP Request + BeautifulSoup |
| Vietnam Silver Prices | phuquy.com.vn | Daily | Selenium (JavaScript-rendered) |
| SBV Interbank Rates | sbv.gov.vn API | Daily | REST API |
| SBV Policy Rates (Rediscount, Refinancing) | sbv.gov.vn | Daily | HTTP + BeautifulSoup |
| Bank Term Deposit Rates | acb.com.vn | Daily | HTTP + BeautifulSoup |
| Global Gold/Silver Futures | Yahoo Finance | Daily | yfinance library |
| NASDAQ Composite | Yahoo Finance | Daily | yfinance library |

---

## Automated Pipeline

### Daily Crawl Schedule (GitHub Actions)

```yaml
schedule:
  - cron: '30 1 * * *'  # 8:30 AM Vietnam Time (UTC+7)
```

### Pipeline Flow

```
08:30 VN ──► Crawl Bot Starts
              │
              ├── 1. Crawl Vietnam Silver (Selenium)
              ├── 2. Crawl Vietnam Gold (HTTP)
              ├── 3. Crawl SBV Interbank Rates (API)
              ├── 4. Crawl SBV Policy Rates (HTTP)
              ├── 5. Crawl Bank Term Deposits (HTTP)
              └── 6. Crawl Global Macro (yfinance)
              │
              ▼
         Gold Analysis Agent
              │
              ├── Fetch 7-day global data
              ├── Fetch 7-day Vietnam gold data
              ├── Generate prompt with market context
              ├── Call Gemini AI for analysis
              └── Save analysis to database
              │
              ▼
         Pipeline Complete
```

---

## API Endpoints

### Base URL
- **Production:** `https://nguyenphamdieuhien.online`
- **Local:** `http://localhost:8000`

### Available Endpoints

| Method | Endpoint | Description | Parameters |
|--------|----------|-------------|------------|
| GET | `/api/v1/gold` | Vietnam gold prices | `period` (1m/3m/6m/1y/all), `type` |
| GET | `/api/v1/silver` | Vietnam silver prices | `period` |
| GET | `/api/v1/sbv` | SBV interbank rates | `period` |
| GET | `/api/v1/global-macro` | Global market data | `period` |
| GET | `/api/v1/gold-analysis` | AI market analysis | `date` (optional) |
| GET | `/api/dataverse/datasets` | List all datasets | - |
| GET | `/api/dataverse/{dataset}/csv` | Download dataset CSV | - |

### Response Format

```json
{
  "success": true,
  "data": {
    "dates": ["2024-01-01", "2024-01-02", ...],
    "buy_prices": [75000000, 75100000, ...],
    "sell_prices": [76000000, 76100000, ...],
    "count": 30
  },
  "period": "1m",
  "type": "DOJI HN"
}
```

---

## Database Schema

### vn_gold_24h_hist
```sql
CREATE TABLE vn_gold_24h_hist (
    date DATE NOT NULL,
    type VARCHAR(50) NOT NULL,
    buy_price NUMERIC,
    sell_price NUMERIC,
    PRIMARY KEY (date, type)
);
```

### vn_sbv_interbankrate
```sql
CREATE TABLE vn_sbv_interbankrate (
    date DATE PRIMARY KEY,
    crawl_time TIMESTAMP,
    ls_quadem NUMERIC,      -- Overnight rate
    ls_1w NUMERIC,          -- 1 week
    ls_2w NUMERIC,          -- 2 weeks
    ls_1m NUMERIC,          -- 1 month
    ls_3m NUMERIC,          -- 3 months
    ls_6m NUMERIC,          -- 6 months
    ls_9m NUMERIC,          -- 9 months
    doanhso_quadem NUMERIC, -- Overnight volume
    doanhso_1w NUMERIC,
    doanhso_2w NUMERIC,
    doanhso_1m NUMERIC,
    doanhso_3m NUMERIC,
    doanhso_6m NUMERIC,
    doanhso_9m NUMERIC,
    rediscount_rate NUMERIC,   -- SBV rediscount rate
    refinancing_rate NUMERIC   -- SBV refinancing rate
);
```

### global_macro
```sql
CREATE TABLE global_macro (
    date DATE PRIMARY KEY,
    crawl_time TIMESTAMP,
    gold_price NUMERIC,    -- COMEX Gold Futures ($/oz)
    silver_price NUMERIC,  -- Silver Futures ($/oz)
    nasdaq_price NUMERIC   -- NASDAQ Composite Index
);
```

### gold_analysis
```sql
CREATE TABLE gold_analysis (
    date DATE PRIMARY KEY,
    generated_at TIMESTAMP NOT NULL,
    content TEXT NOT NULL,         -- HTML content
    global_data_points INTEGER,
    vietnam_data_points INTEGER
);
```

---

## Key Features

### 1. Responsive Data Visualization
- Interactive Chart.js charts with zoom/pan capabilities
- Mobile-optimized touch interactions
- Tooltip with detailed price information

### 2. Multi-language Support
- Vietnamese (default)
- English translation
- Language toggle with localStorage persistence

### 3. CSV Export
- Client-side CSV generation (no server dependency)
- Full historical data download
- Proper UTF-8 encoding for Vietnamese text

### 4. AI-Powered Analysis
- Daily automated market analysis
- Context-aware prompts with real market data
- Structured HTML output for consistent formatting

### 5. SEO Optimization
- Semantic HTML structure
- Schema.org structured data
- Meta tags for social sharing
- Keywords: "tải lịch sử giá vàng", "download vietnam historical gold price"

---

## Security Considerations

- Environment variables for all credentials
- No hardcoded API keys in codebase (fallbacks only for development)
- CORS configured for specific origins
- SQL injection prevention via SQLAlchemy parameterized queries
- Rate limiting on yfinance requests with exponential backoff

---

## Deployment

### GitHub Pages (Frontend)
```bash
# Automatic deployment on push to main branch
# Static files served from /vietdataverse/
```

### Render.com (Backend)
```yaml
# render.yaml
services:
  - type: web
    name: nguyenphamdieuhien.online
    env: python
    region: singapore
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn back.main:app --host 0.0.0.0 --port $PORT
```

### GitHub Actions (Automation)
```yaml
# .github/workflows/daily-crawl.yml
# Triggered daily at 08:30 Vietnam time
# Manual trigger available via workflow_dispatch
```

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Frontend Load Time | < 2s |
| API Response Time | < 500ms |
| Data Coverage | 2009 - Present |
| Total Gold Records | 33,000+ |
| Daily Crawl Duration | ~3 minutes |

---

## Future Roadmap

- [ ] Add more data sources (stock indices, forex rates)
- [ ] Implement data caching layer (Redis)
- [ ] Build mobile app (React Native)
- [ ] Add user authentication for premium features
- [ ] Expand AI analysis to cover silver and other commodities

---

## License

This project is open source. Data is provided for educational and research purposes only.

---

## Contact

**Developer:** Nguyen Pham Dieu Hien
**Website:** [nguyenphamdieuhien.online](https://nguyenphamdieuhien.online)
**GitHub:** [hiienng](https://github.com/hiienng)