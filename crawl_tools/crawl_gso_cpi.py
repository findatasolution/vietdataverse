"""
Vietnam CPI / Gold Index / USD Index Monthly Crawler
Source: nso.gov.vn (Tổng cục Thống kê)
Strategy: Discover latest article URL → fetch HTML → Gemini extract
Table: vn_gso_cpi_monthly — 1 row per month

Sample data extracted:
  CPI tháng 02/2026: +1.14% mom
  Giá vàng tháng 02/2026: +11.42% mom
  Đô la Mỹ tháng 02/2026: -0.89% mom

Schedule: Monthly 7th–9th at 09:00 VN (02:00 UTC)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import re
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from bs4 import BeautifulSoup

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

current_date = datetime.now()
# Crawl for previous month (article published on ~7th of next month)
if current_date.month == 1:
    PERIOD_YEAR, PERIOD_MONTH = current_date.year - 1, 12
else:
    PERIOD_YEAR, PERIOD_MONTH = current_date.year, current_date.month - 1
PERIOD = f"{PERIOD_YEAR:04d}-{PERIOD_MONTH:02d}"

print(f"\n{'='*60}")
print(f"NSO CPI Crawler — Period: {PERIOD} — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    raise ValueError("CRAWLING_BOT_DB environment variable not set")
engine = create_engine(CRAWLING_BOT_DB)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept-Language': 'vi-VN,vi;q=0.9',
}


# ─────────────────────────────────────────────────────────────
# DB SETUP — 1 row per month
# ─────────────────────────────────────────────────────────────
def ensure_table():
    with engine.connect() as conn:
        # Drop old multi-row-per-month table if still exists
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'vn_gso_cpi_monthly' AND column_name = 'category'
                ) THEN
                    DROP TABLE vn_gso_cpi_monthly CASCADE;
                END IF;
            END $$;
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_gso_cpi_monthly (
                id          SERIAL PRIMARY KEY,
                period      VARCHAR(7) NOT NULL UNIQUE,   -- YYYY-MM (period of data)
                -- CPI
                cpi_mom_pct FLOAT,   -- % so với tháng trước
                cpi_yoy_pct FLOAT,   -- % so với cùng kỳ năm trước
                cpi_ytd_pct FLOAT,   -- % bình quân từ đầu năm
                -- Chỉ số giá vàng
                gold_mom_pct FLOAT,
                gold_yoy_pct FLOAT,
                gold_ytd_pct FLOAT,
                -- Chỉ số giá USD
                usd_mom_pct  FLOAT,
                usd_yoy_pct  FLOAT,
                usd_ytd_pct  FLOAT,
                -- Metadata
                source      TEXT NOT NULL DEFAULT 'nso.gov.vn',
                crawl_time  TIMESTAMP NOT NULL,
                group_name  VARCHAR(20) NOT NULL DEFAULT 'macro'
            )
        """))
        # Migrate existing table: rename source_url → source, add group_name
        try:
            conn.execute(text("ALTER TABLE vn_gso_cpi_monthly RENAME COLUMN source_url TO source"))
            conn.commit()
        except Exception:
            conn.rollback()  # column already renamed or doesn't exist
        for col, definition in [
            ('source',     "TEXT NOT NULL DEFAULT 'nso.gov.vn'"),
            ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'macro'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn_gso_cpi_monthly ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.commit()
    print("Table vn_gso_cpi_monthly ready (1 row/month schema).")


# ─────────────────────────────────────────────────────────────
# URL DISCOVERY — find latest CPI article on nso.gov.vn
# ─────────────────────────────────────────────────────────────
def _period_from_pubdate(pub_iso: str) -> str:
    """An article published in early month M reports data for month M-1."""
    y, m = int(pub_iso[:4]), int(pub_iso[5:7])
    pm = m - 1 if m > 1 else 12
    py = y if m > 1 else y - 1
    return f"{py:04d}-{pm:02d}"


def discover_articles_by_period() -> dict:
    """
    Map {'YYYY-MM': article_url} for every CPI article the WP API exposes.
    NSO alternates the URL section between /tin-tuc-thong-ke/ and
    /du-lieu-va-so-lieu-thong-ke/, so we never construct URLs blindly — we read
    the published list and key each article by its data period (pub_month - 1).
    """
    found = {}
    search_terms = [
        "chi so gia tieu dung",
        "chỉ số giá tiêu dùng chỉ số giá vàng",
    ]
    for term in search_terms:
        try:
            api_url = (f"https://www.nso.gov.vn/wp-json/wp/v2/posts"
                       f"?search={requests.utils.quote(term)}&per_page=30&_fields=link,date")
            resp = requests.get(api_url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                for post in resp.json():
                    link = post.get('link', '')
                    date = post.get('date', '')
                    if 'chi-so-gia-tieu-dung' in link.lower() and len(date) >= 7:
                        found.setdefault(_period_from_pubdate(date), link)
        except Exception as e:
            print(f"  WP API search error: {e}")
    print(f"  Discovered {len(found)} CPI article(s): {sorted(found)}")
    return found


def construct_article_urls(period_year: int, period_month: int) -> list:
    """Best-effort fallback URLs when the WP API does not list a period."""
    pub_month = period_month + 1 if period_month < 12 else 1
    pub_year  = period_year if period_month < 12 else period_year + 1
    # Vietnamese ordinal month names as used in NSO slugs (tháng Tư = 'tu', not 'bon')
    month_names = {
        1:'mot', 2:'hai', 3:'ba', 4:'tu', 5:'nam', 6:'sau',
        7:'bay', 8:'tam', 9:'chin', 10:'muoi', 11:'muoi-mot', 12:'muoi-hai'
    }
    slug = (f"chi-so-gia-tieu-dung-chi-so-gia-vang-va-chi-so-gia-do-la-my"
            f"-thang-{month_names[period_month]}-va-{period_month}-thang-dau-nam-{period_year}")
    return [
        f"https://www.nso.gov.vn/{base}/{pub_year}/{pub_month:02d}/{slug}/"
        for base in ('tin-tuc-thong-ke', 'du-lieu-va-so-lieu-thong-ke')
    ]


# ─────────────────────────────────────────────────────────────
# FETCH HTML
# ─────────────────────────────────────────────────────────────
def fetch_article_html(url: str) -> str:
    """Fetch article HTML from nso.gov.vn."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            print(f"  Fetched {len(resp.text):,} bytes from {url}")
            return resp.text
        else:
            print(f"  HTTP {resp.status_code} for {url}")
    except Exception as e:
        print(f"  Fetch error: {e}")

    # Try listing page as fallback
    try:
        listing = f"https://www.nso.gov.vn/tin-tuc-thong-ke/{PERIOD_YEAR}/"
        resp = requests.get(listing, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'chi-so-gia-tieu-dung' in href and str(PERIOD_YEAR) in href:
                    print(f"  Found via listing: {href}")
                    r2 = requests.get(href, headers=HEADERS, timeout=20)
                    if r2.status_code == 200:
                        return r2.text
    except Exception as e:
        print(f"  Listing fetch error: {e}")

    return None


# ─────────────────────────────────────────────────────────────
# LAYER 1: Structured Parse — look for known patterns in text
# ─────────────────────────────────────────────────────────────
def layer1_structured(text_content: str, period: str) -> dict:
    """
    Extract CPI/Gold/USD mom% directly from text using regex.
    Example: "CPI tháng 02/2026 tăng 1,14% so với tháng trước"
    """
    result = {}
    text_lower = text_content.lower()

    patterns = {
        # CPI mom
        'cpi_mom_pct': [
            r'(?:cpi|chỉ số giá tiêu dùng)[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
            r'(?:tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước[^\n]*?(?:cpi|tiêu dùng)',
        ],
        # CPI yoy
        'cpi_yoy_pct': [
            r'(?:cpi|tiêu dùng)[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%\s*so với cùng kỳ',
        ],
        # Gold mom
        'gold_mom_pct': [
            r'(?:giá vàng|vàng)[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
            r'chỉ số giá vàng[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%',
        ],
        # USD mom
        'usd_mom_pct': [
            r'(?:đô la|đô la mỹ|usd)[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
            r'chỉ số giá đô la[^\n]*?(?:tăng|giảm)\s+([\d,\.]+)%',
        ],
    }

    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text_lower, re.IGNORECASE)
            if m:
                val = float(m.group(1).replace(',', '.'))
                # Detect sign
                context = text_lower[max(0, m.start()-20):m.end()]
                if 'giảm' in context:
                    val = -val
                result[field] = val
                break

    return result


# ─────────────────────────────────────────────────────────────
# LAYER 2: Gemini Parse — primary extraction method
# ─────────────────────────────────────────────────────────────
def layer2_gemini(text_content: str) -> dict:
    """Use Gemini to extract CPI/Gold/USD index changes from article text."""
    if not GEMINI_API_KEY:
        print("  [Gemini] GEMINI_API_KEY not set, skipping.")
        return {}

    # Extract readable text, trim to 5000 chars
    clean_text = text_content[:5000]

    prompt = f"""Bạn là trợ lý phân tích dữ liệu thống kê Việt Nam.
Từ bài viết NSO dưới đây, trích xuất dữ liệu cho kỳ {PERIOD}:

Trả về JSON object với các trường sau (dùng null nếu không tìm thấy):
{{
  "cpi_mom_pct": <% thay đổi CPI so với tháng trước, dương=tăng, âm=giảm>,
  "cpi_yoy_pct": <% thay đổi CPI so với cùng kỳ năm trước>,
  "cpi_ytd_pct": <% bình quân CPI từ đầu năm so với cùng kỳ năm trước>,
  "gold_mom_pct": <% thay đổi chỉ số giá vàng so với tháng trước>,
  "gold_yoy_pct": <% thay đổi chỉ số giá vàng so với cùng kỳ năm trước>,
  "gold_ytd_pct": <% bình quân chỉ số giá vàng từ đầu năm>,
  "usd_mom_pct":  <% thay đổi chỉ số giá USD so với tháng trước>,
  "usd_yoy_pct":  <% thay đổi chỉ số giá USD so với cùng kỳ năm trước>,
  "usd_ytd_pct":  <% bình quân chỉ số giá USD từ đầu năm>
}}

Lưu ý: giảm → âm (ví dụ: giảm 0.89% → -0.89), tăng → dương.
Chỉ trả về JSON, không có text khác.

Bài viết:
{clean_text}"""

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    for attempt in range(3):
        try:
            if attempt > 0:
                import time; time.sleep(15 * attempt)
                print(f"  [Gemini] Retry {attempt}...")
            resp = requests.post(api_url, json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 512}
            }, timeout=30)
            resp.raise_for_status()
            raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
            raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
            data = json.loads(raw)
            print(f"  [Gemini] Extracted: CPI mom={data.get('cpi_mom_pct')}, Gold={data.get('gold_mom_pct')}, USD={data.get('usd_mom_pct')}")
            return data
        except Exception as e:
            print(f"  [Gemini] Attempt {attempt+1} error: {e}")
    return {}


# ─────────────────────────────────────────────────────────────
# UPSERT
# ─────────────────────────────────────────────────────────────
def upsert_record(data: dict, period: str, source: str, crawl_time: datetime):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn_gso_cpi_monthly
                (period, cpi_mom_pct, cpi_yoy_pct, cpi_ytd_pct,
                 gold_mom_pct, gold_yoy_pct, gold_ytd_pct,
                 usd_mom_pct, usd_yoy_pct, usd_ytd_pct,
                 source, crawl_time, group_name)
            VALUES
                (:period, :cpi_mom_pct, :cpi_yoy_pct, :cpi_ytd_pct,
                 :gold_mom_pct, :gold_yoy_pct, :gold_ytd_pct,
                 :usd_mom_pct, :usd_yoy_pct, :usd_ytd_pct,
                 :source, :crawl_time, :group_name)
            ON CONFLICT (period) DO UPDATE SET
                cpi_mom_pct  = EXCLUDED.cpi_mom_pct,
                cpi_yoy_pct  = EXCLUDED.cpi_yoy_pct,
                cpi_ytd_pct  = EXCLUDED.cpi_ytd_pct,
                gold_mom_pct = EXCLUDED.gold_mom_pct,
                gold_yoy_pct = EXCLUDED.gold_yoy_pct,
                gold_ytd_pct = EXCLUDED.gold_ytd_pct,
                usd_mom_pct  = EXCLUDED.usd_mom_pct,
                usd_yoy_pct  = EXCLUDED.usd_yoy_pct,
                usd_ytd_pct  = EXCLUDED.usd_ytd_pct,
                source       = EXCLUDED.source,
                crawl_time   = EXCLUDED.crawl_time,
                group_name   = EXCLUDED.group_name
        """), {
            'period': period,
            'cpi_mom_pct':  data.get('cpi_mom_pct'),
            'cpi_yoy_pct':  data.get('cpi_yoy_pct'),
            'cpi_ytd_pct':  data.get('cpi_ytd_pct'),
            'gold_mom_pct': data.get('gold_mom_pct'),
            'gold_yoy_pct': data.get('gold_yoy_pct'),
            'gold_ytd_pct': data.get('gold_ytd_pct'),
            'usd_mom_pct':  data.get('usd_mom_pct'),
            'usd_yoy_pct':  data.get('usd_yoy_pct'),
            'usd_ytd_pct':  data.get('usd_ytd_pct'),
            'source': source,
            'crawl_time': crawl_time,
            'group_name': 'macro',
        })
        conn.commit()
    print(f"  Upserted 1 row for period {period}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def crawl_period(period_year: int, period_month: int, articles: dict) -> bool:
    """Fetch + extract + upsert one month. Returns True on success."""
    global PERIOD, PERIOD_YEAR, PERIOD_MONTH
    PERIOD_YEAR, PERIOD_MONTH = period_year, period_month
    PERIOD = f"{period_year:04d}-{period_month:02d}"
    print(f"\n--- Period {PERIOD} ---")

    candidates = []
    if articles.get(PERIOD):
        candidates.append(articles[PERIOD])
    candidates += construct_article_urls(period_year, period_month)

    html, used_url = None, None
    for url in candidates:
        html = fetch_article_html(url)
        if html:
            used_url = url
            break
    if not html:
        print(f"  ERROR: could not fetch article for {PERIOD}")
        return False

    soup = BeautifulSoup(html, 'html.parser')
    article = soup.find('article') or soup.find('div', class_=re.compile(r'post|content|entry'))
    text_content = (article or soup).get_text(separator='\n', strip=True)

    data = layer1_structured(text_content, PERIOD)
    gemini_data = layer2_gemini(text_content)
    merged = {**data, **{k: v for k, v in gemini_data.items() if v is not None}}
    if not merged:
        print(f"  ERROR: no data extracted for {PERIOD}")
        return False

    print(f"  CPI mom={merged.get('cpi_mom_pct')}% yoy={merged.get('cpi_yoy_pct')}% | "
          f"Gold mom={merged.get('gold_mom_pct')}% | USD mom={merged.get('usd_mom_pct')}%")
    upsert_record(merged, PERIOD, used_url, datetime.now())
    return True


def _latest_period_in_db():
    """Return 'YYYY-MM' of the newest row already stored, or None."""
    try:
        with engine.connect() as conn:
            return conn.execute(text("SELECT MAX(period) FROM vn_gso_cpi_monthly")).scalar()
    except Exception as e:
        print(f"  DB read error (treating as empty): {e}")
        return None


def _missing_periods(last_period: str, target_year: int, target_month: int, cap: int = 18):
    """Months strictly after last_period, up to and including the target."""
    target = f"{target_year:04d}-{target_month:02d}"
    if not last_period or last_period >= target:
        return [(target_year, target_month)]  # nothing missing → just refresh target
    y, m = int(last_period[:4]), int(last_period[5:7])
    out = []
    while len(out) < cap:
        m += 1
        if m > 12:
            m, y = 1, y + 1
        out.append((y, m))
        if f"{y:04d}-{m:02d}" == target:
            break
    return out


def main():
    ensure_table()
    # Target = latest published month = previous calendar month (computed at top).
    target_year, target_month = PERIOD_YEAR, PERIOD_MONTH
    articles = discover_articles_by_period()

    last = _latest_period_in_db()
    plan = _missing_periods(last, target_year, target_month)
    print(f"\nLatest in DB: {last} | Target: {target_year:04d}-{target_month:02d} | "
          f"Backfill plan: {[f'{y}-{m:02d}' for y, m in plan]}")

    results = {}
    for y, m in plan:
        results[(y, m)] = crawl_period(y, m, articles)

    ok = [f"{y}-{m:02d}" for (y, m), r in results.items() if r]
    failed = [f"{y}-{m:02d}" for (y, m), r in results.items() if not r]
    print(f"\n{'='*60}")
    print(f"NSO CPI Crawler done. OK: {ok or '—'} | Failed: {failed or '—'}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    # Fail loudly if the newest expected month did not land, so staleness is visible.
    if not results.get((target_year, target_month), False):
        print(f"❌ Target {target_year:04d}-{target_month:02d} not stored — exiting non-zero")
        sys.exit(1)


if __name__ == '__main__':
    main()
