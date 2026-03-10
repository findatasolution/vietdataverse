# Viet Dataverse — Product Description

## 1. What Is Viet Dataverse?

**Viet Dataverse** (domain: vietdataverse.online) is a free, open-source Vietnamese economic data platform that automatically aggregates, cleans, and serves financial market data — including gold prices, silver prices, bank interest rates, exchange rates, and global macro indicators.

The platform serves three types of users:
- **Retail investors / analysts** who need historical Vietnamese financial data for research
- **Developers / fintech teams** who need a free REST API for Vietnamese economic data
- **General public** who want to monitor daily gold/silver/FX movements with clean charts

---

## 2. Core Products

### 2.1 Open Economic Data (Free)
The flagship product — a SPA (single-page app) dashboard with:

| Dataset | Coverage | Update Frequency |
|---|---|---|
| Domestic gold prices (DOJI HN, DOJI SG, SJC, BTMC, DONGA BANK) | 2015–present | 2x daily (8:30 AM, 2:30 PM) |
| Silver prices (Phú Quý Group) | Historical | 2x daily |
| SBV interbank rates (overnight → 9 months) | 2025–present | Daily |
| Bank term deposit rates (ACB, VCB, CTG, SHB) | Historical | Daily |
| VCB FX rates (USD/VND, EUR/VND, JPY/VND) | Historical | Daily |
| Global macro (COMEX Gold GC=F, Silver SI=F, NASDAQ ^IXIC) | Historical | 2x daily |

Data is served via:
- **Static JSON files** on GitHub Pages (zero latency CDN, no cost)
- **REST API** at api.vietdataverse.online (FastAPI, hosted on Render.com)
- **CSV download** directly from charts in the UI

### 2.2 1s Market Pulse (Free)
A real-time financial news aggregator that uses AI (Gemini) to score each news article with an **MRI (Market Relevance Index)** score from -100 to +100, indicating the likely directional impact on specific Vietnamese assets (VN-Index, gold, real estate, banking, FX). Only articles with |MRI| ≥ 60 are displayed — filtering noise for busy investors.

Sources: CNBC, BBC, MarketWatch + Vietnamese financial news.

### 2.3 1s Future Outlook (Free + Gated)
Research reports and interactive forecasts from the "Fintel Insight" brand:
- **Gold Forecast 2026** — Comprehensive analysis consolidating Goldman Sachs ($5,400), J.P. Morgan ($6,300), UBS ($6,200) targets with interactive simulation charts
- Upcoming: Vietnam real estate 2026, VN-Index 2026

### 2.4 Fintel AI Agent (Paid — Beta)
A suite of AI-powered financial agents available via subscription:

| Agent | Function |
|---|---|
| Market Analysis Agent | VN-Index tracking, technical analysis, trend detection, 24/7 alerts |
| Gold Trading Agent | SJC/DOJI/PNJ vs. XAU/USD spread analysis, buy/sell signals |
| News Sentiment Agent | 50+ news sources, NLP/LLM scoring, impact prediction |
| Custom Agent | Enterprise-grade agent built to specification |

**Pricing:**
- Starter: Free (1 agent, 1,000 API calls/month)
- Pro: $9.9/month (all agents, unlimited calls, real-time webhooks)
- Enterprise: Custom

**Domestic payment options:** PayOS (VietQR), SePay (bank transfer)

### 2.5 Đối Tác / Partners (Affiliate Revenue)
Referral partner page linking to:
- **SSI Securities** — largest Vietnam securities broker
- **VPBank Securities (VPBS)** — integrated with VPBank banking

### 2.6 Direct Advertising
Banner placement on the main dashboard header strip — available to brands via a self-serve form (1920×520 px, video/image, direct pricing).

---

## 3. Target User Segments

| Segment | Size (est.) | Need |
|---|---|---|
| Retail investors (individual) | 7M+ accounts in VN (2025) | Monitor gold, FX, savings rates |
| Academic researchers | Thousands | Historical Vietnamese economic data |
| Fintech developers | Thousands | Free Vietnamese financial API |
| Financial analysts | Thousands | Cross-asset macro analysis tools |
| New stock market entrants | 500K+ per year | Brokerage account guidance |

---

## 4. Value Proposition

1. **Free, no registration required** for most data — removes friction vs. paid data providers (Bloomberg, Reuters, local equivalents)
2. **Long historical depth** — gold price data from 2015 (10+ years)
3. **Automated pipeline** — 5 crawlers running daily via GitHub Actions, no manual updates
4. **Open source transparency** — data collection methodology published
5. **API-first** — developers can integrate directly without scraping
6. **AI-augmented** — Gemini LLM fallback ensures data collection resilience; MRI scoring adds intelligence layer
7. **Local market focus** — tracks nuances specific to Vietnam (SJC premium, SBV policy rates, VPBank/SSI ecosystem)

---

## 5. Competitive Landscape

| Competitor | Weakness vs. Viet Dataverse |
|---|---|
| SJC official website | No API, no history, no CSV |
| 24h.com.vn, giabac.vn | Charts only, no download, no API |
| Bloomberg / Reuters | Expensive, Vietnam data incomplete |
| VNDirect data service | Limited historical, requires account |
| Local fintech apps | Fragmented, not developer-friendly |

**Viet Dataverse's moat:** combination of free long-history CSV export + open REST API + AI news scoring — not offered together anywhere else for Vietnam data.

---

## 6. Platform Architecture Summary

```
User → GitHub Pages SPA (index.html)
          ↓ fetch JSON (static, fast)
       data/ folder on GitHub Pages CDN
          ↓ if premium/interactive
       api.vietdataverse.online (FastAPI on Render.com)
          ↓ authenticated routes
       PostgreSQL on Neon (3 DB instances)
          ↑ populated by
       GitHub Actions Crawlers (5 crawlers, daily cron)
          ↑ parse from
       DOJI, SJC, BTMC, giabac.vn, SBV.org.vn, VCB, Yahoo Finance
```

---

## 7. Branding

- **Brand name:** Viet Dataverse
- **Sub-brand:** Fintel Insight (for research/AI agent products)
- **Tagline:** "Economic Intelligence"
- **Visual identity:** Dark gold theme (#C9A55B), Playfair Display serif titles, Inter sans-serif body
- **Language:** Vietnamese primary, English secondary
- **Contact:** contact@vietdataverse.online / findatasolution@gmail.com
