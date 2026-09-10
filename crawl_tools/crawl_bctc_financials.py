"""
Automated BCTC (balance sheet) crawler — replaces the manual per-company
process used to build the first 27 rows of `tracked_companies`.

Pipeline: find PDF -> locate statement pages (cheap local OCR via `tesseract`
CLI) -> classify accounting scheme -> send page IMAGES to Gemini for
structured extraction (vision, not local OCR text — local Tesseract produced
~8 digit-misread errors across the manual pilot; sending the page image
directly lets the model read the actual glyphs instead of a garbled text
pass) -> validate against bctc_line_code_dict (sign convention + parent/child
arithmetic + V01, reusing crawl_tools/validate_financial_statements.py) ->
insert only what validates; everything else lands with validated=false, never
silently corrected.

See .claude/skills/financial_statement_extraction/SKILL.md for the manual
methodology this automates, and .claude/knowledge/financial_statements/ for
the accounting rules the validation step enforces.

Usage:
    python crawl_tools/crawl_bctc_financials.py TICKER [TICKER ...] [--year 2025]

Deliberately shells out to `pdftoppm`/`tesseract` (CLI, poppler + tesseract-ocr
system packages) instead of the pdf2image/pytesseract Python bindings pinned
in requirements.txt — those aren't actually installed in this environment,
while the CLI tools were used and proven all through the manual pilot this
automates. Gemini is called via raw REST (matching crawl_gso_gdp.py's
layer3_llm pattern), not the `google-generativeai` SDK also pinned in
requirements.txt — that SDK is now upstream-deprecated ("all support... has
ended, switch to google.genai") and there's no reason to build new code
against a dead library when the REST endpoint works fine with `requests`,
already a real dependency everywhere else in this project.

Rate-limit note: Gemini free tier throttles hard under bulk use (see
crawl_gso_gdp.py's layer3_llm note) — this script makes 1 Gemini call per
ticker, so it's meant to be run over a handful of tickers per invocation, not
the full market in one shot.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv('CRAWLING_CORP_DB')
if not DB_URL:
    sys.exit("CRAWLING_CORP_DB not set")
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

engine = create_engine(DB_URL)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_financial_statements as vfs  # noqa: E402


# ── 1. PDF discovery ─────────────────────────────────────────────────────────

MIRROR_TMPL = ("https://static2.vietstock.vn/data/HOSE/{year}/BCTC/VN/NAM/"
               "{ticker}_Baocaotaichinh_{year}_Kiemtoan_Hopnhat{suffix}.pdf")


def find_pdf_url(ticker: str, year: int) -> str | None:
    """Vietstock static2 mirror, verified working for HOSE-listed tickers
    across the manual pilot (see SKILL.md "Nguồn tìm file BCTC"). PDR needed
    the _1 suffix; some tickers (POW, VIX, banks with no subsidiaries) use a
    different naming pattern entirely and need a bespoke IR-page fallback not
    yet automated here — returns None so the caller can flag it for manual
    follow-up instead of guessing.
    """
    for suffix in ("", "_1"):
        url = MIRROR_TMPL.format(year=year, ticker=ticker, suffix=suffix)
        try:
            r = requests.head(url, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                return url
        except requests.RequestException:
            continue
    return None


def download_pdf(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200 or len(r.content) < 10000:
            return False
        dest.write_bytes(r.content)
        return True
    except requests.RequestException:
        return False


# ── 2. Locate statement pages (cheap local OCR, no Gemini call) ─────────────

def render_pages(pdf_path: Path, out_dir: Path, first: int, last: int, dpi: int) -> list[Path]:
    prefix = out_dir / "p"
    subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), "-f", str(first), "-l", str(last),
         str(pdf_path), str(prefix)],
        capture_output=True, check=False,
    )
    return sorted(out_dir.glob("p-*.png"))


def page_num_from_path(p: Path) -> int:
    # pdftoppm names p-01.png / p-001.png depending on total page count.
    m = re.search(r'p-0*(\d+)\.png$', p.name)
    return int(m.group(1)) if m else -1


def ocr_text(image_path: Path) -> str:
    proc = subprocess.run(
        ["tesseract", str(image_path), "-", "-l", "vie"],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout or ""


MARKER_PATTERNS = {
    'BANK_B02_TCTD_HN': re.compile(r'B\s*0?2\s*/\s*TCTD', re.IGNORECASE),
    'CTCK_B01': re.compile(r'B\s*0?1\s*[-–—]\s*CTCK', re.IGNORECASE),
    'TT200_DN': re.compile(r'B\s*0?1\s*[-–—]\s*DN', re.IGNORECASE),
}
# Checked in this order — CTCK/BANK markers are more specific than the bare
# "B01-DN" pattern, so they must be tried first or a bank page whose OCR
# garbled "TCTD" down to noise could wrongly fall through to TT200_DN.
MARKER_ORDER = ['BANK_B02_TCTD_HN', 'CTCK_B01', 'TT200_DN']

ASSET_HEADER_RE = re.compile(r'(TÀI SẢN|TAI SAN)', re.IGNORECASE)
LIABILITY_HEADER_RE = re.compile(r'(NGUỒN VỐN|NGUON VON|NỢ PHẢI TRẢ|NO PHAI TRA)', re.IGNORECASE)
INSURANCE_MARKER_RE = re.compile(r'tái bảo hiểm|tai bao hiem', re.IGNORECASE)
# Explicit stop signals: title of the NEXT statement in the filing (income
# statement / cash flow / notes). A balance sheet legitimately runs 2-4 pages
# and keeps repeating "TÀI SẢN"/"NGUỒN VỐN" on each one — capping the range by
# page count alone was too rigid, but running unbounded once let a distant,
# unrelated page (case: FPT FY2024, page 19) get treated as if it were the
# liabilities continuation. Stopping on the next statement's own title is a
# structural signal, not a fragile page-count guess.
NEXT_STATEMENT_RE = re.compile(
    r'KẾT QUẢ HOẠT ĐỘNG|KET QUA HOAT DONG|LƯU CHUYỂN TIỀN TỆ|LUU CHUYEN TIEN TE|'
    r'THUYẾT MINH BÁO CÁO|THUYET MINH BAO CAO',
    re.IGNORECASE,
)
MAX_STATEMENT_PAGES = 6  # safety valve — no real balance sheet needs more than this


def scan_for_statement_pages(pdf_path: Path, scratch: Path, max_pages: int = 25) -> dict:
    """Cheap pass: low-DPI render + Tesseract to find which CONTIGUOUS range of
    pages carries the balance sheet and what scheme it's in. This stays local
    (no Gemini call) because it only needs structural yes/no answers — the
    expensive, accuracy-critical extraction happens later on images sent
    straight to Gemini.

    Returns the full page range, not just one "asset page" + one "liability
    page" — a balance sheet is not reliably 2 pages. FPT's FY2024 filing needed
    3 (short-term assets / long-term assets / liabilities+equity); assuming 2
    silently dropped the long-term-assets page entirely and, worse, let the
    liability-page search wander to an unrelated page far later in the
    document once nothing matched nearby.
    """
    pages = render_pages(pdf_path, scratch, 1, max_pages, dpi=120)

    scheme = None
    statement_pages: list[int] = []
    is_insurance = False
    started = False

    for p in pages:
        pnum = page_num_from_path(p)
        txt = ocr_text(p)

        page_scheme = None
        for s in MARKER_ORDER:
            if MARKER_PATTERNS[s].search(txt):
                page_scheme = s
                break

        if INSURANCE_MARKER_RE.search(txt):
            is_insurance = True

        has_statement_content = bool(ASSET_HEADER_RE.search(txt) or LIABILITY_HEADER_RE.search(txt))

        if not started:
            if page_scheme and has_statement_content:
                started = True
                scheme = page_scheme
                statement_pages.append(pnum)
            continue

        # Already inside the statement — a DIFFERENT scheme marker, or the
        # next statement's own title, means the balance sheet has ended.
        other_scheme = any(page_scheme == s2 for s2 in MARKER_ORDER if s2 != scheme and page_scheme == s2)
        if other_scheme or NEXT_STATEMENT_RE.search(txt):
            break
        if has_statement_content or page_scheme == scheme:
            statement_pages.append(pnum)
            if len(statement_pages) >= MAX_STATEMENT_PAGES:
                break
        else:
            break  # a page with neither header nor scheme marker ends the run

    if scheme == 'TT200_DN' and is_insurance:
        scheme = 'TT200_DN_INSURANCE'

    return {
        'scheme': scheme,
        'pages': statement_pages,
    }


# ── 3. Gemini vision extraction ──────────────────────────────────────────────

def get_code_dict(scheme: str) -> list[dict]:
    """Pull the sign-convention/parent-code dictionary for this scheme (plus
    its base scheme if it inherits one, e.g. TT200_DN_INSURANCE) so the model
    has real codes to match against instead of inventing its own."""
    base = {'TT200_DN_INSURANCE': 'TT200_DN'}.get(scheme)
    schemes = [base, scheme] if base else [scheme]
    rows = []
    with engine.connect() as conn:
        for s in schemes:
            rows += [dict(r._mapping) for r in conn.execute(text(
                "SELECT line_code, line_label, parent_code, sign_convention "
                "FROM bctc_line_code_dict WHERE code_scheme = :s"
            ), dict(s=s))]
    return rows


def gemini_extract_lines(image_paths: list[Path], scheme: str, code_dict: list[dict]) -> list[dict]:
    if not GEMINI_API_KEY:
        print("  [gemini] GEMINI_API_KEY not set, skipping")
        return []

    dict_text = json.dumps(code_dict, ensure_ascii=False)
    prompt = f"""Bạn đang đọc trang "Bảng cân đối kế toán" (balance sheet) từ báo cáo tài chính
của một công ty niêm yết Việt Nam, biểu mẫu scheme = "{scheme}".

Dưới đây là từ điển mã chỉ tiêu chính thức cho scheme này (line_code, line_label, parent_code,
sign_convention — 'negative' nghĩa là giá trị BẮT BUỘC ghi âm, 'positive' bắt buộc dương,
'either' có thể cả hai):
{dict_text}

Đọc CHÍNH XÁC từng dòng số liệu trong ảnh. Với mỗi dòng, khớp với line_code gần nhất trong từ
điển trên nếu tên khớp (không suy đoán mã nếu tên không khớp — để line_code là mã gốc in trên
ảnh, ví dụ số La Mã, và đánh dấu "unmatched": true).

Với dòng có sign_convention='negative' trong từ điển: nếu ảnh in số trong dấu ngoặc đơn "(...)",
PHẢI trả về giá trị ÂM (thêm dấu trừ), không trả số dương.

Trả về DUY NHẤT 1 JSON array, không kèm giải thích, mỗi phần tử có dạng:
{{"line_code": "...", "line_label": "...", "value_current": <number>, "value_prior": <number or null>,
  "unmatched": <true/false>}}

value_current/value_prior là số nguyên (loại bỏ dấu chấm/phẩy phân cách nghìn), giữ đúng đơn vị
in trên ảnh (không tự quy đổi)."""

    parts = [{"text": prompt}]
    for p in image_paths:
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": base64.b64encode(p.read_bytes()).decode("ascii"),
            }
        })

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={"contents": [{"parts": parts}],
                  "generationConfig": {"temperature": 0.1}},
            timeout=280,
        )
        resp.raise_for_status()
        raw = resp.json()['candidates'][0]['content']['parts'][0]['text']
        raw = re.sub(r'^```\w*\n?|\n?```$', '', raw.strip()).strip()
        return json.loads(raw)
    except Exception as e:
        print(f"  [gemini] extraction failed: {e}")
        return []


# ── 4. Insert + validate ─────────────────────────────────────────────────────

def detect_unit(image_paths: list[Path]) -> str:
    """Best-effort: OCR the header row for 'Triệu' — defaults to VND (raw)
    if not found, matching the more common case across the manual pilot."""
    for p in image_paths[:1]:
        if re.search(r'triệu|trieu', ocr_text(p), re.IGNORECASE):
            return 'VND_million'
    return 'VND'


def insert_rows(ticker: str, scheme: str, rows: list[dict], unit: str,
                 source_url: str, consolidated: bool, period_end: str):
    mult = 1_000_000 if unit == 'VND_million' else 1
    with engine.begin() as conn:
        for r in rows:
            cur = r.get('value_current')
            pri = r.get('value_prior')
            code = str(r.get('line_code', ''))[:10]
            if not code or cur is None:
                continue
            conn.execute(text("""
                INSERT INTO listed_company_financials
                (ticker, report_type, consolidated, period_end, period_type,
                 line_code, line_label, value_current, value_prior, unit,
                 value_current_vnd, value_prior_vnd,
                 source_url, extraction_method, validated, source, group_name, crawl_time)
                VALUES (:ticker, 'balance_sheet', :consolidated, :period_end, 'annual',
                 :code, :label, :cur, :pri, :unit, :curv, :priv,
                 :src, 'ocr_llm', false, :src, 'stock', now())
                ON CONFLICT (ticker, report_type, consolidated, period_end, line_code)
                DO UPDATE SET value_current=EXCLUDED.value_current, value_prior=EXCLUDED.value_prior,
                              value_current_vnd=EXCLUDED.value_current_vnd, value_prior_vnd=EXCLUDED.value_prior_vnd,
                              validated=false, crawl_time=now()
            """), dict(ticker=ticker, code=code, label=str(r.get('line_label', ''))[:500],
                       cur=cur, pri=pri, unit=unit,
                       curv=(cur * mult) if cur is not None else None,
                       priv=(pri * mult) if pri is not None else None,
                       src=source_url, consolidated=consolidated, period_end=period_end))

        # Ensure a tracked_companies row exists so validate_financial_statements
        # can resolve this ticker's scheme. tracked_companies is one row PER
        # TICKER, not per period — GREATEST() keeps latest_period_end honest
        # when crawling an older year for a ticker that already has a newer
        # one (e.g. backfilling FY2024 for a ticker already done for FY2025);
        # a plain overwrite here once regressed FPT's latest_period_end from
        # 2025 back to 2024. `status` intentionally stays whatever this run's
        # period produced ('partial' until Bước 3.5 confirms it clean) — it
        # does NOT try to summarize "one period is clean, another isn't" across
        # multiple periods; check listed_company_financials.validated per
        # period_end directly for that.
        conn.execute(text("""
            INSERT INTO tracked_companies
            (ticker, industry_group, code_scheme, consolidated, latest_period_end, status, source_url, updated_at)
            VALUES (:t, :ig, :s, :cons, :pe, 'partial', :src, now())
            ON CONFLICT (ticker) DO UPDATE SET
                code_scheme=EXCLUDED.code_scheme,
                latest_period_end=GREATEST(tracked_companies.latest_period_end, EXCLUDED.latest_period_end),
                source_url=EXCLUDED.source_url, updated_at=now()
        """), dict(t=ticker, ig={'TT200_DN': 'corp_thuong', 'TT200_DN_INSURANCE': 'insurance',
                                  'BANK_B02_TCTD_HN': 'bank', 'CTCK_B01': 'securities'}.get(scheme, 'corp_thuong'),
                   s=scheme, cons=consolidated, pe=period_end, src=source_url))


def mark_validated(ticker: str, period_end: str, ok_codes: set[str]):
    if not ok_codes:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE listed_company_financials SET validated = true
            WHERE ticker = :t AND period_end = :p AND line_code = ANY(:codes)
        """), dict(t=ticker, p=period_end, codes=list(ok_codes)))


def run_one(ticker: str, year: int):
    print(f"=== {ticker} ===")
    url = find_pdf_url(ticker, year)
    if not url:
        print(f"  no PDF found at the known mirror pattern — needs manual IR-page lookup")
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO tracked_companies (ticker, industry_group, status, notes, updated_at)
                VALUES (:t, 'unknown', 'not_found', 'crawl_bctc_financials.py: mirror 404, cần dò IR thủ công', now())
                ON CONFLICT (ticker) DO UPDATE SET status='not_found',
                    notes='crawl_bctc_financials.py: mirror 404, cần dò IR thủ công', updated_at=now()
            """), dict(t=ticker))
        return

    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td)
        pdf_path = scratch / f"{ticker}.pdf"
        if not download_pdf(url, pdf_path):
            print(f"  download failed: {url}")
            return

        loc = scan_for_statement_pages(pdf_path, scratch)
        if not loc['scheme'] or not loc['pages']:
            print(f"  could not locate/classify balance sheet pages: {loc}")
            return
        print(f"  scheme={loc['scheme']} pages={loc['pages']}")

        hi_dir = scratch / "hi"
        hi_dir.mkdir()
        images = render_pages(pdf_path, hi_dir, min(loc['pages']), max(loc['pages']), dpi=300)

        unit = detect_unit(images)
        code_dict = get_code_dict(loc['scheme'])
        rows = gemini_extract_lines(images, loc['scheme'], code_dict)
        if not rows:
            print("  gemini returned no rows")
            return
        print(f"  extracted {len(rows)} lines")

        consolidated = loc['scheme'] != 'CTCK_B01'  # CTCK pilot (VIX) was standalone; refine per-ticker later
        period_end = f"{year}-12-31"
        insert_rows(ticker, loc['scheme'], rows, unit, url, consolidated, period_end)

        # Run the same mechanical validation the manual pipeline uses, then
        # promote only the rows that pass to validated=true. validate_ticker
        # checks EVERY period_end this ticker has (it may already carry a
        # different year from an earlier run) — filter down to just the
        # period this run just inserted before acting on the result, or a
        # violation on the ticker's OTHER period would wrongly block this one
        # (and marking "ok" codes true would wrongly touch the other period's
        # rows too, which is why mark_validated is also period-scoped).
        all_violations = []
        vfs.validate_ticker(engine.connect(), ticker, all_violations)
        violations = [v for v in all_violations if str(v[1]) == period_end]
        hard_codes = {v[3] for v in violations if v[2] in ('SIGN', 'ARITHMETIC', 'V01', 'SCALE')}
        all_codes = {str(r.get('line_code', ''))[:10] for r in rows if r.get('value_current') is not None}
        ok_codes = all_codes - hard_codes
        mark_validated(ticker, period_end, ok_codes)

        hard = [v for v in violations if v[2] in ('SIGN', 'ARITHMETIC', 'V01', 'SCALE')]
        if hard:
            print(f"  {len(hard)} violation(s) — left validated=false:")
            for v in hard:
                print(f"    [{v[2]}] {v[3]}: {v[4]}")
        else:
            print(f"  clean — {len(ok_codes)} rows validated=true")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='+')
    ap.add_argument('--year', type=int, default=2025)
    args = ap.parse_args()

    for i, t in enumerate(args.tickers):
        run_one(t.upper(), args.year)
        if i < len(args.tickers) - 1:
            time.sleep(3)  # be polite to the free-tier Gemini rate limit


if __name__ == '__main__':
    main()
