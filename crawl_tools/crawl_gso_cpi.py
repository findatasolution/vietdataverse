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
# Only rewrap stdout when run as a script — as an import (e.g. this module's
# own test suite) it fights pytest's own stdout capture and crashes the
# whole session with "I/O operation on closed file" once the test run ends.
if __name__ == '__main__':
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

# nso.gov.vn serves an incomplete TLS chain (missing intermediate CA). macOS clients
# do AIA fetching so verification succeeds locally, but the GitHub Ubuntu/OpenSSL
# runner cannot and fails with CERTIFICATE_VERIFY_FAILED — which silently blocked CPI
# crawling since 2026-03. This is a public, read-only gov stats source (no credentials
# sent), so we disable TLS verification for nso.gov.vn requests only (NOT the Gemini API).
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
NSO_VERIFY = False


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
            resp = requests.get(api_url, headers=HEADERS, timeout=15, verify=NSO_VERIFY)
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


# Vietnamese ordinal month names as they appear in NSO slugs
# (tháng Tư = 'tu', not 'bon'). Shared by the URL builder and the listing
# fallback so the two cannot disagree about which month an article covers.
MONTH_SLUGS = {
    1: 'mot', 2: 'hai', 3: 'ba', 4: 'tu', 5: 'nam', 6: 'sau',
    7: 'bay', 8: 'tam', 9: 'chin', 10: 'muoi', 11: 'muoi-mot', 12: 'muoi-hai'
}


def find_article_by_window(period_year: int, period_month: int) -> "Optional[str]":
    """Find a month's CPI article by WHEN it was published, not by guessing its slug.

    NSO publishes month M's CPI report in the first half of M+1, but the slug
    wording is not stable — September 2025 is
    "…-thang-9-quy-iii-va-9-thang-nam-2025" while August is
    "…-thang-tam-va-8-thang-dau-nam-2025". construct_article_urls() guesses one
    spelling, so four months of 2025 returned 404 and were written off as
    missing even though every one of them is still online.

    Listing the posts published in the window and taking the one whose slug
    contains "chi-so-gia-tieu-dung" does not care how the month is spelled.
    """
    start = f"{period_year}-{period_month:02d}-25"
    if period_month == 12:
        end = f"{period_year + 1}-01-20"
    else:
        end = f"{period_year}-{period_month + 1:02d}-20"
    url = (f"https://www.nso.gov.vn/wp-json/wp/v2/posts"
           f"?after={start}T00:00:00&before={end}T23:59:59"
           f"&per_page=100&_fields=link,date")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=NSO_VERIFY)
        if resp.status_code != 200:
            return None
        # See crawl_gso_industry.py's find_article_by_window: a stray
        # 2019-republish hit can land inside a post-2020 window too, not just
        # before 2020, so the slug filter alone is not enough — the target
        # year must also appear in the post's own URL.
        hits = [x for x in resp.json()
                if 'chi-so-gia-tieu-dung' in x.get('link', '') and str(period_year) in x.get('link', '').rstrip('/').rsplit('/', 1)[-1]]
        if not hits:
            return None
        hits.sort(key=lambda x: x.get('date', ''))
        print(f"  Found by publication window: {hits[0]['link']}")
        return hits[0]['link']
    except Exception as e:
        print(f"  Window search error: {e}")
        return None


def construct_article_urls(period_year: int, period_month: int) -> list:
    """Best-effort fallback URLs when the WP API does not list a period."""
    pub_month = period_month + 1 if period_month < 12 else 1
    pub_year  = period_year if period_month < 12 else period_year + 1
    month_names = MONTH_SLUGS
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
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=NSO_VERIFY)
        if resp.status_code == 200:
            print(f"  Fetched {len(resp.text):,} bytes from {url}")
            return resp.text
        else:
            print(f"  HTTP {resp.status_code} for {url}")
    except Exception as e:
        print(f"  Fetch error: {e}")

    # Try listing page as fallback.
    #
    # The month must match. This used to accept any link containing
    # "chi-so-gia-tieu-dung" and the year, so when a month's own article 404'd
    # it silently returned whatever CPI article the listing happened to show —
    # a backfill of July, August, September, October and December 2025 all came
    # back with NOVEMBER's article and stored five identical rows
    # (m/m 0.23, y/y 3.29). Wrong data is worse than a gap.
    try:
        listing = f"https://www.nso.gov.vn/tin-tuc-thong-ke/{PERIOD_YEAR}/"
        resp = requests.get(listing, headers=HEADERS, timeout=15, verify=NSO_VERIFY)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            month_slug = MONTH_SLUGS.get(PERIOD_MONTH)
            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'chi-so-gia-tieu-dung' not in href or str(PERIOD_YEAR) not in href:
                    continue
                # '-thang-muoi-' is a prefix of '-thang-muoi-mot-', so month 10
                # matched November's article. NSO slugs always read
                # '-thang-{slug}-va-{N}-thang-…', so anchor on the '-va-' too.
                if not month_slug or f'-thang-{month_slug}-va-' not in href:
                    continue
                print(f"  Found via listing: {href}")
                r2 = requests.get(href, headers=HEADERS, timeout=20, verify=NSO_VERIFY)
                if r2.status_code == 200:
                    return r2.text
            print(f"  Listing has no article for month {PERIOD_MONTH} — giving up rather "
                  f"than using another month's figures")
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

    # Real bug, found 2026-09 (2026-07 and 2026-08 both stored cpi_yoy_pct
    # 4.45% — different months, same wrong number; separately confirmed
    # gold_mom_pct/usd_mom_pct also silently wrong on other periods).
    #
    # Two things had to both be fixed, and fixing only one at a time kept
    # reintroducing the other bug (tried and reverted: joining adjacent
    # lines — NSO fragments one sentence into anywhere from 2 to 5+ short
    # lines depending on the bulletin, so no fixed join depth is reliable;
    # a bounded character window after each anchor occurrence — "cpi"/
    # "tiêu dùng"/"vàng" are common enough words that an unrelated nearby
    # "%" occasionally won the match):
    #
    # 1. get_text(separator='\n') puts NSO's bolded subheading on its own
    #    line, separate from the sentence with the actual figures — so any
    #    pattern requiring the anchor and the number on the same line fails,
    #    and falls through to a later occurrence of the anchor word instead
    #    (which is how "CPI" inside "Bình quân tám tháng…, CPI tăng 4,45%…"
    #    got matched instead of the month's own 4,89%).
    # 2. The page's own title lists all three indices together ("...tiêu
    #    dùng (CPI), chỉ số giá vàng và chỉ số giá đô la Mỹ..."), so once \n
    #    boundaries are removed to fix (1), a loose anchor like "vàng" can
    #    run forward from the title straight into CPI's own figure instead
    #    of gold's.
    #
    # Fix: anchor on "<subject> (CPI) tháng" / "giá vàng tháng" / "giá đô la
    # (mỹ) tháng" instead of the bare subject word — every real content
    # sentence starts this way ("chỉ số giá tiêu dùng (CPI) tháng Tám tăng…"
    # / "giá vàng tháng Tám giảm…"). This isn't quite enough on its own,
    # though: the combined title's OWN closing clause is "...và chỉ số giá
    # đô la Mỹ tháng Tám và 8 tháng năm 2026" — literally "đô la Mỹ tháng
    # Tám", matching usd_mom_pct's anchor too. So the title line is also
    # dropped outright (it's the only line naming all three indices
    # together; genuine content sentences only ever discuss one). Both
    # steps combined make the anchor specific enough to flatten the WHOLE
    # remaining document safely: no more line-boundary fragility, and no
    # more cross-section contamination from the title.
    content_lines = [
        l for l in text_content.split('\n')
        if not ('tiêu dùng' in l.lower() and 'vàng' in l.lower()
                 and 'đô la' in l.lower())
    ]
    flat = re.sub(r'\s+', ' ', ' '.join(content_lines))
    YTD_MARKERS = ('bình quân', 'tính chung')
    text_lower = '. '.join(
        s for s in flat.split('.')
        if not any(m in s.lower() for m in YTD_MARKERS)
    ).lower()

    patterns = {
        'cpi_mom_pct': [
            r'tiêu dùng\s*\(cpi\)\s*tháng[^.]*?(tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
        ],
        'cpi_yoy_pct': [
            # Wider than the other patterns' [^.]*? on purpose: yoy% is
            # sometimes in the SAME sentence as mom% ("...4,89% so với
            # cùng kỳ năm trước." — August's bulletin), sometimes in a
            # second sentence after it ("...so với tháng trước [...]. CPI
            # tháng Năm [...] tăng 3,24% so với cùng kỳ năm trước." — May
            # 2025's; a single-sentence bound missed this and is the
            # confirmed root cause of that period's wrong stored value).
            # 300 chars comfortably covers both without reaching the next
            # index's heading (already isolated by the anchor + YTD-drop
            # above, so nothing else nearby says "so với cùng kỳ").
            r'tiêu dùng\s*\(cpi\)\s*tháng.{0,300}?(tăng|giảm)\s+([\d,\.]+)%\s*so với cùng kỳ',
            # NSO sometimes leads with the comparison instead of the subject:
            # "So với cùng kỳ năm trước, CPI tháng Mười Hai tăng 3,48%."
            r'so với cùng kỳ năm trước,\s*cpi[^.]*?(tăng|giảm)\s+([\d,\.]+)%',
        ],
        'gold_mom_pct': [
            r'giá vàng\s*tháng[^.]*?(tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
        ],
        'usd_mom_pct': [
            r'giá đô la(?:\s*mỹ)?\s*tháng[^.]*?(tăng|giảm)\s+([\d,\.]+)%\s*so với tháng trước',
        ],
    }

    for field, pats in patterns.items():
        for pat in pats:
            m = re.search(pat, text_lower, re.IGNORECASE)
            if m:
                # The direction word is captured immediately before the
                # number, not inferred from the whole matched span — a
                # sentence can mix directions ("giảm 0,12% so với tháng
                # trước; … tăng 4,45% so với cùng kỳ") and scanning the span
                # for "giảm" would misattribute one field's sign to another.
                direction, raw = m.group(1), m.group(2)
                val = float(raw.replace(',', '.'))
                if direction == 'giảm':
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

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
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
            # raise_for_status() embeds the full request URL (incl. ?key=API_KEY) in the
            # message — mask it so the Gemini key never leaks into CI logs.
            msg = str(e).replace(GEMINI_API_KEY, '***') if GEMINI_API_KEY else str(e)
            print(f"  [Gemini] Attempt {attempt+1} error: {msg}")
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
    # Publication-window lookup before the guessed slugs: it survives NSO
    # renaming its months, which the guesses do not.
    by_window = find_article_by_window(period_year, period_month)
    if by_window and by_window not in candidates:
        candidates.append(by_window)
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
