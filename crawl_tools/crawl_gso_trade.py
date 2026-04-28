"""
Vietnam Monthly Import/Export Trade Data Crawler
Source: gso.gov.vn (Tổng cục Thống kê)
Strategy: 3-layer adaptive parsing — Structured → Heuristic → LLM (Gemini)
Schedule: Monthly ~28th at 9:30 AM VN (02:30 UTC)
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
if current_date.month == 1:
    period_year = current_date.year - 1
    period_month = 12
else:
    period_year = current_date.year
    period_month = current_date.month - 1
PERIOD = f"{period_year:04d}-{period_month:02d}"

print(f"\n{'='*60}")
print(f"GSO Trade Crawler — Period: {PERIOD} — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    raise ValueError("CRAWLING_BOT_DB environment variable not set")
engine = create_engine(CRAWLING_BOT_DB)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

GSO_TRADE_SEARCH = "https://www.gso.gov.vn/wp-json/wp/v2/posts?search=xu%E1%BA%A5t+nh%E1%BA%ADp+kh%E1%BA%A9u&per_page=5"


def ensure_table():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_gso_trade_monthly (
                id SERIAL PRIMARY KEY,
                period VARCHAR(7) NOT NULL UNIQUE,
                export_billion_usd FLOAT,
                import_billion_usd FLOAT,
                trade_balance FLOAT,
                top_export_markets JSONB,
                yoy_export_pct FLOAT,
                yoy_import_pct FLOAT,
                crawl_time TIMESTAMP NOT NULL
            )
        """))
        conn.commit()
    print("Table vn_gso_trade_monthly ready.")


def _safe_float(s) -> "Optional[float]":
    try:
        if s is None:
            return None
        return float(str(s).replace(',', '.').replace('%', '').strip())
    except (ValueError, TypeError):
        return None


def layer1_structured(html: str, period: str) -> "Optional[dict]":
    """Parse trade data from standard table."""
    soup = BeautifulSoup(html, 'html.parser')
    export_val = None
    import_val = None
    yoy_export = None
    yoy_import = None

    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cells = [c.get_text(strip=True) for c in row.find_all(['th', 'td'])]
            if not cells:
                continue
            label = cells[0].lower()
            if 'xuất khẩu' in label or 'export' in label:
                nums = [_safe_float(c) for c in cells[1:] if _safe_float(c) is not None]
                if nums:
                    export_val = nums[0]
                    yoy_export = nums[1] if len(nums) > 1 else None
            elif 'nhập khẩu' in label or 'import' in label:
                nums = [_safe_float(c) for c in cells[1:] if _safe_float(c) is not None]
                if nums:
                    import_val = nums[0]
                    yoy_import = nums[1] if len(nums) > 1 else None

    if export_val is not None or import_val is not None:
        balance = (export_val - import_val) if (export_val and import_val) else None
        return {
            'period': period,
            'export_billion_usd': export_val,
            'import_billion_usd': import_val,
            'trade_balance': balance,
            'top_export_markets': None,
            'yoy_export_pct': yoy_export,
            'yoy_import_pct': yoy_import,
        }
    return None


def layer3_llm(html: str, period: str) -> "Optional[dict]":
    if not GEMINI_API_KEY:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    text_content = soup.get_text(separator='\n', strip=True)[:6000]
    prompt = f"""Extract Vietnam import/export trade data for period {period} from this GSO text.
Return a single JSON object:
{{
  "period": "{period}",
  "export_billion_usd": <number>,
  "import_billion_usd": <number>,
  "trade_balance": <number>,
  "yoy_export_pct": <number or null>,
  "yoy_import_pct": <number or null>,
  "top_export_markets": {{"US": 12.5, "China": 8.3}} or null
}}
Only JSON object, nothing else.

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
        return None


def fetch_gso_html() -> "Optional[str]":
    headers = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'vi-VN,vi;q=0.9'}
    try:
        resp = requests.get(GSO_TRADE_SEARCH, headers=headers, timeout=15)
        if resp.status_code == 200:
            posts = resp.json()
            if posts:
                url = posts[0].get('link', '')
                if url:
                    print(f"  Found GSO post: {url}")
                    page = requests.get(url, headers=headers, timeout=20)
                    if page.status_code == 200:
                        return page.text
    except Exception as e:
        print(f"  Fetch error: {e}")
    return None


def upsert_record(rec: dict, crawl_time: datetime):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn_gso_trade_monthly
                (period, export_billion_usd, import_billion_usd, trade_balance,
                 top_export_markets, yoy_export_pct, yoy_import_pct, crawl_time)
            VALUES
                (:period, :export_billion_usd, :import_billion_usd, :trade_balance,
                 :top_export_markets, :yoy_export_pct, :yoy_import_pct, :crawl_time)
            ON CONFLICT (period) DO UPDATE SET
                export_billion_usd = EXCLUDED.export_billion_usd,
                import_billion_usd = EXCLUDED.import_billion_usd,
                trade_balance = EXCLUDED.trade_balance,
                top_export_markets = EXCLUDED.top_export_markets,
                yoy_export_pct = EXCLUDED.yoy_export_pct,
                yoy_import_pct = EXCLUDED.yoy_import_pct,
                crawl_time = EXCLUDED.crawl_time
        """), {
            **{k: v for k, v in rec.items() if k != 'top_export_markets'},
            'top_export_markets': json.dumps(rec.get('top_export_markets')) if rec.get('top_export_markets') else None,
            'crawl_time': crawl_time,
        })
        conn.commit()


def main():
    ensure_table()
    crawl_time = datetime.now()

    html = fetch_gso_html()
    if not html:
        print("ERROR: Could not fetch GSO trade page")
        return

    rec = layer1_structured(html, PERIOD)
    if rec:
        print(f"Layer 1: export={rec.get('export_billion_usd')}, import={rec.get('import_billion_usd')} B USD")
    else:
        print("Layer 1: No data, trying LLM...")
        rec = layer3_llm(html, PERIOD)
        if rec:
            print(f"LLM: export={rec.get('export_billion_usd')}, import={rec.get('import_billion_usd')} B USD")

    if rec:
        upsert_record(rec, crawl_time)
        print(f"Upserted trade data for {PERIOD}")
    else:
        print(f"WARNING: No trade data extracted for {PERIOD}")

    print(f"\n{'='*60}")
    print(f"GSO Trade Crawler done. Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
