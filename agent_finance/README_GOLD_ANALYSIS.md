# Gold Analysis AI Agent

## Overview
Automated gold market analysis agent powered by Google Gemini AI. Generates daily Vietnamese-language analysis of global and Vietnam gold markets, stores results in database, and displays on frontend.

## Features
- **Daily Automation**: Runs automatically via GitHub Actions at 8 AM VN time
- **AI-Powered**: Uses Google Gemini Pro model for intelligent market analysis
- **Data-Driven**: Analyzes 7 days of historical data from PostgreSQL
- **Structured Output**: Generates consistently formatted HTML analysis
- **Multi-Source**: Combines global macro data (Yahoo Finance) + Vietnam gold prices (DOJI)
- **API Integration**: Exposes REST API for frontend consumption

## Architecture

```
┌─────────────────────┐
│  GitHub Actions     │
│  (Daily 8 AM)       │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐      ┌──────────────────┐
│ gold_analysis_agent │─────>│  Neon PostgreSQL │
│     (Python)        │      │  gold_analysis   │
└──────┬──────────────┘      └──────────────────┘
       │                              │
       │ Gemini AI                    │ SQL Query
       ▼                              ▼
┌─────────────────────┐      ┌──────────────────┐
│  Google Gemini Pro  │      │   FastAPI        │
│    (Analysis)       │      │   /gold-analysis │
└─────────────────────┘      └──────┬───────────┘
                                    │
                                    ▼
                             ┌──────────────────┐
                             │   Frontend       │
                             │  Article 1       │
                             └──────────────────┘
```

## Database Schema

```sql
CREATE TABLE gold_analysis (
    date DATE PRIMARY KEY,
    generated_at TIMESTAMP NOT NULL,
    content TEXT NOT NULL,
    global_data_points INTEGER,
    vietnam_data_points INTEGER
);
```

## Files

### 1. gold_analysis_agent.py
**Purpose**: Core AI agent that generates analysis

**Key Functions**:
- `fetch_global_macro_data(days=7)`: Fetches Gold/Silver/NASDAQ from global_macro table
- `fetch_vietnam_gold_data(days=7)`: Fetches VN gold prices from vn_gold_24h_dojihn_hist
- `generate_analysis_prompt()`: Creates structured prompt for Gemini AI
- `generate_analysis()`: Calls Gemini API and returns formatted HTML
- `save_analysis_to_db()`: Stores analysis in gold_analysis table

**Output Structure**:
```html
<h3>Diễn biến thị trường vàng toàn cầu</h3>
<p>[3 sentences analyzing global market with actual data]</p>

<h3>Thị trường vàng trong nước</h3>
<p>[3 sentences analyzing Vietnam market with actual data]</p>

<h3>Dự báo tuần tới (DD/MM - DD/MM/YYYY)</h3>
<p>[3 sentences with price predictions and reasoning]</p>

<h3>Tin tức quốc tế liên quan</h3>
<ul>[5 international news source links]</ul>

<p class="disclaimer">[Investment disclaimer]</p>
```

### 2. run_daily_analysis.py
**Purpose**: Wrapper script for GitHub Actions automation

**Usage**:
```bash
cd agent_finance
python run_daily_analysis.py
```

### 3. agent_finance/back/main.py
**New Endpoint**: `GET /api/v1/gold-analysis`

**Parameters**:
- `date` (optional): Specific date in YYYY-MM-DD format
- Default: Returns latest analysis

**Response**:
```json
{
    "success": true,
    "data": {
        "date": "2026-01-13",
        "generated_at": "2026-01-13 21:30:45",
        "content": "<h3>Diễn biến thị trường...</h3>...",
        "global_data_points": 7,
        "vietnam_data_points": 7
    }
}
```

### 4. vietdataverse/index.html
**Frontend Integration**: Dynamically loads analysis on page load

**JavaScript Function**: `loadGoldAnalysis()`
- Fetches latest analysis from API
- Updates Article 1 content via innerHTML
- Updates article timestamp
- Falls back to static content on error

## Setup Instructions

### 1. Local Setup

Install dependencies:
```bash
cd agent_finance
pip install -r requirements.txt
```

Create `.env` file:
```bash
DATABASE_URL=postgresql://user:pass@host/db
GEMINI_API_KEY=your_gemini_api_key_here
```

Get Gemini API key: https://makersuite.google.com/app/apikey

### 2. Test Agent Locally

```bash
cd agent_finance
python gold_analysis_agent.py
```

Expected output:
```
============================================================
Gold Market Analysis Agent
============================================================

1. Fetching global macro data...
✅ Fetched 7 days of global data
   Latest: Gold $2677.50, NASDAQ 19,044.39

2. Fetching Vietnam gold data...
✅ Fetched 7 days of Vietnam data
   Latest: 160.0 - 160.0 triệu đồng

3. Generating analysis prompt...

4. Calling Gemini AI for analysis...
✅ Analysis generated successfully
   Length: 2345 characters

5. Saving analysis to database...
✅ Analysis saved to database for 2026-01-13

============================================================
✅ Gold Analysis Agent completed successfully
============================================================
```

### 3. GitHub Secrets Configuration

Add these secrets in repository settings:

1. `DATABASE_URL`: Neon PostgreSQL connection string
2. `GEMINI_API_KEY`: Google Gemini API key

Path: Repository → Settings → Secrets and variables → Actions → New repository secret

### 4. GitHub Actions Workflow

Already configured in `.github/workflows/daily-crawl.yml`:
- Runs daily at 8 AM VN time (1 AM UTC)
- Installs dependencies
- Runs crawl_bot.py first (data collection)
- Runs gold_analysis_agent.py second (AI analysis)
- Can be triggered manually via workflow_dispatch

## API Usage

### Get Latest Analysis
```bash
curl http://localhost:8000/api/v1/gold-analysis
```

### Get Specific Date Analysis
```bash
curl http://localhost:8000/api/v1/gold-analysis?date=2026-01-13
```

### Frontend Integration
```javascript
// Already integrated in index.html
async function loadGoldAnalysis() {
    const response = await fetch(`${API_BASE_URL}/gold-analysis`);
    const result = await response.json();
    if (result.success) {
        document.querySelector('#article-1 .article-text').innerHTML = result.data.content;
    }
}
```

## Analysis Prompt Structure

The agent generates analysis following this structure:

### Section 1: Global Market (3 sentences)
1. Gold futures price and trend
2. NASDAQ impact on gold investment sentiment
3. Silver price and correlation with gold

### Section 2: Vietnam Market (3 sentences)
1. SJC gold price today and trend
2. Bid-ask spread and market liquidity
3. Comparison with world gold price (exchange rate adjusted)

### Section 3: Next Week Forecast (3 sentences)
1. Expected trend (up/down/sideways) with specific price levels
2. Main factors supporting the trend (Fed, inflation, geopolitics)
3. Risks to watch and recommendations

### Section 4: International News
5 curated links to:
- Reuters
- Bloomberg
- CNBC
- Kitco
- Financial Times

## Gemini AI Prompt Engineering

Key prompt features:
- **Data-Driven**: Provides actual 7-day historical data
- **Structured**: Enforces exact 3-sentence format per section
- **Localized**: Generates Vietnamese output
- **Actionable**: Includes specific price predictions
- **Professional**: Uses formal market analysis tone
- **Safe**: Includes investment disclaimer

## Error Handling

- **No Data**: Falls back to static content if database empty
- **API Failure**: Logs error and keeps previous analysis
- **Rate Limiting**: Gemini API calls are infrequent (1x/day)
- **Database Errors**: Displays user-friendly error messages

## Monitoring

Check agent status:
```bash
# View latest analysis
SELECT date, generated_at, LENGTH(content) as content_length
FROM gold_analysis
ORDER BY date DESC
LIMIT 5;

# Check data freshness
SELECT MAX(date) as latest_analysis FROM gold_analysis;
```

## Current Status
- ✅ Agent created and tested
- ✅ API endpoint integrated
- ✅ Frontend dynamic loading implemented
- ✅ GitHub Actions workflow configured
- ⏳ Awaiting Gemini API key configuration in GitHub Secrets
- ⏳ Awaiting first automated run

## Future Enhancements
- Multi-language support (English analysis toggle)
- Historical analysis archive viewer
- Sentiment analysis scoring
- Prediction accuracy tracking
- Email notifications for major market moves

## Troubleshooting

### Issue: "No analysis found"
**Solution**: Run agent manually first to create initial analysis

### Issue: "Gemini API key not configured"
**Solution**: Set GEMINI_API_KEY in .env or GitHub Secrets

### Issue: Analysis content is empty
**Solution**: Check Gemini API response format, may need prompt adjustment

### Issue: Frontend shows static content
**Solution**: Check browser console, verify API endpoint is reachable

## License
Part of Viet Dataverse project - Open economic data portal