# Viet Dataverse — Technical Document

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    USERS / BROWSERS                      │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────┐
│             FRONTEND — GitHub Pages CDN                  │
│  index.html (SPA) + style.css + auth.js + data/*.json   │
│  Domain: vietdataverse.online                            │
└──────────────────────────┬──────────────────────────────┘
                  Auth0    │ API calls (protected routes)
              ┌────────────┤
              ▼            ▼
   ┌─────────────┐  ┌──────────────────────────────────┐
   │    Auth0    │  │  BACKEND — FastAPI on Render.com  │
   │  vietdata   │  │  api.vietdataverse.online         │
   │  verse.jp   │  │  Python 3.11 + Uvicorn            │
   └─────────────┘  └─────────────────┬────────────────┘
                                      │ SQLAlchemy
              ┌───────────────────────┼───────────────────┐
              ▼                       ▼                    ▼
   ┌──────────────────┐ ┌──────────────────┐ ┌────────────────────┐
   │ CRAWLING_BOT_DB  │ │ GLOBAL_INDICATOR │ │    USER_DB         │
   │ (Neon PostgreSQL)│ │ _DB (Neon PG)    │ │ (Neon PostgreSQL)  │
   │ Gold, Silver, FX │ │ Global macro,    │ │ Users, Payments    │
   │ SBV, Term Deposit│ │ Market pulse     │ │ Subscriptions      │
   └──────────────────┘ └──────────────────┘ └────────────────────┘
              ▲
   ┌──────────┴──────────────────────────────────────┐
   │          GITHUB ACTIONS — 5 Crawlers            │
   │  Gold/Silver (2x daily) │ SBV (daily)           │
   │  Term Deposits (daily)  │ FX Rates (daily)      │
   │  Market Pulse (sched)   │ Static Gen (post-run) │
   └─────────────────────────────────────────────────┘
              ▲ HTTP scraping
   ┌──────────┴──────────────────────────────────────┐
   │            EXTERNAL DATA SOURCES                │
   │  giabac.vn, 24h.com.vn, phuquygroup.vn          │
   │  sbv.gov.vn, vietcombank.com.vn                 │
   │  Yahoo Finance (yfinance)                       │
   └─────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | HTML5, Vanilla JS, CSS3 | No framework — zero JS bundle overhead |
| Charts | Chart.js 4.4.1 | Deferred load, canvas-based |
| Authentication (frontend) | Auth0 SPA SDK 2.1 | PKCE flow |
| PWA | Web App Manifest | Installable, offline capable |
| Backend | Python 3.11 + FastAPI | Async/await throughout |
| ASGI server | Uvicorn | Production ASGI |
| ORM | SQLAlchemy 2.0 | Async engine |
| Database driver | psycopg2-binary | PostgreSQL |
| Database | PostgreSQL via Neon | Serverless, ap-southeast-1 |
| Authentication (backend) | Auth0 RS256 JWT | python-jose[cryptography] |
| Payment | PayOS + SePay | VietQR + bank transfer |
| AI / LLM | Google Gemini 2.5 | Parsing fallback + analysis |
| Web scraping | BeautifulSoup4, requests | HTML parsing |
| Browser automation | Selenium + ChromeDriver | Bank deposit rates |
| Data processing | Pandas | Normalization, dedup |
| API hosting | Render.com (free tier) | Auto-sleep on inactivity |
| Frontend hosting | GitHub Pages | Free CDN via git push |
| Image CDN | ImageKit.io | Logos, OG images |
| Analytics | Google Analytics 4 | GA4 + Tag Manager |
| Ads | Google AdSense | pub-6080033337103483 |
| CI/CD | GitHub Actions | Cron + workflow_dispatch |
| Domain/DNS | Cloudflare | vietdataverse.online |

---

## 3. Frontend Architecture

### Single Page Application (SPA) Structure

`index.html` is a **~3,730-line monolithic SPA** with client-side tab routing. No build step, no bundler — served directly as static HTML.

**Tab routing pattern:**
```javascript
// Each section is a div.tab-content with an id
// Navigation triggers data-tab attribute switching
// Active class applied via JS; CSS hides/shows sections
document.querySelectorAll('[data-tab]').forEach(link => {
    link.addEventListener('click', () => switchTab(link.dataset.tab));
});
```

**Tab sections and IDs:**
| Tab | DOM ID | Content |
|---|---|---|
| Open Economic Data | `#data-portal` | Charts + articles + CSV download |
| 1s Market Pulse | `#1smarket-portal` | Live news + MRI scores |
| 1s Future Outlook | `#1s-future-outlook` | Research report cards |
| Fintel AI Agent | `#fintel-agent-for-hire` | Pricing + agent descriptions |
| About & Terms | `#about-terms` | Project info + ToS |
| Privacy Policy | `#privacy-policy` | GDPR-style privacy doc |
| Contact | `#contact` | Contact cards + ad request form |

**Chart lazy-loading:**
- Tab 1 (gold/silver) loads immediately on DOMContentLoaded
- Tabs 2 & 3 are lazy-loaded on first tab click via IntersectionObserver pattern
- Skeleton loaders shown during fetch

**Data fetching strategy:**
```javascript
// Static JSON from GitHub Pages (primary — fast, free)
const BASE_URL = 'https://vietdataverse.online/data/';
// Falls back to API for dynamic/auth-required data
const API_URL  = 'https://api.vietdataverse.online/api/v1/';
```

**i18n (bilingual):**
```javascript
// data-i18n attributes on HTML elements
// translations object with vi/en keys
// updateLanguage(lang) swaps textContent
// Saved to localStorage
```

### Auth Flow (auth.js)
```
User clicks Login
    → auth0Client.loginWithRedirect()
    → Redirect: vietdataverse.jp.auth0.com/authorize?...
    → User authenticates (Google SSO or email)
    → Callback: /index.html?code=...
    → auth0Client.handleRedirectCallback()
    → getAccessToken() → JWT for API calls
    → User info displayed in header
```

**Auth0 config:**
```javascript
domain:    'vietdataverse.jp.auth0.com'
clientId:  'EDXXS3TBQpJ3HhWilLLgEHNB8SsAvG0O'
audience:  'https://api.vietdataverse.online'
scope:     'openid profile email'
```

---

## 4. Backend API (FastAPI)

### Base URL
`https://api.vietdataverse.online`

### Public Endpoints (No Authentication)

```
GET  /api/v1/gold
     ?gold_type=DOJI HN|BTMC SJC|DOJI SG|BTMH|DONGA BANK
     ?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
     → JSON: [{date, buy, sell, type, source}]
     → CSV: via ?format=csv

GET  /api/v1/silver
     ?start_date=&end_date=
     → [{date, buy, sell, unit: "nghìn VND/lượng"}]

GET  /api/v1/sbv-interbank
     ?term=overnight|1w|2w|1m|3m|6m|9m
     → [{date, term, rate, volume}]

GET  /api/v1/sbv-centralrate
     → [{date, usd_vnd_central, document_no}]

GET  /api/v1/termdepo
     ?bank=VCB|ACB|CTG|SHB
     → [{date, bank, term_months, rate_pa}]

GET  /api/v1/global-macro
     → [{date, gold_usd_oz, silver_usd_oz, nasdaq}]

GET  /api/v1/gold-analysis
     → {analysis: "...", generated_at: "..."}  (Gemini output)

GET  /api/v1/market-pulse
     → [{title, source, mri_score, label, published_at, url}]

GET  /api/v1/gold/types        → [{name, description, brand}]
GET  /api/v1/termdepo/banks    → [{code, full_name, logo_url}]

GET  /health                   → {status: "ok"}
GET  /api/docs                 → Swagger UI
```

### Protected Endpoints (Bearer JWT Required)
```
GET  /me                        → {user_id, email, role, is_premium, premium_expiry}
GET  /api/protected             → auth test
GET  /api/dashboard             → user dashboard data
POST /api/v1/interest/{type}    → track user interest clicks
GET  /api/v1/interest/stats     → aggregated interest (admin)
GET  /api/v1/admin/users        → user list (is_admin only)
POST /api/v1/generate-market-pulse  → trigger AI analysis
```

### Authentication Middleware
```python
# auth.py — RS256 JWT verification
# Public key fetched from: vietdataverse.jp.auth0.com/.well-known/jwks.json
# Claims verified: aud, iss, exp
# Custom claims extracted from namespace: https://vietdataverse.online/
#   role, business_unit, is_admin, email
```

---

## 5. Database Schema

### CRAWLING_BOT_DB

**`vn_gold_24h_hist`**
```sql
id          SERIAL PRIMARY KEY
crawled_at  TIMESTAMP
price_date  DATE
gold_type   VARCHAR  -- 'DOJI HN', 'BTMC SJC', 'DOJI SG', 'BTMH', 'DONGA BANK'
buy_price   NUMERIC  -- nghìn VND/chỉ
sell_price  NUMERIC
source      VARCHAR  -- '24h.com.vn'
UNIQUE(price_date, gold_type)
```

**`vn_silver_phuquy_hist`**
```sql
id          SERIAL PRIMARY KEY
crawled_at  TIMESTAMP
price_date  DATE
buy_price   NUMERIC  -- nghìn VND/lượng
sell_price  NUMERIC
source      VARCHAR
UNIQUE(price_date)
```

**`vn_sbv_interbankrate`**
```sql
id          SERIAL PRIMARY KEY
rate_date   DATE
term        VARCHAR  -- 'overnight','1w','2w','1m','3m','6m','9m'
rate        NUMERIC  -- %/year
volume      NUMERIC  -- billion VND
UNIQUE(rate_date, term)
```

**`vn_sbv_centralrate`**
```sql
id           SERIAL PRIMARY KEY
rate_date    DATE UNIQUE
usd_vnd      NUMERIC  -- central rate
document_no  VARCHAR
```

**`vn_termdepo_rate_hist`**
```sql
id           SERIAL PRIMARY KEY
crawled_at   TIMESTAMP
bank         VARCHAR  -- 'VCB','ACB','CTG','SHB'
term_months  INTEGER  -- 1,3,6,12,24,36
rate_pa      NUMERIC  -- %/year annual
UNIQUE(crawled_at::date, bank, term_months)
```

**`vn_fxrate_vcb_hist`**
```sql
id           SERIAL PRIMARY KEY
rate_date    DATE
currency     VARCHAR  -- 'USD','EUR','JPY'
buy_cash     NUMERIC  -- VND
buy_transfer NUMERIC
sell         NUMERIC
UNIQUE(rate_date, currency)
```

### USER_DB

**`users`**
```sql
user_id         SERIAL PRIMARY KEY
auth0_id        VARCHAR UNIQUE NOT NULL  -- Auth0 sub
email           VARCHAR UNIQUE NOT NULL
name            VARCHAR
picture         VARCHAR  -- URL
role            VARCHAR DEFAULT 'user'  -- user|gceo|bugm
business_unit   VARCHAR  -- APAC|EMEA|Americas (for bugm)
is_admin        BOOLEAN DEFAULT false
is_premium      BOOLEAN DEFAULT false
premium_expiry  TIMESTAMP
auth0_metadata  JSONB
created_at      TIMESTAMP DEFAULT NOW()
last_login      TIMESTAMP
```

**`payment_orders`**
```sql
order_code  VARCHAR PRIMARY KEY  -- PayOS/SePay reference
user_id     INTEGER REFERENCES users
plan        VARCHAR  -- 'monthly'|'yearly'
amount      INTEGER  -- VND
status      VARCHAR  -- 'pending'|'paid'|'cancelled'
gateway     VARCHAR  -- 'payos'|'sepay'
created_at  TIMESTAMP
paid_at     TIMESTAMP
```

---

## 6. Data Pipeline (Crawlers)

### Architecture Pattern
```
GitHub Actions Cron → Python Script → PostgreSQL → generate_static_data.py → JSON files → Git commit → GitHub Pages
```

### Crawler 1: Gold & Silver (`crawl_gold_silver.py`)
```
Cron:   "30 1,7 * * *" (UTC) = 8:30 AM & 2:30 PM Vietnam
Sources:
  - Domestic gold: scrape 24h.com.vn/tai-chinh/gia-vang.html
    Parser: BeautifulSoup, table rows → brand/buy/sell
  - Domestic silver: scrape giabac.vn or phuquygroup.vn/giabac (fallback)
  - Global: yfinance.Ticker(['GC=F','SI=F','^IXIC']).history(period='2d')
Dedup:  SELECT WHERE price_date = today AND gold_type = X → skip if exists
Output: INSERT INTO vn_gold_24h_hist, vn_silver_phuquy_hist, global_macro
```

### Crawler 2: SBV Rates (`crawl_sbv.py`)
```
Cron:   "30 2 * * *" (UTC) = 9:30 AM Vietnam
Sources:
  1. sbv.gov.vn interbank API → JSON rates by term
  2. sbv.gov.vn/web/guest/thi-truong-tien-te → scrape central rate
  3. Fallback chain: HTML parser → regex heuristic → Gemini LLM
Output: INSERT INTO vn_sbv_interbankrate, vn_sbv_centralrate
```

### Crawler 3: Term Deposits (`crawl_bank_termdepo.py`)
```
Cron:   "30 1 * * *" (UTC) = 8:30 AM Vietnam
Method: Selenium + ChromeDriver (each bank has a JS-rendered rate table)
Banks:
  - VCB: vietcombank.com.vn → rates table
  - ACB: acb.com.vn → rates table
  - CTG: vietinbank.vn → rates table
  - SHB: shb.com.vn → rates table
Fallback: Gemini LLM to parse HTML if selectors change
Output: INSERT INTO vn_termdepo_rate_hist
```

### Crawler 4: FX Rates (`crawl_exchange_rate.py`)
```
Cron:   Daily
Source: vietcombank.com.vn/personal-service/foreign-exchange/
Pairs:  USD/VND, EUR/VND, JPY/VND (buy cash, buy transfer, sell)
Output: INSERT INTO vn_fxrate_vcb_hist
```

### Static Data Generation (`generate_static_data.py`)
```
Trigger: After each crawler run + every 6h backup
Action:
  1. Query DB for last 7d, 1m, 1y of each dataset
  2. Serialize to JSON
  3. Write to data/*.json
  4. Git commit --allow-empty + push → GitHub Pages CDN updated
Output: 52 JSON files in /data folder
```

---

## 7. GitHub Actions CI/CD

**Workflow trigger patterns:**
```yaml
on:
  schedule:
    - cron: '30 1 * * *'  # UTC time
  workflow_dispatch:       # Manual trigger from GitHub UI
  workflow_run:            # Chain: triggered after another workflow
    workflows: ["Gold Crawl"]
    types: [completed]
```

**Standard runner setup:**
```yaml
steps:
  - uses: actions/checkout@v3
  - uses: actions/setup-python@v4
    with: {python-version: '3.11'}
  - run: pip install -r crawl_tools/requirements.txt
  - run: python crawl_tools/crawl_gold_silver.py
    env:
      CRAWLING_BOT_DB: ${{ secrets.CRAWLING_BOT_DB }}
      GEMINI_API_KEY:  ${{ secrets.GEMINI_API_KEY }}
  - run: |
      git config user.email "bot@vietdataverse.online"
      git add data/
      git commit -m "data: auto-update [skip ci]" || true
      git push
```

---

## 8. Payment Integration

### PayOS (VietQR)
```python
# POST /api/v1/payment/create
# Creates payment order → returns QR code URL
# PayOS calls webhook: POST /api/v1/payment/webhook/payos
# Webhook verifies HMAC-SHA256 signature
# On success: UPDATE users SET is_premium=true, premium_expiry=...
```

### SePay (Bank Transfer)
```python
# User transfers with memo: "VIP{user_id}M" or "VIP{user_id}Y"
# SePay webhook: POST /api/v1/payment/webhook/sepay
# Verified by API key in header
# Parses memo → identifies user → activates premium
```

---

## 9. Hosting & Deployment

| Component | Provider | Plan | Cost |
|---|---|---|---|
| Frontend SPA | GitHub Pages | Free | $0 |
| Static data CDN | GitHub Raw/Pages | Free | $0 |
| Backend API | Render.com | Free web service | $0 |
| Database (x3) | Neon PostgreSQL | Free tier | $0 |
| Image CDN | ImageKit.io | Free tier | $0 |
| Auth | Auth0 | Free tier | $0 |
| Domain | — | Paid | ~$10/yr |
| **Total infra cost** | | | **~$10/yr** |

**Render.com cold start note:** Free tier services sleep after 15min inactivity. First API call after sleep has ~30s delay. Static JSON files (served via GitHub Pages) are unaffected.

---

## 10. Key Configuration Values

```
# Auth0
AUTH0_DOMAIN    = vietdataverse.jp.auth0.com
AUTH0_CLIENT_ID = EDXXS3TBQpJ3HhWilLLgEHNB8SsAvG0O
AUTH0_AUDIENCE  = https://api.vietdataverse.online

# AdSense
ADSENSE_PUBLISHER = ca-pub-6080033337103483
ADSENSE_SLOT_HEADER = 2529535655

# Google Analytics
GA4_ID_1 = G-YB3PKHN2E5
GA4_ID_2 = G-B9BHYSYDES

# Neon DB regions: ap-southeast-1 (Singapore)
# Render region: Singapore (ap-southeast-1)
```

---

## 11. SEO Setup

- **Canonical URL:** https://vietdataverse.online/
- **Structured Data (JSON-LD):** Organization, Article, Dataset (x2), FAQPage, BreadcrumbList, WebSite, WebPage (partners)
- **Sitemap:** /sitemap.xml
- **robots.txt:** Allow all
- **Meta:** full OG + Twitter Card on all pages
- **i18n:** hreflang vi/en/x-default
- **Noscript fallback:** Full text content (~500 words) for JS-disabled crawlers
- **ads.txt:** `google.com, pub-6080033337103483, DIRECT, f08c47fec0942fa0`
