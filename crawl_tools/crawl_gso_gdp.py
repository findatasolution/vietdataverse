"""
Vietnam GDP Quarterly Crawler
Source: gso.gov.vn (Tổng cục Thống kê)
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

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'be' / '.env')

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

GSO_GDP_SEARCH = "https://www.gso.gov.vn/wp-json/wp/v2/posts?search=t%E1%BB%95ng+s%E1%BA%A3n+ph%E1%BA%A9m+trong+n%C6%B0%E1%BB%9Bc&per_page=5"

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
                UNIQUE (year, quarter, sector)
            )
        """))
        conn.commit()
    print("Table vn_gso_gdp_quarterly ready.")


def _safe_float(s) -> "Optional[float]":
    try:
        if s is None:
            return None
        return float(str(s).replace(',', '.').replace('%', '').strip())
    except (ValueError, TypeError):
        return None


def layer1_structured(html: str, year: int, quarter: int) -> list[dict]:
    records = []
    soup = BeautifulSoup(html, 'html.parser')
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if not cells:
                continue
            sector_vn = cells[0]
            matched = None
            for vn, en in GDP_SECTORS.items():
                if vn in sector_vn:
                    matched = en
                    break
            if not matched:
                continue
            nums = [_safe_float(c) for c in cells[1:] if _safe_float(c) is not None]
            records.append({
                'year': year, 'quarter': quarter, 'sector': matched,
                'gdp_billion_vnd': nums[0] if nums else None,
                'growth_yoy_pct': nums[1] if len(nums) > 1 else None,
            })
    return records


def layer3_llm(html: str, year: int, quarter: int) -> list[dict]:
    if not GEMINI_API_KEY:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    text_content = soup.get_text(separator='\n', strip=True)[:6000]
    prompt = f"""Extract Vietnam GDP data for {year} Q{quarter} from this GSO text.
Return JSON array: [{{year, quarter, sector, gdp_billion_vnd, growth_yoy_pct}}]
Sectors: total, agriculture, industry, services, taxes_subsidies
Only JSON, nothing else.

Text:
{text_content}"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}],
                                        "generationConfig": {"temperature": 0.1}}, timeout=30)
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw = re.sub(r'```json\s*|\s*```', '', raw).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  [LLM] Error: {e}")
        return []


def fetch_gso_html(search_url: str) -> "Optional[str]":
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi-VN,vi;q=0.9'}
    try:
        resp = requests.get(search_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            posts = resp.json()
            if posts:
                url = posts[0].get('link', '')
                if url:
                    page = requests.get(url, headers=headers, timeout=20)
                    if page.status_code == 200:
                        return page.text
    except Exception as e:
        print(f"  Fetch error: {e}")
    return None


def upsert_records(records: list[dict], crawl_time: datetime):
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


def main():
    ensure_table()
    crawl_time = datetime.now()

    html = fetch_gso_html(GSO_GDP_SEARCH)
    if not html:
        print("ERROR: Could not fetch GSO GDP page")
        return

    records = layer1_structured(html, TARGET_YEAR, TARGET_QUARTER)
    print(f"Layer 1: {len(records)} records")

    if len(records) < 2:
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
