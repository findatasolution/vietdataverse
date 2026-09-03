"""
Vietnam Monthly Import/Export Trade Data Crawler
Source: nso.gov.vn (Tổng cục Thống kê)
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
print(f"GSO Trade Crawler — Period: {PERIOD} — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

CRAWLING_BOT_DB = os.getenv('CRAWLING_BOT_DB')
if not CRAWLING_BOT_DB:
    raise ValueError("CRAWLING_BOT_DB environment variable not set")
engine = create_engine(CRAWLING_BOT_DB)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

GSO_TRADE_SEARCH = "https://www.nso.gov.vn/wp-json/wp/v2/posts?search=xu%E1%BA%A5t+nh%E1%BA%ADp+kh%E1%BA%A9u&per_page=5"


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


VN_MONTH_NAMES = {
    1: 'một', 2: 'hai', 3: 'ba', 4: 'tư', 5: 'năm', 6: 'sáu',
    7: 'bảy', 8: 'tám', 9: 'chín', 10: 'mười', 11: 'mười một', 12: 'mười hai',
}
ROMAN_QUARTER = {1: 'i', 2: 'ii', 3: 'iii', 4: 'iv'}


def _text_after_keyword(text, keyword_variants, year, month, span=220):
    """Return the text starting at a keyword mention that also names this
    exact month, up to `span` characters, or None.

    Two prior versions of this both grabbed the wrong number:
      - a fixed character radius around the keyword picked up a NEIGHBOURING
        month's or a cumulative total's figure sitting nearby;
      - splitting on '.' and taking the whole "sentence" still failed once,
        because NSO's prose sometimes chains two distinct clauses with an
        en-dash and no period ("...đạt 110,52 tỷ USD, chiếm 89,9% – Nhập khẩu
        hàng hóa: Kim ngạch nhập khẩu hàng hóa tháng Ba đạt 47,11 tỷ USD..."),
        so the "sentence" contained TWO tỷ-USD figures and the first (an
        unrelated export sub-category, not the import total) matched.
    Slicing forward FROM the keyword's own position — not from the start of
    whatever punctuation-delimited chunk contains it — is what guarantees the
    number found is the one actually attached to that keyword mention.
    """
    # NSO writes "month/year" four different ways across bulletins:
    # "8/2023", "08/2023", "tháng 8 năm 2023" (no slash), or the bare
    # Vietnamese month name with no digit at all ("tháng Bảy"). All four are
    # accepted; none alone covers every year seen in this backfill.
    digit_tokens = (f'{month}/{year}', f'{month:02d}/{year}',
                     f'tháng {month} năm {year}', f'tháng {month:02d} năm {year}')
    name_token = f'tháng {VN_MONTH_NAMES[month]}'
    low = text.lower()
    for kw in keyword_variants:
        start = 0
        while True:
            i = low.find(kw, start)
            if i < 0:
                break
            window = text[i:i + span]
            wlow = window.lower()
            if any(tok in wlow for tok in digit_tokens) or name_token in wlow:
                return window
            start = i + len(kw)
    return None


def layer1_structured(html: str, period: str) -> "Optional[dict]":
    """Parse trade data from prose text — NSO's monthly bulletins do not use
    <table> markup for this figure (verified back to 2020); the previous
    table-only parser matched nothing for any bulletin before ~2023 and every
    period silently fell through to the rate-limited Gemini layer."""
    text = re.sub(r'\s+', ' ', BeautifulSoup(html, 'html.parser').get_text(' ', strip=True))
    year, month = (int(x) for x in period.split('-'))

    def parse(window):
        if not window:
            return None, None
        vm = re.search(r'([\d]+(?:[,\.]\d+)?)\s*t[ỷy]\s*USD', window, re.IGNORECASE)
        if not vm:
            return None, None
        value = _safe_float(vm.group(1))
        ym = re.search(r'(t[ăa]ng|gi[ảa]m)\s+([\d]+(?:[,\.]\d+)?)%\s*so v[ớo]i c[ùu]ng k[ỳy]',
                        window, re.IGNORECASE)
        yoy = None
        if ym:
            sign = -1 if ym.group(1).lower() == 'giảm' else 1
            yoy = sign * _safe_float(ym.group(2))
        return value, yoy

    # NSO also reverses this phrase's word order in some bulletins ("Kim
    # ngạch hàng hóa xuất khẩu tháng 2/2020 ước tính đạt..." vs the more
    # common "kim ngạch xuất khẩu hàng hóa") — 2020-02 has both forms in the
    # same article, one stating the 2-month cumulative and the other the
    # standalone month; missing the reversed form meant only the cumulative
    # sentence was ever seen, and it has no per-month token to match on.
    export_win = _text_after_keyword(
        text, ['kim ngạch xuất khẩu hàng hóa', 'kim ngạch hàng hóa xuất khẩu'], year, month)
    import_win = _text_after_keyword(
        text, ['kim ngạch nhập khẩu hàng hóa', 'kim ngạch hàng hóa nhập khẩu'], year, month)
    export_val, yoy_export = parse(export_win)
    import_val, yoy_import = parse(import_win)

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
    # The bulletin body runs ~16k characters and the figures sit well past the
    # 6,000-character mark this used to cut at, so the extractor was reading
    # only the opening summary. `content.rendered` is body-only, so passing it
    # whole costs a few thousand tokens and no noise.
    text_content = soup.get_text(separator='\n', strip=True)[:20000]
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
        return None


# NSO publishes its statistics inside the monthly socio-economic bulletin, whose
# slug always starts with this. Free-text search alone returns the newsroom —
# a piece about a deputy director's site visit outranked the actual report —
# so hits are filtered by slug the way crawl_gso_cpi.py already does.
REPORT_SLUG = 'bao-cao-tinh-hinh-kinh-te-xa-hoi'
REPORT_SEARCH = ("https://www.nso.gov.vn/wp-json/wp/v2/posts?search="
                 + requests.utils.quote("báo cáo tình hình kinh tế xã hội")
                 + "&per_page=30&_fields=link,date,title,content")



def find_article_by_window(year: int, month: int) -> "Optional[dict]":
    """Find the month's bulletin by WHEN NSO published it — see the identical
    function in crawl_gso_industry.py for why fetch_gso_html() alone cannot
    target a specific historical month. Not used before 2020 (see there)."""
    start = f"{year}-{month:02d}-25"
    # The bulletin closing a quarter (Mar/Jun/Sep/Dec) bundles a full
    # quarter's extra tables and publishes noticeably later than a plain
    # month's report — see crawl_gso_industry.py's find_article_by_window for
    # the Sept-2020 case (didn't appear until Nov 2) that motivated this.
    is_quarter_close = month in (3, 6, 9, 12)
    if month >= 11:
        ny, nm = year + 1, month - 10
    else:
        ny, nm = year, month + 2
    end_day = 10 if is_quarter_close else 20
    end = f"{ny}-{nm:02d}-{end_day:02d}"
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
                 if REPORT_SLUG in p.get('link', '') and str(year) in p.get('link', '').rstrip('/').rsplit('/', 1)[-1]]
        if not posts:
            return None
        posts.sort(key=lambda p: p.get('date', ''))
        if is_quarter_close:
            q = month // 3
            quarterly = [p for p in posts if f'quy-{ROMAN_QUARTER[q]}' in p.get('link', '').lower()]
            if quarterly:
                posts = quarterly
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

    rec = layer1_structured(html, period)
    if not rec:
        rec = layer3_llm(html, period)
    if not rec:
        print(f"  Nothing extracted for {period}")
        return False

    upsert_record(rec, datetime.now())
    print(f"  Upserted trade data for {period}: export={rec.get('export_billion_usd')}, "
          f"import={rec.get('import_billion_usd')} B USD")
    return True

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
