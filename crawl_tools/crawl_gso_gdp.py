"""
Vietnam GDP Quarterly Crawler
Source: nso.gov.vn (Tổng cục Thống kê)
Strategy: 3-layer adaptive parsing — Structured → Heuristic → LLM (Gemini)
Schedule: Quarterly — end of Mar, Jun, Sep, Dec (02:00 UTC)
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
# Current quarter
current_quarter = (current_date.month - 1) // 3 + 1
# Previous quarter (the one we're reporting on)
if current_quarter == 1:
    TARGET_YEAR = current_date.year - 1
    TARGET_QUARTER = 4
else:
    TARGET_YEAR = current_date.year
    TARGET_QUARTER = current_quarter - 1

print(f"\n{'='*60}")
print(f"GSO GDP Crawler — {TARGET_YEAR}Q{TARGET_QUARTER} — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    raise ValueError("CRAWLING_BOT_DB environment variable not set")
engine = create_engine(CRAWLING_BOT_DB)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

GSO_GDP_SEARCH = "https://www.nso.gov.vn/wp-json/wp/v2/posts?search=t%E1%BB%95ng+s%E1%BA%A3n+ph%E1%BA%A9m+trong+n%C6%B0%E1%BB%9Bc&per_page=5"

GDP_SECTORS = {
    'Tổng số': 'total',
    'Nông, lâm nghiệp và thủy sản': 'agriculture',
    'Công nghiệp và xây dựng': 'industry',
    'Dịch vụ': 'services',
    'Thuế sản phẩm trừ trợ cấp sản phẩm': 'taxes_subsidies',
}


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_gso_gdp_quarterly (
                id SERIAL PRIMARY KEY,
                year INTEGER NOT NULL,
                quarter INTEGER NOT NULL,
                sector VARCHAR(50) NOT NULL,
                gdp_billion_vnd FLOAT,
                growth_yoy_pct FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'nso.gov.vn',
                UNIQUE (year, quarter, sector)
            )
        """))
        # ALTER for tables created before the source column existed — NSO
        # requires attribution ("ghi rõ nguồn ... www.nso.gov.vn") when its
        # published data is reused; this was missing on this table.
        conn.execute(text(
            "ALTER TABLE vn_gso_gdp_quarterly ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'nso.gov.vn'"
        ))
        conn.commit()
    print("Table vn_gso_gdp_quarterly ready.")


def _safe_float(s) -> "Optional[float]":
    try:
        if s is None:
            return None
        return float(str(s).replace(',', '.').replace('%', '').strip())
    except (ValueError, TypeError):
        return None


ROMAN_QUARTER = {1: 'I', 2: 'II', 3: 'III', 4: 'IV'}

# Sector breakdown always follows the headline total, in this fixed order,
# each as "khu vực <name> tăng/giảm N%". Matched only inside the window right
# after the total figure (see layer1_structured) so a same-named phrase
# elsewhere in the bulletin (e.g. a year-to-date recap later in the article)
# can't be picked up instead.
GDP_SECTOR_PATTERNS = (
    ('agriculture', r'nông,?\s*lâm nghiệp và thủy sản\s+(t[ăa]ng|gi[ảa]m)\s+([\d]+(?:[,\.]\d+)?)%'),
    ('industry', r'công nghiệp và xây dựng\s+(t[ăa]ng|gi[ảa]m)\s+([\d]+(?:[,\.]\d+)?)%'),
    ('services', r'dịch vụ\s+(t[ăa]ng|gi[ảa]m)\s+([\d]+(?:[,\.]\d+)?)%'),
)


def _signed_pct(sign_word: str, num_str: str) -> "Optional[float]":
    sign = -1 if sign_word.lower() == 'giảm' else 1
    val = _safe_float(num_str)
    return None if val is None else sign * val


def layer1_structured(html: str, year: int, quarter: int) -> list[dict]:
    """Parse GDP from prose text — NSO's quarterly bulletin never puts this
    figure in a <table> (verified 2020Q1/2022Q3/2023Q2/2026Q1, all 0 matches
    with the table parser this replaced); every quarter was silently falling
    through to the rate-limited Gemini layer, which is how a wrong LLM-guessed
    industry figure (1.56%, actual source text says 1.13%) reached
    vn_gso_gdp_quarterly for 2023Q2 undetected — nothing had verified anything
    but the headline total.

    The bulletin always opens its GDP paragraph with the fixed phrase
    "Tổng sản phẩm trong nước (GDP) quý X/YYYY ước tính tăng N% so với cùng kỳ
    năm trước", so the total is anchored on the literal "quý {roman}/{year}"
    token. Sector growth (agriculture/industry/services) is searched for only
    in the text immediately following that anchor — never guessed, and left
    absent (not a record) if a sector isn't found there, rather than reusing
    a number from elsewhere in the bulletin.
    """
    text = re.sub(r'\s+', ' ', BeautifulSoup(html, 'html.parser').get_text(' ', strip=True))
    roman = ROMAN_QUARTER[quarter]

    anchor = re.search(r'quý\s+' + re.escape(roman) + r'/' + str(year), text, re.IGNORECASE)
    if not anchor:
        return []

    # The headline sentence isn't always "tăng N%" back to back — NSO
    # sometimes inserts a qualifier ("tăng khá cao ở mức 13,67%", 2022Q3),
    # which broke an earlier version requiring tăng/giảm immediately before
    # the number and made it grab an unrelated later figure ("tiêu dùng cuối
    # cùng tăng 10,08%", a GDP-by-expenditure sub-line) instead. The number
    # sitting between the quarter anchor and the sentence's own first "so với
    # cùng kỳ" is always exactly the headline growth rate, regardless of
    # what qualifier words sit between "tăng"/"giảm" and the digits.
    head = text[anchor.end():anchor.end() + 250]
    cmp_idx = head.lower().find('so với cùng kỳ')
    if cmp_idx < 0:
        return []
    segment = head[:cmp_idx]
    num_m = re.search(r'([\d]+(?:[,\.]\d+)?)%', segment)
    if not num_m:
        return []
    sign = -1 if 'giảm' in segment[:num_m.start()].lower() else 1
    total_yoy = sign * _safe_float(num_m.group(1))
    records = [{'year': year, 'quarter': quarter, 'sector': 'total',
                'gdp_billion_vnd': None, 'growth_yoy_pct': total_yoy}]

    window = text[anchor.end() + cmp_idx:anchor.end() + cmp_idx + 500]
    for sector, pattern in GDP_SECTOR_PATTERNS:
        sm = re.search(pattern, window, re.IGNORECASE)
        if sm:
            records.append({'year': year, 'quarter': quarter, 'sector': sector,
                             'gdp_billion_vnd': None,
                             'growth_yoy_pct': _signed_pct(sm.group(1), sm.group(2))})
    return records


def layer3_llm(html: str, year: int, quarter: int) -> list[dict]:
    if not GEMINI_API_KEY:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    # The bulletin body runs ~16k characters and the figures sit well past the
    # 6,000-character mark this used to cut at, so the extractor was reading
    # only the opening summary. `content.rendered` is body-only, so passing it
    # whole costs a few thousand tokens and no noise.
    text_content = soup.get_text(separator='\n', strip=True)[:20000]
    prompt = f"""Extract Vietnam GDP data for {year} Q{quarter} from this GSO text.
Return JSON array: [{{year, quarter, sector, gdp_billion_vnd, growth_yoy_pct}}]
Sectors: total, agriculture, industry, services, taxes_subsidies
Only JSON, nothing else.

Text:
{text_content}"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.1,
                                                             "thinkingConfig": {"thinkingBudget": 0}}}, timeout=30)
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  [LLM] Error: {e}")
        return []


# NSO publishes its statistics inside the monthly socio-economic bulletin, whose
# slug always starts with this. Free-text search alone returns the newsroom —
# a piece about a deputy director's site visit outranked the actual report —
# so hits are filtered by slug the way crawl_gso_cpi.py already does.
# GDP is a QUARTERLY figure: it is absent from the monthly bulletin and appears
# in the quarter-closing report, whose slug carries the quarter in Roman
# numerals (…-quy-ii-va-6-thang-dau-nam-2026).
REPORT_SLUG_ANY = ('tinh-hinh-kinh-te-xa-hoi-quy-', 'bao-cao-tinh-hinh-kinh-te-xa-hoi')
REPORT_SEARCH = ("https://www.nso.gov.vn/wp-json/wp/v2/posts?search="
                 + requests.utils.quote("tổng sản phẩm trong nước quý")
                 + "&per_page=30&_fields=link,date,title,content")



def find_article_by_window(year: int, quarter: int) -> "Optional[str]":
    """Find the bulletin closing quarter Q by WHEN NSO published it, not by
    assuming fetch_gso_html() will always be called for the CURRENT quarter.

    Verified reliable back to 2020-01 (spot-checked against several years);
    posts before that share bulk-republish timestamps from a 2019 site
    migration that do not reflect their actual reporting period, so a window
    search there can silently match the wrong year. Not used before 2020.
    """
    end_month = quarter * 3
    start = f"{year}-{end_month:02d}-25"
    ny, nm = (year + 1, 1) if end_month == 12 else (year, end_month + 1)
    end = f"{ny}-{nm:02d}-20"
    url = (f"https://www.nso.gov.vn/wp-json/wp/v2/posts"
           f"?after={start}T00:00:00&before={end}T23:59:59"
           f"&per_page=100&_fields=link,date,content,title")
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        if resp.status_code != 200:
            return None
        # See crawl_gso_industry.py's find_article_by_window: a stray
        # 2019-republish hit can land inside a post-2020 window too, not just
        # before 2020, so the slug filter alone is not enough — the target
        # year must also appear in the post's own URL.
        posts = [p for p in resp.json()
                 if any(sl in p.get('link', '') for sl in REPORT_SLUG_ANY)
                 and str(year) in p.get('link', '').rstrip('/').rsplit('/', 1)[-1]]
        if not posts:
            return None
        posts.sort(key=lambda p: p.get('date', ''))
        quarterly = [p for p in posts if 'tinh-hinh-kinh-te-xa-hoi-quy-' in p.get('link', '')]
        best = (quarterly or posts)[0]
        print(f"  Found by window: {best['link']}")
        return best
    except Exception as e:
        print(f"  Window search error: {e}")
        return None


def fetch_gso_html(search_url: str = "", keywords=None) -> "Optional[str]":
    """Return the BODY html of the newest NSO monthly bulletin.

    Three separate faults kept this table empty since it was created:
      - it pointed at gso.gov.vn, a domain that stopped resolving when the
        office rebranded to nso.gov.vn (the CPI crawler was already migrated);
      - it fetched the article's full page, so the first 6,000 characters handed
        to the extractor were the site menu and stylesheet, not the report —
        `content.rendered` from the API is the body alone;
      - it took posts[0] from a free-text search, which returns newsroom items.
    
    GDP additionally needs a quarter-closing bulletin — see below.
    """
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi-VN,vi;q=0.9'}
    try:
        resp = requests.get(REPORT_SEARCH, headers=headers, timeout=25)
        if resp.status_code != 200:
            print(f"  Search HTTP {resp.status_code}")
            return None
        posts = [p for p in resp.json()
                 if any(sl in p.get('link', '') for sl in REPORT_SLUG_ANY)]
        if not posts:
            print("  No bulletin matched the report slug")
            return None
        posts.sort(key=lambda p: p.get('date', ''), reverse=True)
        # Prefer a genuine quarterly report over a monthly bulletin.
        quarterly = [p for p in posts if 'tinh-hinh-kinh-te-xa-hoi-quy-' in p.get('link', '')]
        best = (quarterly or posts)[0]
        print(f"  Article: {best.get('date','?')[:10]} — "
              f"{re.sub(r'<[^>]+>', '', (best.get('title',{}) or {}).get('rendered',''))[:70]}")
        return (best.get('content', {}) or {}).get('rendered', '') or None
    except Exception as e:
        print(f"  Fetch error: {e}")
    return None

def _clean_records(records: list[dict], year: int, quarter: int) -> list[dict]:
    """Coerce the LLM's answer to the column types and drop empty rows.

    The prompt asks for the period as "Q2", so the model returns it as a string
    while `quarter` is an INTEGER column — the insert failed with
    InvalidTextRepresentation. And a row where BOTH figures came back null
    carries no information but still violates the NOT NULL columns, which is how
    this crawler ended a run with a DataError instead of a clean "nothing
    published yet". Both are handled here rather than trusting the model.
    """
    out = []
    for rec in records:
        q = rec.get('quarter', quarter)
        if isinstance(q, str):
            digits = ''.join(ch for ch in q if ch.isdigit())
            q = int(digits) if digits else quarter
        y = rec.get('year', year)
        try:
            y = int(y)
        except (TypeError, ValueError):
            y = year
        gdp = rec.get('gdp_billion_vnd')
        yoy = rec.get('growth_yoy_pct')
        if gdp is None and yoy is None:
            continue                      # nothing extracted — do not write a hollow row
        out.append({'year': y, 'quarter': int(q),
                    'sector': rec.get('sector') or 'total',
                    'gdp_billion_vnd': gdp, 'growth_yoy_pct': yoy})
    return out


def upsert_records(records: list[dict], crawl_time: datetime):
    records = _clean_records(records, TARGET_YEAR, TARGET_QUARTER)
    if not records:
        print("  Nothing usable extracted — no rows written")
        return 0
    with engine.connect() as conn:
        for rec in records:
            conn.execute(text("""
                INSERT INTO vn_gso_gdp_quarterly (year, quarter, sector, gdp_billion_vnd, growth_yoy_pct, crawl_time)
                VALUES (:year, :quarter, :sector, :gdp_billion_vnd, :growth_yoy_pct, :crawl_time)
                ON CONFLICT (year, quarter, sector) DO UPDATE SET
                    gdp_billion_vnd = EXCLUDED.gdp_billion_vnd,
                    growth_yoy_pct = EXCLUDED.growth_yoy_pct,
                    crawl_time = EXCLUDED.crawl_time
            """), {**rec, 'crawl_time': crawl_time})
        conn.commit()
    return len(records)



def crawl_period(year: int, quarter: int) -> bool:
    """Fetch + extract + upsert ONE quarter. Returns True on success.

    Lets the crawler target a specific historical quarter instead of always
    reading whatever fetch_gso_html() currently returns (the newest bulletin),
    which is what left this table able to hold only the single most recent
    quarter no matter when it ran.
    """
    global TARGET_YEAR, TARGET_QUARTER
    TARGET_YEAR, TARGET_QUARTER = year, quarter
    print(f"\n--- {year}Q{quarter} ---")

    post = find_article_by_window(year, quarter)
    if not post:
        print(f"  No article found for {year}Q{quarter}")
        return False
    html = (post.get('content', {}) or {}).get('rendered', '')
    if not html:
        print(f"  Article has no body for {year}Q{quarter}")
        return False

    records = layer1_structured(html, year, quarter)
    if not records and GEMINI_API_KEY:
        records = layer3_llm(html, year, quarter)
    if not records:
        print(f"  Nothing extracted for {year}Q{quarter}")
        return False

    upsert_records(records, datetime.now())
    print(f"  Upserted {len(records)} GDP records for {year}Q{quarter}")
    return True

def main():
    ensure_table()
    crawl_time = datetime.now()

    html = fetch_gso_html(GSO_GDP_SEARCH)
    if not html:
        print("ERROR: Could not fetch GSO GDP page")
        return

    records = layer1_structured(html, TARGET_YEAR, TARGET_QUARTER)
    print(f"Layer 1: {len(records)} records")

    if not records:
        records = layer3_llm(html, TARGET_YEAR, TARGET_QUARTER)
        print(f"Layer 3 LLM: {len(records)} records")

    if records:
        n = upsert_records(records, crawl_time)
        print(f"Upserted {n} GDP records for {TARGET_YEAR}Q{TARGET_QUARTER}")
    else:
        print(f"WARNING: No GDP data extracted")

    print(f"\n{'='*60}")
    print(f"GSO GDP Crawler done. Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
