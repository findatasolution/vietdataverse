# Setup Guide: AI Gold Analysis Agent

## Quick Start

Your AI-powered gold analysis agent is now fully integrated! Follow these steps to activate it.

## Step 1: Get Gemini API Key (5 minutes)

1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated key (starts with `AIza...`)

## Step 2: Configure GitHub Secrets (2 minutes)

1. Go to your GitHub repository: https://github.com/your-username/nguyenphamdieuhien.online
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add two secrets:

**Secret 1:**
- Name: `GEMINI_API_KEY`
- Value: [Paste your Gemini API key from Step 1]

**Secret 2:**
- Name: `DATABASE_URL`
- Value: `postgresql://neondb_owner:npg_DX5hbAHqgif1@ep-autumn-meadow-a1xklzwk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`

## Step 3: Test Locally (Optional)

If you want to test before pushing:

```bash
cd agent_finance

# Update .env file with your Gemini API key
# Edit .env and replace: GEMINI_API_KEY=your_gemini_api_key_here

# Run the agent
python gold_analysis_agent.py
```

Expected output:
```
============================================================
Gold Market Analysis Agent
============================================================

1. Fetching global macro data...
✅ Fetched 7 days of global data

2. Fetching Vietnam gold data...
✅ Fetched 7 days of Vietnam data

3. Generating analysis prompt...

4. Calling Gemini AI for analysis...
✅ Analysis generated successfully

5. Saving analysis to database...
✅ Analysis saved to database

✅ Gold Analysis Agent completed successfully
```

## Step 4: Push to GitHub

```bash
git push origin main
```

## Step 5: Trigger First Run

### Option A: Wait for Automatic Run
- The agent runs automatically every day at 8 AM VN time (1 AM UTC)
- GitHub Actions workflow: `.github/workflows/daily-crawl.yml`

### Option B: Trigger Manually (Immediate)
1. Go to: https://github.com/your-username/nguyenphamdieuhien.online/actions
2. Click **Daily Data Crawl** workflow
3. Click **Run workflow** → **Run workflow**
4. Wait ~2 minutes for completion
5. Check the logs to verify success

## Step 6: Verify It Works

### Check Database
```sql
SELECT date, generated_at, LENGTH(content) as content_length
FROM gold_analysis
ORDER BY date DESC
LIMIT 1;
```

Expected result:
```
date       | generated_at        | content_length
2026-01-13 | 2026-01-13 21:30:45 | 2345
```

### Check API Endpoint
Open in browser: `https://nguyenphamdieuhien.online/api/v1/gold-analysis`

Expected response:
```json
{
    "success": true,
    "data": {
        "date": "2026-01-13",
        "generated_at": "2026-01-13 21:30:45",
        "content": "<h3>Diễn biến thị trường vàng toàn cầu</h3>...",
        "global_data_points": 7,
        "vietnam_data_points": 7
    }
}
```

### Check Frontend
Visit: https://nguyenphamdieuhien.online/vietdataverse/

- Navigate to **Flash News** → **Gold Prices Today**
- Article should display AI-generated analysis
- Check browser console for: `✅ Gold analysis loaded successfully`

## What Happens Daily

```
8:00 AM VN Time (1:00 AM UTC)
├── Step 1: crawl_bot.py runs
│   ├── Crawls gold prices from 24h.com.vn
│   ├── Crawls silver prices from giabac.vn
│   ├── Crawls SBV interbank rates from sbv.gov.vn
│   ├── Crawls bank deposit rates from ACB
│   └── Fetches global macro data from Yahoo Finance
│
└── Step 2: gold_analysis_agent.py runs
    ├── Fetches 7 days of global macro data
    ├── Fetches 7 days of Vietnam gold data
    ├── Generates AI analysis prompt
    ├── Calls Gemini Pro API
    ├── Receives structured Vietnamese analysis
    └── Stores in gold_analysis table (replaces previous day)

Frontend (anytime user visits)
├── Loads page
├── Fetches /api/v1/gold-analysis
├── Updates Article 1 content dynamically
└── Displays latest AI-generated analysis
```

## Analysis Structure

Each day's analysis contains:

### 1. Global Market Analysis (3 sentences)
- Gold futures price and trend
- NASDAQ impact on gold sentiment
- Silver price correlation

### 2. Vietnam Market Analysis (3 sentences)
- SJC gold price today
- Market liquidity and spread
- Comparison with global prices

### 3. Weekly Forecast (3 sentences)
- Expected trend with specific prices
- Key supporting factors (Fed, inflation, etc.)
- Risk factors and recommendations

### 4. International News Links (5 sources)
- Reuters
- Bloomberg
- CNBC
- Kitco
- Financial Times

### 5. Disclaimer
Investment warning in Vietnamese

## Monitoring

### View Recent Analyses
```sql
SELECT date, LENGTH(content) as length, global_data_points, vietnam_data_points
FROM gold_analysis
ORDER BY date DESC
LIMIT 5;
```

### Check GitHub Actions Logs
1. Go to: https://github.com/your-username/nguyenphamdieuhien.online/actions
2. Click latest "Daily Data Crawl" run
3. Expand "Run gold analysis agent" step
4. Verify: `✅ Gold Analysis Agent completed successfully`

### Frontend Console
Press F12 → Console tab, look for:
```
✅ Gold analysis loaded successfully
```

## Troubleshooting

### Issue: "GEMINI_API_KEY not configured"
**Solution**: Double-check GitHub Secrets configuration (Step 2)

### Issue: Analysis is empty or shows old content
**Solution**:
1. Check if agent ran successfully in GitHub Actions logs
2. Verify database has recent entry: `SELECT MAX(date) FROM gold_analysis;`
3. Check browser console for API errors

### Issue: "No analysis found" in API response
**Solution**: Agent hasn't run yet. Trigger manually (Step 5, Option B)

### Issue: Static content still showing
**Solution**:
1. Hard refresh browser (Ctrl+Shift+R)
2. Check API endpoint directly
3. Verify JavaScript console for errors

## Cost Estimation

- **Gemini API**: Free tier includes 60 requests/minute
- **Daily Usage**: 1 request/day = ~30 requests/month
- **Cost**: $0 (well within free tier)

## Security

- ✅ API keys stored in GitHub Secrets (encrypted)
- ✅ Database credentials in environment variables
- ✅ No sensitive data in frontend code
- ✅ CORS properly configured
- ✅ Rate limiting on API endpoints

## Success Checklist

- [ ] Gemini API key obtained
- [ ] GitHub Secrets configured (GEMINI_API_KEY + DATABASE_URL)
- [ ] Code pushed to GitHub
- [ ] First workflow run completed successfully
- [ ] Database contains analysis record
- [ ] API endpoint returns valid JSON
- [ ] Frontend displays AI-generated content
- [ ] Browser console shows success message

## Support

For issues or questions:
1. Check GitHub Actions logs first
2. Verify database connectivity
3. Test API endpoint directly
4. Review browser console errors

## Next Steps After Setup

1. Monitor first few days to ensure consistent quality
2. Adjust Gemini prompt if needed (in gold_analysis_agent.py)
3. Consider adding email notifications for errors
4. Implement analysis archive viewer (future enhancement)

---

**Congratulations!** Your AI gold analysis agent is ready to run automatically every day at 8 AM VN time. 🎉