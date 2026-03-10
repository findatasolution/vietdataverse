# Viet Dataverse — Business Model & LTV Analysis

## 1. Revenue Streams Overview

Viet Dataverse operates a **multi-revenue freemium model** with 4 monetization channels:

| Stream | Type | Maturity |
|---|---|---|
| Google AdSense | CPM/CPC display ads | Active (pending full approval) |
| Affiliate (VPBS, SSI) | CPA referral commission | Active |
| Premium Subscription (Fintel AI) | SaaS monthly/yearly | Beta |
| Direct Banner Advertising | Fixed CPM | Available |

---

## 2. Revenue Stream Details

### 2.1 Google AdSense

**Model:** CPM (Cost Per Mille) — revenue per 1,000 page impressions

**Placement:** Header banner strip (1920×520 px horizontal unit, slot 2529535655)

**Vietnam AdSense benchmarks (2025):**
- Average RPM (Revenue Per Mille pageviews): $0.30–$0.80 USD for Vietnamese finance content
- Finance niche commands higher rates than general content (typical multiplier: 1.5–2.5x)
- Estimated effective RPM for this niche: $0.50–$1.20

**Revenue formula:**
```
Monthly AdSense Revenue = (Monthly Pageviews / 1,000) × RPM

Example scenarios:
  Conservative (5,000 PV/mo)  → $2.50–$6.00/mo
  Growth      (20,000 PV/mo)  → $10–$24/mo
  Scale       (100,000 PV/mo) → $50–$120/mo
```

### 2.2 Affiliate Program (VPBS & SSI)

**Model:** CPA (Cost Per Acquisition) — fixed commission per verified account opened

**Commission estimates (Vietnam securities affiliates, 2025):**
- SSI referral: ~100,000–300,000 VND per activated account (~$4–$12)
- VPBS referral: ~100,000–300,000 VND per activated account (~$4–$12)
- Some brokers offer recurring commission on trading fees (~0.01–0.05% of monthly trading volume)

**Revenue formula:**
```
Monthly Affiliate Revenue = New Referrals × Avg Commission

Example:
  5 referrals/mo × 200,000 VND = 1,000,000 VND/mo (~$40)
  20 referrals/mo × 200,000 VND = 4,000,000 VND/mo (~$160)
```

### 2.3 Fintel AI Agent Subscription

**Pricing (VND):**
| Plan | Price | Period | USD Equiv |
|---|---|---|---|
| Pro Monthly | 99,000 VND | 30 days | ~$3.90 |
| Pro Yearly | 990,000 VND | 365 days | ~$39.00 |
| Enterprise | Custom | Custom | TBD |

**International pricing:** $9.9/month (displayed in UI)

**Payment:** PayOS (VietQR) + SePay (bank transfer)

**Revenue formula:**
```
Monthly Subscription Revenue
  = (Monthly subscribers × 99,000)
  + (Annual subscribers / 12 × 990,000)

Example:
  10 monthly + 5 annual = (10 × 99K) + (5 × 82.5K) = 1,402,500 VND/mo (~$55)
  50 monthly + 20 annual = (50 × 99K) + (20 × 82.5K) = 6,600,000 VND/mo (~$260)
```

### 2.4 Direct Banner Advertising

**Model:** Fixed weekly/monthly fee for brand banner in header strip

**Position:** Full-width 1920×520px header banner (video or image)
**Target advertisers:** Securities firms, fintech apps, banks, gold dealers

**Rate card estimate (Vietnamese finance publisher):**
| Duration | Price |
|---|---|
| 1 week | 500,000–2,000,000 VND |
| 1 month | 1,500,000–5,000,000 VND |

**Advantage over AdSense:** Higher yield if direct deal closed; brand-safe content.

---

## 3. LTV (Lifetime Value) by User Segment

### 3.1 Free User (No Account)

**Revenue generated:**
- AdSense impressions only
- Potential affiliate click-through

**LTV calculation:**
```
Avg sessions per month:    2–4
Avg pages per session:     2–3
Monthly pageviews:         4–12 PV
Annual pageviews:          48–144 PV
AdSense RPM:               $0.70 (mid-range)
Annual AdSense revenue:    $0.03–$0.10 per free user

LTV (1-year free user) = ~$0.03–$0.10
```

**Key metric:** Volume matters. 10,000 free users = $300–$1,000/yr from ads alone.

### 3.2 Affiliate-Referred User

**Revenue generated:**
- One-time CPA commission on account opening
- Possible residual trading fee commission

**LTV calculation:**
```
Conversion rate (visitor → clicks affiliate) = 2–5%
Conversion rate (click → opens account)      = 15–30%
Commission per account:                       200,000 VND

Expected value per visitor reaching partner page:
  = 0.05 × 0.25 × 200,000 = 2,500 VND (~$0.10)

For a user who DOES open account:
  LTV = 200,000 VND commission
      + potential residual = ~200,000–500,000 VND total (~$8–$20)
```

### 3.3 Premium Subscriber (Monthly)

**LTV calculation:**
```
Monthly price:          99,000 VND (~$3.90)
Expected churn rate:    15–25%/month (early-stage SaaS, no strong lock-in)
Expected avg tenure:    4–7 months (1/churn)

LTV = Monthly price × Avg tenure months
    = 99,000 × 5 months = 495,000 VND (~$19.50)

With gross margin ~90% (near-zero server cost):
    LTV (net) ≈ 445,000 VND (~$17.50)
```

### 3.4 Premium Subscriber (Annual)

**LTV calculation:**
```
Annual price:           990,000 VND (~$39)
Annual churn:           40–60% (many don't renew year 2)
Expected avg tenure:    1.5–2 years

LTV = 990,000 × 1.7 = 1,683,000 VND (~$66)
Net LTV (~90% margin) ≈ 1,515,000 VND (~$59)

Annual plan LTV is 3x higher than monthly — strong incentive to push annual.
```

### 3.5 Enterprise Customer

**Estimated LTV:**
```
Custom agent development: $200–$2,000 one-time
Ongoing subscription:     $50–$500/month
Expected tenure:          12–36 months

LTV = (monthly × 24 months) + setup
    = $200 × 24 + $500 = $5,300 average case
```

---

## 4. Unit Economics Summary

| User Type | Acquisition Cost (est.) | LTV | LTV:CAC Ratio |
|---|---|---|---|
| Free user (organic SEO) | ~$0.05–$0.20 | $0.05–$0.10 | 0.5x (needs scale) |
| Affiliate converter | ~$0.50–$2.00 | $8–$20 | 10–40x |
| Monthly subscriber | ~$2–$5 (organic) | ~$19.50 | 4–10x |
| Annual subscriber | ~$2–$5 (organic) | ~$66 | 13–33x |
| Enterprise | ~$20–$100 (BD) | $2,000–$10,000 | 20–100x |

**Key insight:** Affiliate conversions and annual subscriptions have the best LTV:CAC ratio.

---

## 5. Growth Model

### Phase 1 — Current: Free Data Platform (0–10K users/mo)
- Revenue mix: ~80% AdSense, ~20% affiliate
- Primary goal: Build organic SEO traffic
- Monthly revenue estimate: $50–$200

### Phase 2 — Growth: Premium Expansion (10K–100K users/mo)
- Revenue mix: ~40% AdSense, ~30% affiliate, ~30% subscriptions
- Monthly revenue target: $500–$3,000
- Key lever: Fintel AI Agent feature depth → convert free users

### Phase 3 — Scale: B2B + Direct Ads (100K+ users/mo)
- Revenue mix: ~30% AdSense, ~20% affiliate, ~30% subscriptions, ~20% direct ads + enterprise
- Monthly revenue target: $5,000–$20,000+
- Key lever: Enterprise data API packages, direct brand deals

---

## 6. Key Business Metrics to Track

| Metric | Definition | Target |
|---|---|---|
| MAU (Monthly Active Users) | Unique visitors/month | 10K → 100K |
| Avg Session Duration | Time on site | >3 min (indicates content value) |
| AdSense RPM | Revenue per 1,000 pageviews | $0.70+ |
| Affiliate CVR | Clicks → opened accounts | 3–5% |
| Premium Conversion Rate | Free users → paid | 1–3% |
| MRR (Monthly Recurring Revenue) | Subscription revenue | Growing MoM |
| Monthly Churn Rate | % subscribers who cancel | <15% |
| Organic Search Traffic % | SEO vs. direct vs. referral | >60% organic |
| Avg LTV | Blended across all user types | $5–$15 |

---

## 7. Cost Structure

| Cost | Monthly | Notes |
|---|---|---|
| Infrastructure (hosting, DB, CDN) | ~$0–$5 | Mostly free tiers |
| Domain | ~$1 | ~$10/year |
| AI API (Gemini) | ~$1–$10 | Crawling fallback + analysis |
| Auth0 | $0 | Free tier (<7,500 MAU) |
| PayOS / SePay | 0.5–1% per transaction | Payment processing |
| **Total COGS** | **~$5–$20/mo** | Near-zero marginal cost |

**Gross margin at scale: ~85–95%** — exceptional for a software business.

---

## 8. Risk Factors

| Risk | Impact | Mitigation |
|---|---|---|
| AdSense policy violation / rejection | Revenue loss | Content quality improvements (done) |
| Website scraping sources change HTML | Data gaps | Multi-layer fallback parsers + Gemini LLM |
| Render.com cold starts | UX degradation | Cache static JSON; migrate to paid tier when revenue justifies |
| Auth0 free tier limit (7,500 MAU) | Auth failures | Upgrade plan or migrate to self-hosted auth |
| Gold data accuracy issues | Trust loss | Source attribution + disclaimer shown |
| Affiliate program terms change | Revenue drop | Diversify to 3–4 brokers |

---

## 9. Competitive Pricing Context

| Service | Price | Data quality |
|---|---|---|
| Bloomberg Terminal | $2,000/mo | Excellent, global |
| Refinitiv Eikon | $1,500/mo | Excellent, global |
| FiinTrade (Vietnam) | ~$30–$100/mo | Good, Vietnam-focused |
| VNDirect data | Limited free + subscription | OK, Vietnam only |
| **Viet Dataverse Free** | **$0** | Good, Vietnam-focused, API-ready |
| **Viet Dataverse Pro** | **$3.90/mo** | Good + AI agents |

**Pricing power:** Viet Dataverse is positioned at the extreme value end. Potential to increase Pro pricing to $9.90–$19.90/month as product matures without losing competitiveness.
