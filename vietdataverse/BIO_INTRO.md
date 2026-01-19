# Viet Dataverse - Project Introduction

## Short Bio (LinkedIn/Resume)

> Built **Viet Dataverse**, an open data platform providing free access to Vietnam's historical gold prices, silver prices, and central bank rates dating back to 2009. Developed a fully automated data pipeline using Python, GitHub Actions, and Selenium to crawl 6+ data sources daily, storing 33,000+ records in Neon PostgreSQL. Integrated Google Gemini AI to generate daily Vietnamese market analysis. Tech stack: FastAPI, Chart.js, SQLAlchemy, deployed on Render.com with GitHub Pages frontend.

---

## Extended Bio (Portfolio/Blog)

### Viet Dataverse: Democratizing Vietnam's Financial Data

As someone passionate about data accessibility, I noticed a significant gap in Vietnam's financial data landscape—historical gold prices, central bank rates, and market indicators were scattered across multiple sources with no unified, free access point for researchers and analysts.

**Viet Dataverse** was born from this need. It's a fully automated open data platform that:

- **Aggregates 6+ data sources** including domestic gold prices (SJC, DOJI, PNJ), silver prices, SBV interbank rates, policy rates, and global market indicators from Yahoo Finance
- **Provides 15+ years of historical data** with records dating back to August 2009
- **Runs autonomously** via GitHub Actions cron jobs, crawling fresh data every morning at 8:30 AM Vietnam time
- **Generates AI-powered analysis** using Google Gemini to provide daily market insights in Vietnamese
- **Offers free CSV downloads** for researchers and analysts who need raw data for their own analysis

### Technical Highlights

**Data Engineering:**
- Built robust web scrapers handling both static HTML (BeautifulSoup) and JavaScript-rendered pages (Selenium)
- Implemented retry logic with exponential backoff to handle rate limiting from Yahoo Finance
- Designed a multi-database architecture separating concerns: crawling data, global indicators, and AI-generated content

**Backend Development:**
- Developed RESTful APIs with FastAPI, supporting flexible query parameters for date ranges and data types
- Utilized SQLAlchemy ORM with connection pooling for efficient database operations
- Deployed on Render.com's free tier with automatic scaling

**Frontend Development:**
- Created responsive data visualizations using Chart.js with mobile-optimized touch interactions
- Implemented client-side CSV generation for instant downloads without server dependency
- Built bilingual support (Vietnamese/English) with localStorage persistence

**AI Integration:**
- Engineered prompts for Gemini 2.5 Flash to generate structured, consistent market analysis
- Automated the entire analysis pipeline: data fetching → prompt generation → AI call → database storage

**DevOps:**
- Configured GitHub Actions for daily automated execution with proper secret management
- Set up multi-environment deployments across GitHub Pages, Render.com, and Neon PostgreSQL

### Impact

The platform serves as a free resource for:
- Financial researchers studying Vietnam's gold market trends
- Data scientists needing clean, structured historical data
- Students learning about financial data analysis
- Anyone interested in tracking Vietnam's economic indicators

**All data is free to download, no registration required.**

---

## Technical Skills Demonstrated

| Category | Technologies |
|----------|--------------|
| **Languages** | Python, JavaScript, SQL, HTML/CSS |
| **Backend** | FastAPI, SQLAlchemy, Uvicorn |
| **Frontend** | Chart.js, Vanilla JS, Responsive Design |
| **Databases** | PostgreSQL (Neon), Database Design |
| **Data Engineering** | Web Scraping, ETL Pipelines, Data Cleaning |
| **AI/ML** | Prompt Engineering, Gemini AI Integration |
| **DevOps** | GitHub Actions, CI/CD, Cron Jobs |
| **Cloud** | Render.com, GitHub Pages, Neon (Serverless) |
| **Tools** | Selenium, BeautifulSoup, Pandas, yfinance |

---

## Call to Action

🔗 **Live Demo:** [hiienng.github.io/nguyenphamdieuhien.online/vietdataverse](https://hiienng.github.io/nguyenphamdieuhien.online/vietdataverse/)

📊 **Download Data:** Free CSV exports for all datasets

📖 **Source Code:** Available on GitHub

---

## One-liner Pitch

*"An automated, AI-powered open data platform delivering 15+ years of Vietnam's gold prices and economic indicators—completely free."*