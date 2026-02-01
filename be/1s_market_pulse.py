"""
1s Market Pulse - RSS-based News Pipeline
Crawls real RSS feeds from major international news sources,
uses Gemini AI to filter/translate articles relevant to Vietnam's financial market.
Deduplicates against existing DB entries by URL.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import re
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import google.generativeai as genai
import feedparser

# Load environment variables
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / '.env')

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY or GEMINI_API_KEY == 'your_gemini_api_key_here':
    raise ValueError("Please set GEMINI_API_KEY in .env file")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

# Database
ARGUS_FINTEL_DB = os.getenv('ARGUS_FINTEL_DB')
if not ARGUS_FINTEL_DB:
    raise ValueError("ARGUS_FINTEL_DB not found in .env file")
engine = create_engine(ARGUS_FINTEL_DB, pool_pre_ping=True)

# ==============================
# RSS FEED SOURCES
# ==============================
RSS_FEEDS = [
    {
        "name": "CNBC Top News",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"
    },
    {
        "name": "CNBC Economy",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"
    },
    {
        "name": "CNBC Finance",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"
    },
    {
        "name": "BBC Business",
        "url": "http://feeds.bbci.co.uk/news/business/rss.xml"
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.marketwatch.com/marketwatch/topstories/"
    },
]


# ==============================
# CRAWL RSS FEEDS
# ==============================
def crawl_rss_feeds(hours=24):
    """Crawl RSS feeds and return articles from the last N hours"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for feed_info in RSS_FEEDS:
        count = 0
        try:
            feed = feedparser.parse(feed_info["url"])
            for entry in feed.entries[:20]:
                # Parse published date
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                # Skip old articles
                if pub_date and pub_date < cutoff:
                    continue

                title = entry.get('title', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                link = entry.get('link', '').strip()

                if not title or not link:
                    continue

                # Clean HTML tags from summary
                summary = re.sub(r'<[^>]+>', '', summary).strip()
                summary = summary[:500]

                articles.append({
                    "title": title,
                    "summary": summary,
                    "url": link,
                    "source": feed_info["name"],
                    "published": pub_date.isoformat() if pub_date else datetime.now(timezone.utc).isoformat()
                })
                count += 1

            print(f"  {feed_info['name']}: {count} articles")
        except Exception as e:
            print(f"  {feed_info['name']}: Failed - {e}")

    return articles


# ==============================
# DEDUPLICATION
# ==============================
def get_existing_urls():
    """Get URLs already in the database to avoid duplicates"""
    with engine.connect() as conn:
        # Ensure table exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS mri_analysis (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                brief_content TEXT,
                source_name TEXT,
                source_date TEXT,
                url TEXT,
                label TEXT,
                mri INTEGER,
                generated_at TIMESTAMP,
                lang TEXT DEFAULT 'vi'
            )
        """))
        conn.commit()

        # Add lang column if missing (for existing tables)
        try:
            conn.execute(text("""
                ALTER TABLE mri_analysis ADD COLUMN IF NOT EXISTS lang TEXT DEFAULT 'vi'
            """))
            conn.commit()
        except Exception:
            pass

        # Get URLs from last 48 hours for dedup
        result = conn.execute(text("""
            SELECT DISTINCT url FROM mri_analysis
            WHERE generated_at > NOW() - INTERVAL '48 hours'
        """))
        return {row[0] for row in result.fetchall() if row[0]}


# ==============================
# GEMINI FILTERING
# ==============================
def filter_with_gemini(articles, existing_urls):
    """Use Gemini to filter and score articles for Vietnam market relevance"""

    # Remove already-seen URLs
    new_articles = [a for a in articles if a["url"] not in existing_urls]

    if not new_articles:
        print("   No new articles to process (all duplicates)")
        return []

    # Limit to 30 most recent for Gemini context window
    new_articles = new_articles[:30]

    articles_text = ""
    for i, a in enumerate(new_articles):
        articles_text += f"""[{i}] Title: {a['title']}
Summary: {a['summary']}
Source: {a['source']}
URL: {a['url']}
Published: {a['published']}
---
"""

    prompt = f"""You are a global macro financial research assistant.

From the following {len(new_articles)} real news articles, select EXACTLY 5 that are MOST LIKELY to have HIGH IMPACT on Vietnam's financial market.

Vietnam market scope:
- VN-Index / equities
- Banking system
- Gold & precious metals
- Real estate
- FX / interest rates / commodities
- Trade & geopolitics affecting ASEAN/Vietnam

ARTICLES:
{articles_text}

For EACH selected item, return:
- index: the article index number [0-{len(new_articles)-1}]
- title_vi: Vietnamese translation of the title
- summary_vi: 2-sentence Vietnamese summary focusing on impact to Vietnam market
- title_en: English title (keep original or slightly edited for clarity)
- summary_en: 2-sentence English summary focusing on impact to Vietnam market
- affected_market: one of (VNINDEX, GOLD, REAL_ESTATE, BANKING, FX)
- impact_score: number from -1.0 to 1.0 (negative = bearish, positive = bullish), absolute value >= 0.5

Return ONLY valid JSON (no markdown code blocks):

{{
  "items": [ ... exactly 5 items ... ]
}}"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Clean markdown code blocks if present
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
        if raw.endswith('```'):
            raw = raw[:-3]
        raw = raw.strip()

    data = json.loads(raw)
    items = data.get("items", [])

    if len(items) != 5:
        print(f"   Warning: Expected 5 items, got {len(items)}")

    # Merge with original article data (real URLs from RSS)
    results = []
    for item in items:
        idx = item.get("index", -1)
        if 0 <= idx < len(new_articles):
            original = new_articles[idx]
            item["url"] = original["url"]       # Always use real URL from RSS
            item["source"] = original["source"]
            item["source_date"] = original["published"]
            results.append(item)
        else:
            print(f"   Warning: Invalid index {idx}, skipping")

    return results


# ==============================
# SAVE TO DB
# ==============================
def save_items(items):
    """Save items to mri_analysis table (both VI and EN versions)"""
    now = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh"))

    insert_sql = text("""
        INSERT INTO mri_analysis
        (title, brief_content, source_name, source_date, url, label, mri, generated_at, lang)
        VALUES
        (:title, :brief, :source, :source_date, :url, :label, :mri, :generated_at, :lang)
    """)

    with engine.begin() as conn:
        for item in items:
            # Vietnamese version
            conn.execute(insert_sql, {
                "title": item["title_vi"],
                "brief": item["summary_vi"],
                "source": item["source"],
                "source_date": item["source_date"],
                "url": item["url"],
                "label": item["affected_market"],
                "mri": int(float(item["impact_score"]) * 100),
                "generated_at": now,
                "lang": "vi"
            })
            # English version
            conn.execute(insert_sql, {
                "title": item["title_en"],
                "brief": item["summary_en"],
                "source": item["source"],
                "source_date": item["source_date"],
                "url": item["url"],
                "label": item["affected_market"],
                "mri": int(float(item["impact_score"]) * 100),
                "generated_at": now,
                "lang": "en"
            })


# ==============================
# MAIN
# ==============================
def main():
    print("=" * 60)
    print("1s Market Pulse - RSS Pipeline")
    print("=" * 60)

    # Step 1: Crawl RSS feeds
    print("\n1. Crawling RSS feeds (last 24h)...")
    articles = crawl_rss_feeds(hours=24)
    print(f"   Total: {len(articles)} articles")

    if not articles:
        print("No articles found from RSS feeds")
        return False

    # Step 2: Get existing URLs for dedup
    print("\n2. Checking for duplicates...")
    existing_urls = get_existing_urls()
    new_count = len([a for a in articles if a["url"] not in existing_urls])
    print(f"   {len(existing_urls)} existing URLs, {new_count} new articles")

    if new_count == 0:
        print("   All articles already processed, skipping")
        return True

    # Step 3: Filter with Gemini
    print("\n3. Filtering with Gemini AI...")
    items = filter_with_gemini(articles, existing_urls)

    if not items:
        print("   No relevant items after filtering")
        return False

    # Step 4: Save to DB
    print(f"\n4. Saving {len(items)} items (VI + EN) to database...")
    save_items(items)

    print(f"\nMarket Pulse completed: {len(items)} items saved")
    for item in items:
        score = int(float(item['impact_score']) * 100)
        print(f"   [{item['affected_market']:>12}] (MRI:{score:+d}) {item['title_en'][:70]}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
