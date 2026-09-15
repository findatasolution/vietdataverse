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
import unicodedata
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


DOWNLOAD_HEADERS = {
    # Some IR sites (SSI confirmed: 403 with no header, 200 with this) reject
    # requests' default "python-requests/x.y" User-Agent outright — curl's
    # default UA (or lack of one) sails through the same check, which is why
    # a manual `curl` retest can look like it "just works" while the Python
    # path fails silently. Not an anti-bot bypass attempt, just presenting as
    # an ordinary browser client the way curl already does by default.
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"),
}


def download_pdf(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, timeout=60, headers=DOWNLOAD_HEADERS)
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


def _strip_diacritics(s: str) -> str:
    """Collapse Vietnamese diacritics to bare ASCII before pattern matching.

    OCR at low DPI is unreliable about WHICH diacritic/glyph it reports even
    when the general shape is right — two real cases this session: the dash
    in "B 01 – DN/HN" OCR'd as a tilde on one page of GAS's FY2024 filing
    (silently missed 2 of 3 balance-sheet pages, with no validator signal
    since there was nothing to cross-check the missing assets side against);
    "KẾT QUẢ" OCR'd as "KÉT QUÀ" (wrong tone mark on both syllables) on the
    very next page, missing the income statement entirely. Enumerating every
    possible OCR misspelling as a regex alternative doesn't scale — stripping
    diacritics to ASCII once here, centrally, means every pattern below only
    needs its plain-ASCII form and stops caring which specific accent OCR
    guessed wrong.
    """
    nfkd = unicodedata.normalize('NFKD', s)
    ascii_s = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_s.replace('Đ', 'D').replace('đ', 'd')


def ocr_text(image_path: Path) -> str:
    proc = subprocess.run(
        ["tesseract", str(image_path), "-", "-l", "vie"],
        capture_output=True, text=True, check=False,
    )
    return _strip_diacritics(proc.stdout or "")


# Every pattern below is ASCII-only and matched against ocr_text()'s output,
# which is always diacritic-stripped (see _strip_diacritics) — do not add
# accented alternatives here, they can never match and just add noise. The
# dash in "B01-DN" is intentionally `\W?` (any single non-word char or none)
# rather than an enumerated dash-character class: real case (GAS FY2024) had
# it OCR'd as "~" on one page and a normal "-" on the next, and a tilde is
# far from being the only glyph a low-DPI scan can turn a dash into.
MARKER_PATTERNS = {
    'BANK_B02_TCTD_HN': re.compile(r'B\s*0?2\s*/\s*TCTD', re.IGNORECASE),
    'CTCK_B01': re.compile(r'B\s*0?1\s*\W?\s*CTCK', re.IGNORECASE),
    'TT200_DN': re.compile(r'B\s*0?1\s*\W?\s*DN', re.IGNORECASE),
}
# Checked in this order — CTCK/BANK markers are more specific than the bare
# "B01-DN" pattern, so they must be tried first or a bank page whose OCR
# garbled "TCTD" down to noise could wrongly fall through to TT200_DN.
MARKER_ORDER = ['BANK_B02_TCTD_HN', 'CTCK_B01', 'TT200_DN']

ASSET_HEADER_RE = re.compile(r'TAI SAN', re.IGNORECASE)
LIABILITY_HEADER_RE = re.compile(r'NGUON VON|NO PHAI TRA', re.IGNORECASE)
INSURANCE_MARKER_RE = re.compile(r'tai bao hiem', re.IGNORECASE)
# The running page title ("BẢNG CÂN ĐỐI KẾ TOÁN" / CTCK's "BÁO CÁO TÌNH HÌNH
# TÀI CHÍNH") reprints on every page of the statement and is a far more
# reliable start/continuation signal than MARKER_PATTERNS's small italic
# "Mẫu số B01-DN/HN" side-note: real case (GAS FY2024) — that side-note's
# dash OCR'd as "~" on page 9/10 at 120 DPI (matched fine on page 11), so
# scheme-marker-gated detection silently started 2 pages late and captured
# ONLY the liabilities+equity page, dropping the entire assets side with no
# validator signal (V01 can't fire without an assets total to compare against
# — it looked like a clean, complete extraction). Statement-range detection
# below no longer depends on the scheme marker at all; scheme is resolved
# separately from whichever page in the found range does carry a clean marker.
CORP_BS_TITLE_RE = re.compile(r'BANG CAN DOI KE TOAN', re.IGNORECASE)
CTCK_BS_TITLE_RE = re.compile(r'BAO CAO TINH HINH TAI CHINH', re.IGNORECASE)
BS_TITLE_RE = re.compile(f'{CORP_BS_TITLE_RE.pattern}|{CTCK_BS_TITLE_RE.pattern}', re.IGNORECASE)
# BS_TITLE_RE alone false-positives on the table of contents (lists every
# statement's title as an entry) and the audit-opinion page (names the
# statement in prose — "báo cáo tài chính hợp nhất này bao gồm: bảng cân đối
# kế toán hợp nhất..."), both of which precede the real statement pages in
# every filing and have neither content markers in volume. A real statement
# page is dense with dot-grouped VND figures (thousand-separator formatting);
# TOC/prose pages have none. Real case: GAS FY2024 page 7 (audit opinion)
# matched BS_TITLE_RE with 0 such figures — this floor rejects that class of
# false start without rejecting genuine statement pages (which had 35-56).
#
# Raised 5→10 after a second false-positive class (VIX FY2025 page 3): some
# filings bundle a "công văn giải trình chênh lệch lợi nhuận" (a disclosure
# letter explaining the year's profit swing) ahead of the actual statements,
# which is prose but cites enough real VND totals (6 matches) to clear a
# floor of 5, and separately says "tài sản tài chính" (financial assets)
# often enough to match ASSET_HEADER_RE too. Every genuine statement page
# checked so far — GAS/BCM/NVL/VIX among others — has carried at least 14
# money-matches, so 10 keeps a safety margin on both sides without needing a
# third, more specific filter for this one letter's phrasing.
MONEY_RE = re.compile(r'\d{1,3}(?:\.\d{3}){2,}')
MIN_MONEY_MATCHES = 10
# Explicit stop signals: title of the NEXT statement in the filing (income
# statement / cash flow / notes). A balance sheet legitimately runs 2-4 pages
# and keeps repeating "TÀI SẢN"/"NGUỒN VỐN" on each one — capping the range by
# page count alone was too rigid, but running unbounded once let a distant,
# unrelated page (case: FPT FY2024, page 19) get treated as if it were the
# liabilities continuation. Stopping on the next statement's own title is a
# structural signal, not a fragile page-count guess.
#
# "THUYET MINH BAO CAO" is NOT safe to match bare: every single statement page
# ends with the routine footer disclaimer "Bản thuyết minh báo cáo tài chính
# ... là phần KHÔNG THỂ TÁCH RỜI của báo cáo này" ("the notes are an integral
# part of this report") — real case (NVL FY2024): that footer on page 14 (the
# balance sheet's own 2nd page) matched and broke the scan after only 1 page,
# same failure class as GAS's TOC/audit-opinion false start. The genuine notes
# SECTION title never has "KHÔNG THỂ TÁCH RỜI" nearby; the footer disclaimer
# always does — check the text just after the match to tell them apart.
_DISCLAIMER_NEARBY_RE = re.compile(r'khong the tach roi', re.IGNORECASE)


def _has_next_statement_title(txt: str, pattern: 're.Pattern') -> bool:
    for m in pattern.finditer(txt):
        if not _DISCLAIMER_NEARBY_RE.search(txt[m.start():m.start() + 80]):
            return True
    return False


NEXT_STATEMENT_RE = re.compile(
    r'KET QUA HOAT DONG|LUU CHUYEN TIEN TE|THUYET MINH BAO CAO', re.IGNORECASE
)
MAX_STATEMENT_PAGES = 6  # safety valve — no real balance sheet needs more than this

# Income statement (B02) always immediately follows the balance sheet (B01) in
# a VN BCTC PDF — its own title doubles as B01's stop marker above. Its own
# stop marker is deliberately NEXT_STATEMENT_RE minus the KẾT QUẢ pattern
# (that would just match this statement's own title on page 1 of the scan).
IS_TITLE_RE = re.compile(r'KET QUA HOAT DONG', re.IGNORECASE)
IS_STOP_RE = re.compile(r'LUU CHUYEN TIEN TE|THUYET MINH BAO CAO', re.IGNORECASE)


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
    texts = {page_num_from_path(p): ocr_text(p) for p in pages}

    # Pass 1 — find the contiguous page RANGE using content signals only
    # (running title + TÀI SẢN/NGUỒN VỐN headers), independent of whether the
    # small scheme-marker side-note OCR'd cleanly on any given page. See
    # BS_TITLE_RE's comment for why this is decoupled from scheme detection.
    statement_pages: list[int] = []
    is_insurance = False
    started = False
    for pnum in sorted(texts):
        txt = texts[pnum]
        if INSURANCE_MARKER_RE.search(txt):
            is_insurance = True
        has_statement_content = bool(
            (ASSET_HEADER_RE.search(txt) or LIABILITY_HEADER_RE.search(txt) or BS_TITLE_RE.search(txt))
            and len(MONEY_RE.findall(txt)) >= MIN_MONEY_MATCHES
        )
        if not started:
            if has_statement_content:
                started = True
                statement_pages.append(pnum)
            continue
        if _has_next_statement_title(txt, NEXT_STATEMENT_RE):
            break
        if has_statement_content:
            statement_pages.append(pnum)
            if len(statement_pages) >= MAX_STATEMENT_PAGES:
                break
        else:
            break  # a page with none of the content signals ends the run

    # Pass 2 — resolve scheme from ANY page within the found range (a bank/
    # CTCK/TT200 marker only needs to OCR cleanly on ONE of the 1-4 pages,
    # not specifically the first).
    scheme = None
    for pnum in statement_pages:
        for s in MARKER_ORDER:
            if MARKER_PATTERNS[s].search(texts[pnum]):
                scheme = s
                break
        if scheme:
            break

    # Fallback: some filings never print the small "Mẫu số B01-DN/HN"
    # side-note at all (real case: BCM FY2024 — every page in the found range
    # matched CORP_BS_TITLE_RE with dozens of money-figure matches, a
    # completely unambiguous ordinary balance sheet, yet MARKER_PATTERNS
    # never matched on any page because the annotation simply isn't there).
    # The RUNNING TITLE that got the page range started already tells corp
    # apart from CTCK (banks always keep the very distinctive "TCTD" marker
    # and haven't needed this fallback in practice) — use it rather than
    # leaving a well-formed statement unclassified.
    if not scheme:
        if any(CTCK_BS_TITLE_RE.search(texts[p]) for p in statement_pages):
            scheme = 'CTCK_B01'
        elif any(CORP_BS_TITLE_RE.search(texts[p]) for p in statement_pages):
            scheme = 'TT200_DN'

    if scheme == 'TT200_DN' and is_insurance:
        scheme = 'TT200_DN_INSURANCE'

    return {
        'scheme': scheme,
        'pages': statement_pages,
    }


def scan_for_income_statement_pages(pdf_path: Path, scratch: Path, after_page: int,
                                     max_pages: int = 30) -> dict:
    """Same cheap local-OCR approach as scan_for_statement_pages, but for B02
    (income statement). Starts scanning right after the balance sheet's own
    last page so it can't re-match B01 content, and stops at IS_STOP_RE (the
    next statement after B02 — cash flow or notes) rather than a fixed page
    count, for the same reason scan_for_statement_pages does: a real income
    statement is usually 1 page but occasionally 2.

    `scratch` MUST be a directory not already used for another render pass —
    render_pages globs the whole directory for "p-*.png", so reusing the same
    dir as the balance-sheet low-DPI scan would silently re-glob its leftover
    files back in. Caller passes a dedicated subdirectory (see run_one)."""
    pages = render_pages(pdf_path, scratch, after_page + 1, after_page + max_pages, dpi=120)
    statement_pages: list[int] = []
    started = False
    for p in pages:
        pnum = page_num_from_path(p)
        txt = ocr_text(p)
        if not started:
            if IS_TITLE_RE.search(txt) and len(MONEY_RE.findall(txt)) >= MIN_MONEY_MATCHES:
                started = True
                statement_pages.append(pnum)
            continue
        if _has_next_statement_title(txt, IS_STOP_RE):
            break
        statement_pages.append(pnum)
        if len(statement_pages) >= MAX_STATEMENT_PAGES:
            break
    return {'pages': statement_pages}


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


def gemini_extract_lines(image_paths: list[Path], scheme: str, code_dict: list[dict],
                          statement_label: str = 'Bảng cân đối kế toán (balance sheet)') -> list[dict]:
    if not GEMINI_API_KEY:
        print("  [gemini] GEMINI_API_KEY not set, skipping")
        return []

    dict_text = json.dumps(code_dict, ensure_ascii=False)
    prompt = f"""Bạn đang đọc trang "{statement_label}" từ báo cáo tài chính
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
        if re.search(r'trieu', ocr_text(p), re.IGNORECASE):
            return 'VND_million'
    return 'VND'


def insert_rows(ticker: str, scheme: str, rows: list[dict], unit: str,
                 source_url: str, consolidated: bool, period_end: str,
                 report_type: str = 'balance_sheet', update_tracked_companies: bool = True):
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
                VALUES (:ticker, :report_type, :consolidated, :period_end, 'annual',
                 :code, :label, :cur, :pri, :unit, :curv, :priv,
                 :src, 'ocr_llm', false, :src, 'stock', now())
                ON CONFLICT (ticker, report_type, consolidated, period_end, line_code)
                DO UPDATE SET value_current=EXCLUDED.value_current, value_prior=EXCLUDED.value_prior,
                              value_current_vnd=EXCLUDED.value_current_vnd, value_prior_vnd=EXCLUDED.value_prior_vnd,
                              validated=false, crawl_time=now()
            """), dict(ticker=ticker, report_type=report_type, code=code, label=str(r.get('line_label', ''))[:500],
                       cur=cur, pri=pri, unit=unit,
                       curv=(cur * mult) if cur is not None else None,
                       priv=(pri * mult) if pri is not None else None,
                       src=source_url, consolidated=consolidated, period_end=period_end))

        if not update_tracked_companies:
            return

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


def mark_validated(ticker: str, period_end: str, ok_codes: set[str],
                    report_type: str = 'balance_sheet'):
    if not ok_codes:
        return
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE listed_company_financials SET validated = true
            WHERE ticker = :t AND period_end = :p AND report_type = :rt AND line_code = ANY(:codes)
        """), dict(t=ticker, p=period_end, rt=report_type, codes=list(ok_codes)))


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
        insert_rows(ticker, loc['scheme'], rows, unit, url, consolidated, period_end,
                    report_type='balance_sheet')
        bs_codes = {str(r.get('line_code', ''))[:10] for r in rows if r.get('value_current') is not None}

        # ── Income statement — only for schemes the KB has a formula table
        # for (see IS_SCHEME_FOR_BS_SCHEME in validate_financial_statements.py:
        # TT200_DN→B02-DN, BANK_B02_TCTD_HN→B03/TCTD-HN, CTCK_B01→B02-CTCK,
        # TT200_DN_INSURANCE→B02-DN/HN's insurance block, each verified against
        # one real filing 2026-09-15). A scheme with no entry there stays
        # out_of_scope here rather than guessing a P&L structure the KB
        # hasn't seen yet.
        is_codes: set[str] = set()
        if loc['scheme'] in vfs.IS_SCHEME_FOR_BS_SCHEME:
            is_dir = scratch / "is_scan"
            is_dir.mkdir()
            is_loc = scan_for_income_statement_pages(pdf_path, is_dir, after_page=max(loc['pages']))
            if is_loc['pages']:
                print(f"  [B02] pages={is_loc['pages']}")
                is_hi_dir = scratch / "is_hi"
                is_hi_dir.mkdir()
                is_images = render_pages(pdf_path, is_hi_dir, min(is_loc['pages']), max(is_loc['pages']), dpi=300)
                is_scheme = vfs.IS_SCHEME_FOR_BS_SCHEME[loc['scheme']]
                is_code_dict = get_code_dict(is_scheme)
                is_rows = gemini_extract_lines(
                    is_images, is_scheme, is_code_dict,
                    statement_label='Báo cáo kết quả hoạt động kinh doanh (income statement) — số liệu TRONG KỲ, không phải số dư cuối kỳ',
                )
                if is_rows:
                    print(f"  [B02] extracted {len(is_rows)} lines")
                    insert_rows(ticker, is_scheme, is_rows, unit, url, consolidated, period_end,
                                report_type='income_statement', update_tracked_companies=False)
                    is_codes = {str(r.get('line_code', ''))[:10] for r in is_rows if r.get('value_current') is not None}
                else:
                    print("  [B02] gemini returned no rows")
            else:
                print("  [B02] could not locate income statement pages")

        # Run the same mechanical validation the manual pipeline uses, then
        # promote only the rows that pass to validated=true. validate_ticker
        # checks EVERY period_end this ticker has (it may already carry a
        # different year from an earlier run) — filter down to just the
        # period this run just inserted before acting on the result, or a
        # violation on the ticker's OTHER period would wrongly block this one
        # (and marking "ok" codes true would wrongly touch the other period's
        # rows too, which is why mark_validated is also period-scoped). B01
        # and B02 codes don't collide (3-digit vs 2-digit namespaces), so one
        # combined hard_codes set can be safely intersected against each
        # statement's own code set below.
        all_violations = []
        vfs.validate_ticker(engine.connect(), ticker, all_violations)
        violations = [v for v in all_violations if str(v[1]) == period_end]
        hard_codes = {v[3] for v in violations if v[2] in ('SIGN', 'ARITHMETIC', 'V01', 'SCALE')}

        bs_ok = bs_codes - hard_codes
        mark_validated(ticker, period_end, bs_ok, report_type='balance_sheet')
        is_ok = is_codes - hard_codes
        if is_codes:
            mark_validated(ticker, period_end, is_ok, report_type='income_statement')

        hard = [v for v in violations if v[2] in ('SIGN', 'ARITHMETIC', 'V01', 'SCALE')]
        if hard:
            print(f"  {len(hard)} violation(s) — left validated=false:")
            for v in hard:
                print(f"    [{v[2]}] {v[3]}: {v[4]}")
        else:
            print(f"  clean — B01 {len(bs_ok)} rows validated=true"
                  + (f", B02 {len(is_ok)} rows validated=true" if is_codes else ""))


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
