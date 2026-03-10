# Viet Dataverse — Project Documentation Index

**Project:** Viet Dataverse (vietdataverse.online)
**Type:** Free Vietnamese Economic Data Platform + Fintel AI Agent SaaS
**Stack:** FastAPI + PostgreSQL + GitHub Pages + Auth0 + Google Gemini

---

## Documents

| File | Contents |
|---|---|
| [01_PRODUCT_DESCRIPTION.md](01_PRODUCT_DESCRIPTION.md) | What the platform is, all products, user segments, value proposition, competitive landscape |
| [02_TECHNICAL_DOCUMENT.md](02_TECHNICAL_DOCUMENT.md) | Full architecture, tech stack, API endpoints, DB schema, crawlers, CI/CD, hosting |
| [03_BUSINESS_MODEL_LTV.md](03_BUSINESS_MODEL_LTV.md) | All revenue streams, LTV per user segment, unit economics, growth model, cost structure |

---

## Quick Context (for ChatGPT — paste this first)

```
Project: Viet Dataverse
Domain: vietdataverse.online
API: api.vietdataverse.online

What it is: A free Vietnamese economic data platform.
Aggregates gold prices (DOJI, SJC, BTMC), silver prices, SBV interbank rates,
bank deposit rates (VCB/ACB/CTG/SHB), VCB FX rates, and global macro (COMEX
gold/silver, NASDAQ). Data served as static JSON via GitHub Pages CDN + FastAPI
REST API. Frontend is a vanilla JS SPA on GitHub Pages.

Tech stack:
  Frontend:  HTML/CSS/Vanilla JS, Chart.js, Auth0 SPA SDK, GitHub Pages
  Backend:   Python 3.11 + FastAPI + Uvicorn on Render.com
  Database:  PostgreSQL × 3 instances on Neon (crawl data, global data, users)
  Crawlers:  5 GitHub Actions cron jobs scraping Vietnamese financial websites
  AI:        Google Gemini 2.5 (crawl parsing fallback + market analysis)
  Auth:      Auth0 (RS256 JWT), user roles: user|gceo|bugm|admin
  Payments:  PayOS (VietQR) + SePay (bank transfer) for VND subscriptions

Revenue streams:
  1. Google AdSense (header banner — pub-6080033337103483)
  2. Affiliate: VPBS + SSI securities account referral
  3. Fintel AI Agent subscription: 99K VND/mo or 990K VND/year
  4. Direct banner advertising

Current status: AdSense pending approval. Affiliate active. Subscriptions in beta.
Infrastructure cost: ~$5–20/month (mostly free tiers). Gross margin ~90%.
```

---

## Key File Locations

```
nguyenphamdieuhien.online/
  index.html         ← Main SPA (3,730 lines, all frontend logic)
  style.css          ← Styling (gold theme)
  auth.js            ← Auth0 integration
  partners.html      ← Affiliate partner page
  ads.txt            ← AdSense authorization
  be/
    main.py          ← FastAPI app (30+ endpoints)
    models.py        ← SQLAlchemy ORM (User, PaymentOrder)
    database.py      ← 3 PostgreSQL connections
    auth.py          ← JWT verification
  crawl_tools/
    crawl_gold_silver.py   ← Gold/silver/global macro (2x daily)
    crawl_sbv.py           ← SBV rates (daily)
    crawl_bank_termdepo.py ← Bank deposit rates (daily, Selenium)
    crawl_exchange_rate.py ← VCB FX rates (daily)
  data/              ← 52 static JSON files (served via GitHub Pages CDN)
  pages/
    GoldForecast2026.html  ← Research report page
  docs/              ← This documentation folder
```
