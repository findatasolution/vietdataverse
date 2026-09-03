"""
Vietnam Industrial Production Index (IIP) Monthly Crawler
Source: nso.gov.vn — Chỉ số Sản xuất Công nghiệp (IIP)
Strategy: 3-layer adaptive parsing — Structured → Heuristic → LLM (Gemini)
Schedule: Monthly ~25th-28th at 9:00 AM VN (02:00 UTC)
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
if current_date.month == 1:
    period_year = current_date.year - 1
    period_month = 12
else:
    period_year = current_date.year
    period_month = current_date.month - 1
PERIOD = f"{period_year:04d}-{period_month:02d}"

print(f"\n{'='*60}")
print(f"GSO Industry (IIP) Crawler — Period: {PERIOD} — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    raise ValueError("CRAWLING_BOT_DB environment variable not set")
engine = create_engine(CRAWLING_BOT_DB)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

GSO_IIP_SEARCH = "https://www.nso.gov.vn/wp-json/wp/v2/posts?search=ch%E1%BB%89+s%E1%BB%91+s%E1%BA%A3n+xu%E1%BA%A5t+c%C3%B4ng+nghi%E1%BB%87p&per_page=5"

IIP_SECTORS = [
    'Toàn ngành công nghiệp',
    'Khai khoáng',
    'Công nghiệp chế biến, chế tạo',
    'Sản xuất và phân phối điện, khí đốt',
    'Cung cấp nước, xử lý rác thải',
]


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_gso_iip_monthly (
                id SERIAL PRIMARY KEY,
                period VARCHAR(7) NOT NULL,
                sector_name VARCHAR(200) NOT NULL,
                iip_index FLOAT,
                iip_yoy_pct FLOAT,
                crawl_time TIMESTAMP NOT NULL,
                source TEXT NOT NULL DEFAULT 'nso.gov.vn',
                group_name VARCHAR(20) NOT NULL DEFAULT 'macro',
                UNIQUE (period, sector_name)
            )
        """))
        for col, definition in [
            ('source',     "TEXT NOT NULL DEFAULT 'nso.gov.vn'"),
            ('group_name', "VARCHAR(20) NOT NULL DEFAULT 'macro'"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE vn_gso_iip_monthly ADD COLUMN IF NOT EXISTS {col} {definition}"))
                conn.commit()
            except Exception:
                conn.rollback()
        conn.commit()
    print("Table vn_gso_iip_monthly ready.")


def _safe_float(s) -> "Optional[float]":
    try:
        if s is None:
            return None
        return float(str(s).replace(',', '.').replace('%', '').strip())
    except (ValueError, TypeError):
        return None


def layer1_structured(html: str, period: str) -> list[dict]:
    records = []
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if not cells:
                continue
            sector_name = cells[0]
            if not any(kw in sector_name for kw in ['ngành', 'công nghiệp', 'khai', 'chế biến', 'điện', 'nước']):
                continue
            nums = [_safe_float(c) for c in cells[1:] if _safe_float(c) is not None]
            records.append({
                'period': period,
                'sector_name': sector_name[:200],
                'iip_index': nums[0] if nums else None,
                'iip_yoy_pct': nums[1] if len(nums) > 1 else None,
            })
    return records


def layer2_heuristic(html: str, period: str) -> list[dict]:
    records = []
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if len(cells) < 2:
                continue
            for sector in IIP_SECTORS:
                if sector in cells[0]:
                    nums = [_safe_float(c) for c in cells[1:] if _safe_float(c) is not None]
                    records.append({
                        'period': period,
                        'sector_name': sector,
                        'iip_index': nums[0] if nums else None,
                        'iip_yoy_pct': nums[1] if len(nums) > 1 else None,
                    })
                    break
    return records


def layer3_llm(html: str, period: str) -> list[dict]:
    if not GEMINI_API_KEY:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    # The bulletin body runs ~16k characters and the figures sit well past the
    # 6,000-character mark this used to cut at, so the extractor was reading
    # only the opening summary. `content.rendered` is body-only, so passing it
    # whole costs a few thousand tokens and no noise.
    text_content = soup.get_text(separator='\n', strip=True)[:20000]
    prompt = f"""Extract Vietnam Industrial Production Index (IIP/Chỉ số sản xuất công nghiệp) for period {period}.
Return JSON array: [{{period, sector_name, iip_index, iip_yoy_pct}}]
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
REPORT_SLUG = 'bao-cao-tinh-hinh-kinh-te-xa-hoi'
REPORT_SEARCH = ("https://www.nso.gov.vn/wp-json/wp/v2/posts?search="
                 + requests.utils.quote("báo cáo tình hình kinh tế xã hội")
                 + "&per_page=30&_fields=link,date,title,content")



def find_article_by_window(year: int, month: int) -> "Optional[dict]":
    """Find the month's bulletin by WHEN NSO published it.

    fetch_gso_html() below only ever returns the NEWEST bulletin, so this
    crawler could only ever populate the single most recent month no matter
    which period it was asked about. Verified reliable back to 2020-01; posts
    before that share bulk-republish timestamps from a 2019 site migration
    that do not reflect their actual reporting period, so this is not used
    before 2020.
    """
    start = f"{year}-{month:02d}-25"
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{ny}-{nm:02d}-20"
    url = (f"https://www.nso.gov.vn/wp-json/wp/v2/posts"
           f"?after={start}T00:00:00&before={end}T23:59:59"
           f"&per_page=100&_fields=link,date,content,title")
    try:
        resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
        if resp.status_code != 200:
            return None
        posts = [p for p in resp.json() if REPORT_SLUG in p.get('link', '')]
        if not posts:
            return None
        posts.sort(key=lambda p: p.get('date', ''))
        print(f"  Found by window: {posts[0]['link']}")
        return posts[0]
    except Exception as e:
        print(f"  Window search error: {e}")
        return None


def fetch_gso_html() -> "Optional[str]":
    """Return the BODY html of the newest NSO monthly bulletin.

    Three separate faults kept this table empty since it was created:
      - it pointed at gso.gov.vn, a domain that stopped resolving when the
        office rebranded to nso.gov.vn (the CPI crawler was already migrated);
      - it fetched the article's full page, so the first 6,000 characters handed
        to the extractor were the site menu and stylesheet, not the report —
        `content.rendered` from the API is the body alone;
      - it took posts[0] from a free-text search, which returns newsroom items.
    """
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi-VN,vi;q=0.9'}
    try:
        resp = requests.get(REPORT_SEARCH, headers=headers, timeout=25)
        if resp.status_code != 200:
            print(f"  Search HTTP {resp.status_code}")
            return None
        posts = [p for p in resp.json() if REPORT_SLUG in p.get('link', '')]
        if not posts:
            print("  No bulletin matched the report slug")
            return None
        posts.sort(key=lambda p: p.get('date', ''), reverse=True)
        best = posts[0]
        print(f"  Article: {best.get('date','?')[:10]} — "
              f"{re.sub(r'<[^>]+>', '', (best.get('title',{}) or {}).get('rendered',''))[:70]}")
        return (best.get('content', {}) or {}).get('rendered', '') or None
    except Exception as e:
        print(f"  Fetch error: {e}")
    return None

def upsert_records(records: list[dict], crawl_time: datetime):
    with engine.connect() as conn:
        for rec in records:
            conn.execute(text("""
                INSERT INTO vn_gso_iip_monthly (period, sector_name, iip_index, iip_yoy_pct, crawl_time, source, group_name)
                VALUES (:period, :sector_name, :iip_index, :iip_yoy_pct, :crawl_time, :source, :group_name)
                ON CONFLICT (period, sector_name) DO UPDATE SET
                    iip_index = EXCLUDED.iip_index,
                    iip_yoy_pct = EXCLUDED.iip_yoy_pct,
                    crawl_time = EXCLUDED.crawl_time,
                    source = EXCLUDED.source,
                    group_name = EXCLUDED.group_name
            """), {**rec, 'crawl_time': crawl_time, 'source': 'nso.gov.vn', 'group_name': 'macro'})
        conn.commit()
    return len(records)



def crawl_period(year: int, month: int) -> bool:
    """Fetch + extract + upsert ONE month. Returns True on success."""
    period = f"{year:04d}-{month:02d}"
    print(f"\n--- {period} ---")

    post = find_article_by_window(year, month)
    if not post:
        print(f"  No article found for {period}")
        return False
    html = (post.get('content', {}) or {}).get('rendered', '')
    if not html:
        print(f"  Article has no body for {period}")
        return False

    records = layer1_structured(html, period)
    if len(records) < 2:
        records = layer2_heuristic(html, period)
    if len(records) < 2:
        records = layer3_llm(html, period)
    if not records:
        print(f"  Nothing extracted for {period}")
        return False

    n = upsert_records(records, datetime.now())
    print(f"  Upserted {n} IIP records for {period}")
    return True

def main():
    ensure_table()
    crawl_time = datetime.now()

    html = fetch_gso_html()
    if not html:
        print("ERROR: Could not fetch GSO IIP page")
        return

    records = layer1_structured(html, PERIOD)
    print(f"Layer 1: {len(records)} records")

    if len(records) < 2:
        records = layer2_heuristic(html, PERIOD)
        print(f"Layer 2: {len(records)} records")

    if len(records) < 2:
        records = layer3_llm(html, PERIOD)
        print(f"Layer 3 LLM: {len(records)} records")

    if records:
        n = upsert_records(records, crawl_time)
        print(f"Upserted {n} IIP records for {PERIOD}")
        for r in records[:3]:
            print(f"  {r['sector_name'][:50]}: iip={r['iip_index']}, yoy={r['iip_yoy_pct']}%")
    else:
        print(f"WARNING: No IIP data extracted for {PERIOD}")

    print(f"\n{'='*60}")
    print(f"GSO Industry Crawler done. Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
