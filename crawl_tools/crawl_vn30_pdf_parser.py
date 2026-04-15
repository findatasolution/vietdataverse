"""
VN30 Financial PDF Parser
Reads PDF URLs from vn30_pdf_index, OCRs/parses with tesseract + Gemini Vision,
extracts key financial figures, and upserts into:
  vn30_income_stmt_quarterly / vn30_balance_sheet_quarterly / vn30_cashflow_quarterly
in CRAWLING_CORP_DB (same DB as KBS crawler).

Extraction strategy:
  - Balance Sheet  → tesseract OCR (keyword matching)
  - Income Stmt    → Gemini Vision (structured prompt) with tesseract fallback
  - Cash Flow      → Gemini Vision (structured prompt) with tesseract fallback

PDF unit convention: raw VND → divide by 1e9 to get tỷ VND (same target as KBS data).

Usage:
  python crawl_vn30_pdf_parser.py                     # parse all 'indexed' PDFs
  python crawl_vn30_pdf_parser.py --ticker BVH        # single ticker
  python crawl_vn30_pdf_parser.py --url <pdf_url>     # single URL (manual test)
  python crawl_vn30_pdf_parser.py --reparse           # re-parse already parsed PDFs
  python crawl_vn30_pdf_parser.py --no-gemini         # use tesseract only
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import re
import time
import base64
import requests
import pytesseract
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from pdf2image import convert_from_bytes
import argparse

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / 'vietdataverse' / 'be' / '.env')

current_date = datetime.now()
print(f"\n{'='*60}")
print(f"VN30 PDF Parser — {current_date.strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*60}")

# PDF index DB (source of URLs + status tracking)
PDF_DB = os.getenv('CRAWLING_CORP_PDF_DB')
if not PDF_DB:
    raise ValueError("CRAWLING_CORP_PDF_DB not set")
pdf_engine = create_engine(PDF_DB)

# Financial data DB (target for parsed figures)
CORP_DB = os.getenv('CRAWLING_CORP_DB')
if not CORP_DB:
    raise ValueError("CRAWLING_CORP_DB not set")
corp_engine = create_engine(CORP_DB)

PDF_TO_TY = 1_000_000_000   # raw VND ÷ 1e9 = tỷ VND

_http = requests.Session()
_http.headers.update({'User-Agent': 'Mozilla/5.0'})

# ── Gemini Vision setup ───────────────────────────────────────────────────────

_GEMINI_AVAILABLE = False
_gemini_model = None

def _init_gemini():
    global _GEMINI_AVAILABLE, _gemini_model
    try:
        import google.generativeai as genai
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("  [Gemini] GEMINI_API_KEY not set — using tesseract only")
            return
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        _GEMINI_AVAILABLE = True
        print("  [Gemini] Initialized (gemini-2.0-flash)")
    except ImportError:
        print("  [Gemini] google-generativeai not installed — using tesseract only")
    except Exception as e:
        print(f"  [Gemini] Init failed: {e} — using tesseract only")

_USE_GEMINI = True   # overridden by --no-gemini flag


_IS_PROMPT = """You are a financial data extractor. This image is a page from a Vietnamese annual financial report (Báo cáo tài chính).

Extract the CONSOLIDATED income statement (Kết quả kinh doanh hợp nhất) figures for the CURRENT YEAR column (leftmost data column):

1. Revenue (Doanh thu thuần / Thu nhập lãi thuần / Doanh thu hoạt động KDBH) — the top-line revenue, in VND
2. Gross profit (Lợi nhuận gộp) — in VND
3. EBIT / Operating profit (Lợi nhuận từ hoạt động kinh doanh / Lợi nhuận trước thuế) — in VND
4. Net income after tax (Lợi nhuận sau thuế TNDN) — in VND
5. Basic EPS (Lãi cơ bản trên cổ phiếu) — in VND/share (typically 100–100,000 range)

Rules:
- Numbers use Vietnamese format: dots as thousands separators (e.g. 1.234.567 = 1,234,567)
- Return null for any field not found on this page
- If this page is NOT an income statement, return all nulls
- Return ONLY valid JSON, no explanation

Return JSON:
{"revenue": <number or null>, "gross_profit": <number or null>, "ebit": <number or null>, "net_income": <number or null>, "eps": <number or null>}"""

_CF_PROMPT = """You are a financial data extractor. This image is a page from a Vietnamese annual financial report.

Extract the CONSOLIDATED cash flow statement (Lưu chuyển tiền tệ hợp nhất) for the CURRENT YEAR column:

1. Net cash from operating activities (Lưu chuyển tiền thuần từ hoạt động kinh doanh) — in VND
2. Net cash from investing activities (Lưu chuyển tiền thuần từ hoạt động đầu tư) — in VND
3. Net cash from financing activities (Lưu chuyển tiền thuần từ hoạt động tài chính) — in VND

Rules:
- Numbers use Vietnamese format: dots as thousands separators
- Negative values may appear as (1.234.567) with parentheses
- Return null for any field not found on this page
- If this page is NOT a cash flow statement, return all nulls
- Return ONLY valid JSON, no explanation

Return JSON:
{"cfo": <number or null>, "cfi": <number or null>, "cff": <number or null>}"""


def _gemini_extract_page(image_pil, prompt: str, retries: int = 3) -> dict | None:
    """Send a PIL image to Gemini Vision with structured prompt. Returns parsed dict or None."""
    import google.generativeai as genai
    import json

    for attempt in range(retries):
        try:
            resp = _gemini_model.generate_content([prompt, image_pil])
            raw = resp.text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            return json.loads(raw)
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower():
                wait = 30 * (attempt + 1)
                print(f"    [Gemini] Rate limit — waiting {wait}s")
                time.sleep(wait)
            else:
                print(f"    [Gemini] Error: {e}")
                return None
    return None


def gemini_extract_is(page_images) -> dict:
    """Use Gemini Vision to extract income statement from relevant pages."""
    result = {'revenue': None, 'gross_profit': None, 'ebit': None, 'net_income': None, 'eps': None}
    if not _GEMINI_AVAILABLE or not _USE_GEMINI:
        return result

    # Try pages classified as IS first, then scan all if needed
    for img in page_images:
        data = _gemini_extract_page(img, _IS_PROMPT)
        if data is None:
            continue
        # Check if Gemini found any meaningful data on this page
        if any(v is not None for v in data.values()):
            # Merge: keep first non-null value for each field
            for k in result:
                if result[k] is None and data.get(k) is not None:
                    result[k] = data[k]
            # If we found revenue + net_income, stop scanning
            if result['revenue'] is not None and result['net_income'] is not None:
                break
        time.sleep(1)   # rate limit courtesy

    return result


def gemini_extract_cf(page_images) -> dict:
    """Use Gemini Vision to extract cash flow from relevant pages."""
    result = {'cfo': None, 'cfi': None, 'cff': None}
    if not _GEMINI_AVAILABLE or not _USE_GEMINI:
        return result

    for img in page_images:
        data = _gemini_extract_page(img, _CF_PROMPT)
        if data is None:
            continue
        if any(v is not None for v in data.values()):
            for k in result:
                if result[k] is None and data.get(k) is not None:
                    result[k] = data[k]
            if result['cfo'] is not None and result['cfi'] is not None:
                break
        time.sleep(1)

    return result


# ── Vietnamese diacritics normalization ───────────────────────────────────────

import unicodedata as _ud

def _norm(text: str) -> str:
    """Strip Vietnamese diacritics → ASCII-ish lowercase for OCR-tolerant matching.
    'tổng cộng tài sản' → 'tong cong tai san'
    'kết quả hoạt động' → 'ket qua hoat dong'
    """
    text = text.replace('đ', 'd').replace('Đ', 'D')
    decomposed = _ud.normalize('NFD', text)
    return ''.join(c for c in decomposed if _ud.category(c) != 'Mn').lower()


# ── Number parsing ────────────────────────────────────────────────────────────

def _parse_vn_number(s: str) -> float | None:
    """Parse Vietnamese number format. Handles:
    - 44.767.937.163.527  → dots as thousands separators
    - 5.844.707.147,758   → OCR mixed: trailing comma ALSO a thousands sep if 3 digits
    - (1.234.567)         → negative
    """
    if not s:
        return None
    s = s.strip().replace(' ', '')
    is_neg = s.startswith('(') and s.endswith(')')
    if is_neg:
        s = s[1:-1]
    # Remove any separator (. or ,) that is followed by exactly 3 digits then
    # another separator, whitespace, or end — i.e., it's a thousands separator.
    s = re.sub(r'[.,](?=\d{3}(?:[.,\s]|$))', '', s)
    # Any remaining comma → decimal point
    s = s.replace(',', '.')
    # Strip non-numeric except dot and minus
    s = re.sub(r'[^\d.\-]', '', s)
    try:
        val = float(s)
        return -val if is_neg else val
    except ValueError:
        return None


def _to_ty(raw_vnd: float | None) -> float | None:
    """Convert raw VND (from PDF) → tỷ VND for DB storage."""
    if raw_vnd is None:
        return None
    return raw_vnd / PDF_TO_TY


def _extract_numbers(line: str) -> list[float]:
    """Extract all numbers from a line of OCR text."""
    # Pattern: number with dots/commas, possibly parenthesized
    pattern = r'\([\d.,\s]+\)|[\d]{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?'
    matches = re.findall(pattern, line)
    nums = []
    for m in matches:
        v = _parse_vn_number(m)
        if v is not None and abs(v) > 0:
            nums.append(v)
    return nums


# ── OCR ───────────────────────────────────────────────────────────────────────

def ocr_pdf(pdf_bytes: bytes, dpi: int = 200) -> tuple[list[str], list]:
    """Convert PDF to images and OCR each page.
    Returns (page_texts, page_images) — texts for tesseract keyword matching,
    images (PIL) for Gemini Vision.
    """
    pages = convert_from_bytes(pdf_bytes, dpi=dpi)
    texts = []
    for page in pages:
        text = pytesseract.image_to_string(page, lang='vie+eng', config='--psm 6')
        texts.append(text)
    return texts, pages


def download_pdf(url: str) -> bytes | None:
    try:
        r = _http.get(url, timeout=60)
        if r.ok and len(r.content) > 10_000:
            return r.content
        print(f"  Download failed: {r.status_code} / {len(r.content)} bytes")
        return None
    except Exception as e:
        print(f"  Download error: {e}")
        return None


# ── Page classification ───────────────────────────────────────────────────────

# All keywords are stored normalized (no diacritics) for OCR-tolerant matching
_BS_KEYWORDS = [
    'bang can doi ke toan', 'can doi ke toan', 'balance sheet',
    'tong cong tai san', 'tong cong nguon von',
]
_IS_KEYWORDS = [
    'ket qua hoat dong kinh doanh', 'bao cao ket qua',
    'income statement', 'profit and loss',
    'doanh thu thuan', 'loi nhuan sau thue',
    'ket qua kinh doanh',
]
_CF_KEYWORDS = [
    'luu chuyen tien te', 'luu chuyen tien',
    'cash flow', 'tien thuan tu hoat dong',
    'luu chuyen tien thuan',
]

def _classify_page(text: str) -> str:
    t = _norm(text)
    if any(k in t for k in _BS_KEYWORDS):
        return 'BS'
    if any(k in t for k in _IS_KEYWORDS):
        return 'IS'
    if any(k in t for k in _CF_KEYWORDS):
        return 'CF'
    return 'OTHER'


# ── Line-item extraction ──────────────────────────────────────────────────────

def _find_line_value(lines: list[str], *keywords,
                     min_val: float = 1_000_000,
                     eps_mode: bool = False) -> float | None:
    """Scan lines for first line matching any keyword (diacritics-normalized, OCR-tolerant).
    Returns the largest number on that line that exceeds min_val.
    eps_mode=True: return largest number in [100, 100_000] range (EPS in VND/share).
    """
    norm_kws = [_norm(k) for k in keywords]
    for line in lines:
        lt = _norm(line)
        if not any(kw in lt or _fuzzy_match(lt, kw) for kw in norm_kws):
            continue
        nums = _extract_numbers(line)
        if not nums:
            continue
        if eps_mode:
            # EPS: first number in [100, 100_000] range (skip line codes < 100)
            for n in nums:
                if 100 <= abs(n) <= 100_000:
                    return n
            return None
        else:
            # Financial figures: first number >= min_val (current-year value comes first)
            for n in nums:
                if abs(n) >= min_val:
                    return n
            return None
    return None


def _fuzzy_match(text: str, keyword: str, threshold: float = 0.75) -> bool:
    """Check if >threshold fraction of keyword words appear in text."""
    words = [w for w in keyword.split() if len(w) >= 3]
    if not words:
        return False
    return sum(1 for w in words if w in text) / len(words) >= threshold


def extract_balance_sheet(page_texts: list[str]) -> dict:
    """Extract key balance sheet figures from OCR'd text."""
    bs_lines = []
    for text in page_texts:
        if _classify_page(text) == 'BS':
            bs_lines.extend(text.split('\n'))
    if not bs_lines:
        return {}

    total_assets = _find_line_value(bs_lines,
        'tổng cộng tài sản', 'tong cong tai san', 'total assets', 'tổng tài sản')

    total_liab = _find_line_value(bs_lines,
        'nợ phải trả', 'no phai tra', 'total liabilities', 'tổng nợ phải trả',
        'a. no phai tra', 'a no phai tra')

    equity = _find_line_value(bs_lines,
        'vốn chủ sở hữu', 'von chu so huu', "shareholders equity",
        'b. von chu so huu', 'b von chu so huu', 'tổng vốn chủ sở hữu')

    cash = _find_line_value(bs_lines,
        'tiền và các khoản tương đương tiền',
        'tien va cac khoan tuong duong tien',
        'cash and cash equivalents', 'tien mat va tuong duong tien',
        'tien va tuong duong tien', 'tien mat tien gui')

    return {
        'total_assets':      _to_ty(total_assets),
        'total_liabilities': _to_ty(total_liab),
        'equity':            _to_ty(equity),
        'cash':              _to_ty(cash),
    }


def extract_income_stmt(page_texts: list[str], page_images: list = None) -> dict:
    """Extract income statement.
    Gemini Vision primary (if available), tesseract fallback.
    """
    # ── Gemini path ──────────────────────────────────────────────────────────
    if _GEMINI_AVAILABLE and _USE_GEMINI and page_images:
        # Send only IS-classified pages to Gemini (faster + more focused)
        is_images = [img for txt, img in zip(page_texts, page_images)
                     if _classify_page(txt) == 'IS']
        # If classifier found nothing, send all pages (Gemini will filter)
        images_to_send = is_images if is_images else page_images
        gem = gemini_extract_is(images_to_send)

        # Convert Gemini raw VND numbers → tỷ, eps stays as-is
        result = {
            'revenue':      _to_ty(gem.get('revenue')),
            'gross_profit': _to_ty(gem.get('gross_profit')),
            'ebit':         _to_ty(gem.get('ebit')),
            'net_income':   _to_ty(gem.get('net_income')),
            'eps':          gem.get('eps'),
        }
        if any(v is not None for v in result.values()):
            return result

    # ── Tesseract fallback ───────────────────────────────────────────────────
    is_lines = []
    for text in page_texts:
        if _classify_page(text) == 'IS':
            is_lines.extend(text.split('\n'))

    all_lines = []
    for text in page_texts:
        all_lines.extend(text.split('\n'))

    search_lines = is_lines if is_lines else all_lines

    revenue = (
        _find_line_value(search_lines, 'doanh thu thuan ve ban hang', 'doanh thu thuan', 'net revenue')
        or _find_line_value(search_lines, 'thu nhap lai thuan', 'thu nhap lai va tuong duong', 'net interest income')
        or _find_line_value(search_lines, 'doanh thu hoat dong kinh doanh bao hiem', 'thu phi bao hiem goc')
        or _find_line_value(search_lines, 'tong doanh thu', 'total revenue', 'tong thu nhap')
    )
    gross = (
        _find_line_value(search_lines, 'loi nhuan gop ve ban hang', 'loi nhuan gop', 'gross profit')
        or _find_line_value(search_lines, 'loi nhuan gop hoat dong kinh doanh bao hiem')
        or _find_line_value(search_lines, 'loi nhuan hoat dong kinh doanh bao hiem')
    )
    ebit = (
        _find_line_value(search_lines, 'loi nhuan tu hoat dong kinh doanh', 'loi nhuan hoat dong kinh doanh')
        or _find_line_value(search_lines, 'tong loi nhuan ke toan truoc thue',
                             'loi nhuan ke toan truoc thue', 'profit before tax', 'loi nhuan truoc thue')
    )
    net_income = _find_line_value(search_lines,
        'loi nhuan sau thue thu nhap doanh nghiep',
        'loi nhuan sau thue', 'profit after tax', 'net profit after tax')
    eps = _find_line_value(all_lines,
        'lai co ban tren co phieu', 'lai co ban', 'earnings per share', 'eps',
        'lai suat co ban', 'lai tren co phieu', eps_mode=True)

    return {
        'revenue':      _to_ty(revenue),
        'gross_profit': _to_ty(gross),
        'ebit':         _to_ty(ebit),
        'net_income':   _to_ty(net_income),
        'eps':          eps,
    }


def extract_cashflow(page_texts: list[str], page_images: list = None) -> dict:
    """Extract cash flow statement.
    Gemini Vision primary (if available), tesseract fallback.
    """
    # ── Gemini path ──────────────────────────────────────────────────────────
    if _GEMINI_AVAILABLE and _USE_GEMINI and page_images:
        cf_images = [img for txt, img in zip(page_texts, page_images)
                     if _classify_page(txt) == 'CF']
        images_to_send = cf_images if cf_images else page_images
        gem = gemini_extract_cf(images_to_send)
        cfo_ty = _to_ty(gem.get('cfo'))
        cfi_ty = _to_ty(gem.get('cfi'))
        result = {
            'cfo': cfo_ty,
            'cfi': cfi_ty,
            'cff': _to_ty(gem.get('cff')),
            'free_cashflow': (cfo_ty + cfi_ty) if (cfo_ty is not None and cfi_ty is not None) else None,
        }
        if any(v is not None for v in result.values()):
            return result

    # ── Tesseract fallback ───────────────────────────────────────────────────
    cf_lines = []
    for text in page_texts:
        if _classify_page(text) == 'CF':
            cf_lines.extend(text.split('\n'))

    all_lines = []
    for text in page_texts:
        all_lines.extend(text.split('\n'))

    search_lines = cf_lines if cf_lines else all_lines

    cfo = _find_line_value(search_lines,
        'luu chuyen tien thuan tu hoat dong kinh doanh',
        'tien thuan tu hoat dong kinh doanh',
        'net cash flows from operating', 'net cash from operating',
        'luu chuyen tien tu hoat dong kinh doanh')

    cfi = _find_line_value(search_lines,
        'luu chuyen tien thuan tu hoat dong dau tu',
        'tien thuan tu hoat dong dau tu',
        'net cash flows from investing', 'net cash from investing')

    cff = _find_line_value(search_lines,
        'luu chuyen tien thuan tu hoat dong tai chinh',
        'tien thuan tu hoat dong tai chinh',
        'net cash flows from financing', 'net cash from financing')

    cfo_ty = _to_ty(cfo)
    cfi_ty = _to_ty(cfi)
    return {
        'cfo': cfo_ty,
        'cfi': cfi_ty,
        'cff': _to_ty(cff),
        'free_cashflow': (cfo_ty + cfi_ty) if (cfo_ty is not None and cfi_ty is not None) else None,
    }


# ── DB upserts ────────────────────────────────────────────────────────────────

def upsert_bs(ticker, year, quarter, fields, crawl_time):
    if not any(v is not None for v in fields.values()):
        return
    with corp_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn30_balance_sheet_quarterly
                (ticker, year, quarter, total_assets, total_liabilities, equity, cash, crawl_time, source, group_name)
            VALUES (:ticker, :year, :quarter, :total_assets, :total_liabilities, :equity, :cash, :crawl_time, 'pdf_parser', 'stock')
            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                total_assets      = COALESCE(EXCLUDED.total_assets,      vn30_balance_sheet_quarterly.total_assets),
                total_liabilities = COALESCE(EXCLUDED.total_liabilities, vn30_balance_sheet_quarterly.total_liabilities),
                equity            = COALESCE(EXCLUDED.equity,            vn30_balance_sheet_quarterly.equity),
                cash              = COALESCE(EXCLUDED.cash,              vn30_balance_sheet_quarterly.cash),
                crawl_time        = EXCLUDED.crawl_time
        """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})
        conn.commit()


def upsert_is(ticker, year, quarter, fields, crawl_time):
    if not any(v is not None for v in fields.values()):
        return
    with corp_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn30_income_stmt_quarterly
                (ticker, year, quarter, revenue, gross_profit, ebit, net_income, eps, crawl_time, source, group_name)
            VALUES (:ticker, :year, :quarter, :revenue, :gross_profit, :ebit, :net_income, :eps, :crawl_time, 'pdf_parser', 'stock')
            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                revenue      = COALESCE(EXCLUDED.revenue,      vn30_income_stmt_quarterly.revenue),
                gross_profit = COALESCE(EXCLUDED.gross_profit, vn30_income_stmt_quarterly.gross_profit),
                ebit         = COALESCE(EXCLUDED.ebit,         vn30_income_stmt_quarterly.ebit),
                net_income   = COALESCE(EXCLUDED.net_income,   vn30_income_stmt_quarterly.net_income),
                eps          = COALESCE(EXCLUDED.eps,          vn30_income_stmt_quarterly.eps),
                crawl_time   = EXCLUDED.crawl_time
        """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})
        conn.commit()


def upsert_cf(ticker, year, quarter, fields, crawl_time):
    if not any(v is not None for v in fields.values()):
        return
    with corp_engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO vn30_cashflow_quarterly
                (ticker, year, quarter, cfo, cfi, cff, free_cashflow, crawl_time, source, group_name)
            VALUES (:ticker, :year, :quarter, :cfo, :cfi, :cff, :free_cashflow, :crawl_time, 'pdf_parser', 'stock')
            ON CONFLICT (ticker, year, quarter) DO UPDATE SET
                cfo           = COALESCE(EXCLUDED.cfo,           vn30_cashflow_quarterly.cfo),
                cfi           = COALESCE(EXCLUDED.cfi,           vn30_cashflow_quarterly.cfi),
                cff           = COALESCE(EXCLUDED.cff,           vn30_cashflow_quarterly.cff),
                free_cashflow = COALESCE(EXCLUDED.free_cashflow, vn30_cashflow_quarterly.free_cashflow),
                crawl_time    = EXCLUDED.crawl_time
        """), {'ticker': ticker, 'year': year, 'quarter': quarter, **fields, 'crawl_time': crawl_time})
        conn.commit()


def mark_pdf_status(pdf_id: int, status: str, error: str = None):
    with pdf_engine.connect() as conn:
        conn.execute(text("""
            UPDATE vn30_pdf_index
            SET status = :status, parse_error = :error, parsed_time = NOW()
            WHERE id = :id
        """), {'id': pdf_id, 'status': status, 'error': error})
        conn.commit()


# ── Parse one PDF ─────────────────────────────────────────────────────────────

def parse_pdf(pdf_id: int, ticker: str, year: int, quarter: int | None, pdf_url: str,
              crawl_time: datetime, verbose: bool = True) -> bool:
    """Download, OCR, extract, and upsert one PDF. Returns True on success."""
    q = quarter or 4     # annual report → treat as Q4 (year-end snapshot)
    label = f'{ticker} {year} Q{q}' if quarter else f'{ticker} {year} (annual)'
    if verbose:
        print(f"  Parsing {label}  {pdf_url[-50:]}")

    # Download
    pdf_bytes = download_pdf(pdf_url)
    if not pdf_bytes:
        mark_pdf_status(pdf_id, 'error', 'download_failed')
        return False

    # OCR
    try:
        page_texts, page_images = ocr_pdf(pdf_bytes)
    except Exception as e:
        mark_pdf_status(pdf_id, 'error', f'ocr_failed: {e}')
        print(f"    OCR error: {e}")
        return False

    if verbose:
        print(f"    OCR done: {len(page_texts)} pages  [Gemini={'on' if (_GEMINI_AVAILABLE and _USE_GEMINI) else 'off'}]")

    # Extract
    try:
        bs = extract_balance_sheet(page_texts)
        inc = extract_income_stmt(page_texts, page_images)
        cf = extract_cashflow(page_texts, page_images)
    except Exception as e:
        mark_pdf_status(pdf_id, 'error', f'extract_failed: {e}')
        print(f"    Extract error: {e}")
        return False

    if verbose:
        print(f"    BS  : total_assets={bs.get('total_assets'):.0f} tỷ  equity={bs.get('equity'):.0f} tỷ" if bs.get('total_assets') else "    BS  : no data")
        print(f"    IS  : revenue={inc.get('revenue'):.0f} tỷ  net_income={inc.get('net_income'):.0f} tỷ  eps={inc.get('eps')}" if inc.get('net_income') else "    IS  : no data")
        print(f"    CF  : cfo={cf.get('cfo'):.0f} tỷ  cfi={cf.get('cfi'):.0f} tỷ" if cf.get('cfo') else "    CF  : no data")

    # Upsert — use COALESCE so PDF data fills gaps without overwriting KBS data
    has_any = False
    try:
        if any(v is not None for v in bs.values()):
            upsert_bs(ticker, year, q, bs, crawl_time)
            has_any = True
        if any(v is not None for v in inc.values()):
            upsert_is(ticker, year, q, inc, crawl_time)
            has_any = True
        if any(v is not None for v in cf.values()):
            upsert_cf(ticker, year, q, cf, crawl_time)
            has_any = True
    except Exception as e:
        mark_pdf_status(pdf_id, 'error', f'db_upsert_failed: {e}')
        print(f"    DB error: {e}")
        return False

    status = 'parsed' if has_any else 'error'
    mark_pdf_status(pdf_id, status, None if has_any else 'no_data_extracted')
    return has_any


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _USE_GEMINI
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker',    help='Process single ticker only')
    parser.add_argument('--url',       help='Parse a single URL directly (bypass index)')
    parser.add_argument('--reparse',   action='store_true', help='Re-parse already parsed PDFs')
    parser.add_argument('--no-gemini', action='store_true', help='Use tesseract only (skip Gemini)')
    args = parser.parse_args()

    if args.no_gemini:
        _USE_GEMINI = False
        print("  [Gemini] Disabled via --no-gemini flag")
    else:
        _init_gemini()

    crawl_time = datetime.now()

    # Single URL mode
    if args.url:
        print(f"Single URL mode: {args.url}")
        # Insert into index first if not there
        with pdf_engine.connect() as conn:
            row = conn.execute(text(
                "SELECT id, ticker, year, quarter FROM vn30_pdf_index WHERE pdf_url = :url"
            ), {'url': args.url}).fetchone()
        if not row:
            print("URL not in index — please add it first or run crawl_vn30_pdf_index.py")
            return
        parse_pdf(row[0], row[1], row[2], row[3], args.url, crawl_time)
        return

    # Fetch pending PDFs from index
    status_filter = "('indexed')" if not args.reparse else "('indexed', 'parsed', 'error')"
    ticker_filter = f"AND ticker = '{args.ticker}'" if args.ticker else ""

    with pdf_engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, ticker, year, quarter, pdf_url
            FROM vn30_pdf_index
            WHERE status IN {status_filter}
              AND report_type = 'ALL'
              {ticker_filter}
            ORDER BY ticker, year
        """)).fetchall()

    print(f"PDFs to parse: {len(rows)}")
    success = 0
    errors = 0

    for row in rows:
        pdf_id, ticker, year, quarter, pdf_url = row
        ok = parse_pdf(pdf_id, ticker, year, quarter, pdf_url, crawl_time)
        if ok:
            success += 1
        else:
            errors += 1
        time.sleep(1)   # be polite

    print(f"\n{'='*60}")
    print(f"PDF Parser done. Success: {success}, Errors: {errors}")
    print(f"Completed at {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
