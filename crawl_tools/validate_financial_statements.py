"""
Validate rows in listed_company_financials (CRAWLING_CORP_DB) against
bctc_line_code_dict — mechanical checks any crawler/agent should run
AFTER inserting a company's BCTC data, before marking it done.

Exists so a weaker model doing OCR extraction doesn't have to reason its way
through sign conventions or arithmetic by judgment alone — run this script and
fix whatever it reports. See .claude/skills/financial_statement_extraction/SKILL.md
Bước 3.5 for when this runs in the workflow, and
.claude/knowledge/financial_statements/tt200_ma_ke_toan_bctc.md §9 R05 /
nganhang_chungkhoan_baohiem_ma_ke_toan_bctc.md §16 for the accounting rules
this encodes.

Usage:
    python crawl_tools/validate_financial_statements.py            # all tickers
    python crawl_tools/validate_financial_statements.py VCB FPT    # specific tickers

Exit code: 0 if no violations, 1 if any found (fails a pipeline step on purpose).
"""

import sys
from pathlib import Path
from decimal import Decimal

from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

DB_URL = os.getenv('CRAWLING_CORP_DB')
if not DB_URL:
    sys.exit("CRAWLING_CORP_DB not set")

engine = create_engine(DB_URL)

# Total-assets code / total-liabilities-plus-equity code per scheme, for the V01
# check (Assets = Liabilities + Equity). Some schemes print the combined
# liabilities+equity total as a single code (TOTAL_COMBINED); others need two
# codes summed (TOTAL_LIAB + TOTAL_EQUITY).
V01_CODES = {
    'TT200_DN':           {'assets': '270', 'combined': '440'},
    'TT200_DN_INSURANCE': {'assets': '270', 'combined': '440'},
    'BANK_B02_TCTD_HN':   {'assets': 'TS', 'liab': 'NPT', 'equity': 'VCSH'},
    'CTCK_B01':           {'assets': 'TS', 'combined': 'NPTVCSH'},
}

# Reasonable absolute VND bounds for a "total assets"-type row — catches an
# obvious unit mistake (e.g. million stored as if it were raw VND) without
# hardcoding a suspiciously narrow range per company.
PLAUSIBLE_TOTAL_VND_MIN = Decimal('1000000000')          # 1 tỷ VND
PLAUSIBLE_TOTAL_VND_MAX = Decimal('20000000000000000')   # 20 triệu tỷ VND (20 quadrillion)

REL_TOLERANCE = Decimal('0.0001')   # 0.01% — matches skill's "chấp nhận sai số nhỏ" rule
ABS_TOLERANCE_FLOOR = Decimal('1000')  # never flag a sub-1000-VND rounding gap

# TT200_DN_INSURANCE only stores the INSURANCE-SPECIFIC delta (190, and the
# note on 330/410) — for every other code it inherits TT200_DN's definitions
# and parent/child map wholesale. Without this, the validator can't see that
# 110/120/130/140/150 are children of 100 for an insurance company, and wrongly
# flags "100 != 190" as an arithmetic error.
SCHEME_INHERITANCE = {
    'TT200_DN_INSURANCE': 'TT200_DN',
}

# Which balance-sheet scheme's income statement uses which bctc_line_code_dict
# scheme. Income-statement (B02) line relationships are explicit add/subtract
# formulas (V03/V04 in tt200_ma_ke_toan_bctc.md §5), NOT a generic "parent =
# sum of children" — B02 deduction/expense lines (02, 11, 22, 25, 26, 32, 51,
# 52) are conventionally stored POSITIVE in the source document with the
# formula itself doing the subtraction, unlike balance-sheet contra accounts
# which are stored negative in the ledger. Reusing the generic parent/child
# summation engine for B02 would require lying about sign_convention (marking
# real positive expenses as sign_convention='negative' for validation
# purposes only), which would then wrongly fail the SIGN check on every
# correctly-extracted row. Hence a separate formula table instead.
#
# Only TT200_DN (ordinary corporates) is mapped — banks/CTCK/insurance have a
# structurally different P&L (interest income/expense breakdown for banks,
# brokerage/margin/investment income for CTCK) that is not yet in the KB.
# Crawling B02 for those schemes must stay out_of_scope until researched, not
# guessed from the TT200 shape.
IS_SCHEME_FOR_BS_SCHEME = {
    'TT200_DN': 'TT200_DN_B02',
}

# (target_code, [(operand_code, +1 or -1, optional), ...]) — matches
# tt200_ma_ke_toan_bctc.md §5's "Cách xác định / quan hệ" column (V03/V04 in
# §10.1). `optional=True` means "contributes 0 if absent, don't downgrade to
# INFO_NULL for its absence" — code 24 ("Phần lãi trong công ty liên doanh,
# liên kết", equity-method share of associate/JV profit) is NOT in the base
# TT200 B02 KB at all; it only appears for holding companies that actually
# hold associate/JV investments (real case: GAS FY2024). A company without
# such investments simply never has this line — that's the normal case, not
# missing data — so it must default to zero contribution rather than forcing
# every ordinary company's "30" check into a permanent INFO_NULL.
# GAS/HPG print every B02 deduction/expense line as a plain POSITIVE number
# and let the formula's own "-" do the subtracting. PDR (real case, FY2024)
# instead prints every one of those SAME lines in parentheses (stored
# negative) — including "52 Thu nhập (chi phí) thuế TNDN hoãn lại", whose
# formula weight is -1 for the same structural reason (it sits in the
# "expense" family per the KB), even though ITS OWN sign varies year to year
# (a genuine tax benefit vs. expense) — the flip is about which SUBTRACTION
# CONVENTION the whole statement uses, not about that one line's current-year
# direction. Detect the convention from code '11' (Giá vốn hàng bán — always
# present, always a true cost, sign is presentation-only) and flip every
# operand whose TEMPLATE weight is -1 (i.e., every item the formula was
# written to subtract) so `X - cost` becomes `X + (-cost)` — the same
# subtraction, regardless of which way the source prints it. Operands with a
# template weight of +1 (01, 21, 24, 31 — items the formula ADDS, whose sign
# is always genuine economic direction, never a presentation artifact) are
# never touched.
def _income_statement_orientation_negative(by_code) -> bool:
    row = by_code.get('11')
    return row is not None and row[2] is not None and row[2] < 0


IS_FORMULAS = {
    'TT200_DN_B02': [
        ('10', [('01', 1, False), ('02', -1, False)]),
        ('20', [('10', 1, False), ('11', -1, False)]),
        ('30', [('20', 1, False), ('21', 1, False), ('22', -1, False),
                 ('24', 1, True), ('25', -1, False), ('26', -1, False)]),
        ('40', [('31', 1, False), ('32', -1, False)]),
        ('50', [('30', 1, False), ('40', 1, False)]),
        ('60', [('50', 1, False), ('51', -1, False), ('52', -1, False)]),
    ],
}


def close_enough(a: Decimal, b: Decimal) -> bool:
    if a is None or b is None:
        return False
    diff = abs(a - b)
    tol = max(ABS_TOLERANCE_FLOOR, abs(b) * REL_TOLERANCE)
    return diff <= tol


def get_tickers(conn, requested):
    if requested:
        return requested
    rows = conn.execute(text(
        "SELECT DISTINCT ticker FROM listed_company_financials ORDER BY ticker"
    )).fetchall()
    return [r[0] for r in rows]


def validate_ticker(conn, ticker, violations):
    """Appends one 5-tuple per finding: (ticker, period_end, kind, code, detail).

    A ticker can carry MULTIPLE period_end values (e.g. FY2024 and FY2025
    crawled separately) — this validates each period independently and never
    mixes rows across periods. An earlier version selected rows by ticker
    alone with no period_end filter, so once a ticker had two periods in the
    table, `by_code` silently overwrote one period's row with the other's
    (whichever the query happened to return last) and compared mismatched
    years against each other — caught via a real run: FPT FY2024's own "100"
    total was checked against child codes actually holding FY2025 values.
    """
    scheme_row = conn.execute(text(
        "SELECT code_scheme FROM tracked_companies WHERE ticker = :t"
    ), dict(t=ticker)).fetchone()
    if not scheme_row or not scheme_row[0]:
        violations.append((ticker, None, 'SCHEME', '—',
                            f"{ticker} không có trong tracked_companies hoặc thiếu code_scheme — "
                            f"thêm 1 dòng vào tracked_companies trước khi validate."))
        return
    scheme = scheme_row[0]

    period_rows = conn.execute(text(
        "SELECT DISTINCT period_end, report_type FROM listed_company_financials "
        "WHERE ticker = :t ORDER BY period_end"
    ), dict(t=ticker)).fetchall()
    for period_end, report_type in period_rows:
        if report_type == 'income_statement':
            validate_income_statement_period(conn, ticker, scheme, period_end, violations)
        else:
            validate_ticker_period(conn, ticker, scheme, period_end, violations)


def validate_ticker_period(conn, ticker, scheme, period_end, violations):
    """Balance sheet (B01) only — see module docstring's report_type note.
    Scoped with report_type='balance_sheet' so an income-statement row for the
    same ticker/period_end can never leak into this function's by_code map;
    B02's line_code namespace (01, 02, 10, 11, 20...) is short enough to
    plausibly collide with a mis-keyed B01 code, and the two statements' sign
    conventions/parent-child semantics are incompatible (see IS_FORMULAS)."""
    rows = conn.execute(text(
        "SELECT line_code, line_label, value_current, value_current_vnd, unit "
        "FROM listed_company_financials WHERE ticker = :t AND period_end = :p "
        "AND report_type = 'balance_sheet'"
    ), dict(t=ticker, p=period_end)).fetchall()
    by_code = {r[0]: r for r in rows}

    # Base scheme first (if this scheme inherits one), then the scheme's own
    # rows layered on top — own rows win on code collisions (e.g. 100/330/410
    # in TT200_DN_INSURANCE override the TT200_DN base for those codes).
    base_scheme = SCHEME_INHERITANCE.get(scheme)
    schemes_to_load = ([base_scheme] if base_scheme else []) + [scheme]
    sign_by_code = {}
    parent_by_code = {}
    full_children_of = {}
    for s in schemes_to_load:
        dict_rows = conn.execute(text(
            "SELECT line_code, parent_code, sign_convention FROM bctc_line_code_dict "
            "WHERE code_scheme = :s"
        ), dict(s=s)).fetchall()
        for code, parent, conv in dict_rows:
            sign_by_code[code] = conv
            parent_by_code[code] = parent

    # 1. Sign convention
    for code, (_, label, cur, _, _) in by_code.items():
        if cur is None:
            continue
        conv = sign_by_code.get(code)
        if conv == 'negative' and cur > 0:
            violations.append((ticker, period_end, 'SIGN', code,
                                f"{code} ({label}) = {cur} — PHẢI ÂM theo bctc_line_code_dict "
                                f"(scheme={scheme}) nhưng đang dương."))
        elif conv == 'positive' and cur < 0:
            violations.append((ticker, period_end, 'SIGN', code,
                                f"{code} ({label}) = {cur} — PHẢI DƯƠNG theo bctc_line_code_dict "
                                f"(scheme={scheme}) nhưng đang âm."))

    # 2. Parent = sum of children actually present for this ticker
    children_of = {}
    for code, parent in parent_by_code.items():
        if parent:
            children_of.setdefault(parent, []).append(code)

    for parent_code, child_codes in children_of.items():
        if parent_code not in by_code:
            continue
        present_children = [c for c in child_codes if c in by_code]
        if not present_children:
            continue
        child_sum = sum(
            (by_code[c][2] for c in present_children if by_code[c][2] is not None),
            Decimal(0),
        )
        parent_val = by_code[parent_code][2]
        if parent_val is None:
            continue
        if close_enough(child_sum, parent_val):
            continue
        missing = [c for c in child_codes if c not in by_code]
        if missing:
            # Can't tell "real error" from "chưa trích hết mã con" — only warn,
            # don't fail the pipeline over an incomplete-by-design extraction.
            violations.append((ticker, period_end, 'INFO_NULL', parent_code,
                                f"{parent_code} = {parent_val}, tổng {len(present_children)} mã con có "
                                f"({', '.join(present_children)}) = {child_sum} (lệch "
                                f"{abs(child_sum - parent_val)}) — nhưng còn thiếu mã con "
                                f"{', '.join(missing)} chưa trích, nên KHÔNG kết luận là sai số học."))
        else:
            violations.append((ticker, period_end, 'ARITHMETIC', parent_code,
                                f"{parent_code} = {parent_val}, đủ mã con ({', '.join(present_children)}) "
                                f"nhưng tổng = {child_sum} (lệch {abs(child_sum - parent_val)}) — "
                                f"ĐÂY LÀ LỖI THẬT, không phải do thiếu trích."))

    # 3. V01 — Assets = Liabilities + Equity
    v01 = V01_CODES.get(scheme)
    if v01:
        assets_row = by_code.get(v01['assets'])
        assets_val = assets_row[2] if assets_row else None
        if 'combined' in v01:
            combined_row = by_code.get(v01['combined'])
            combined_val = combined_row[2] if combined_row else None
            if assets_val is not None and combined_val is not None:
                if not close_enough(assets_val, combined_val):
                    violations.append((ticker, period_end, 'V01', v01['assets'],
                                        f"Tổng tài sản ({v01['assets']}={assets_val}) != "
                                        f"Tổng nguồn vốn ({v01['combined']}={combined_val})."))
        else:
            liab_row = by_code.get(v01['liab'])
            equity_row = by_code.get(v01['equity'])
            if assets_val is not None and liab_row and equity_row and liab_row[2] is not None and equity_row[2] is not None:
                combined_val = liab_row[2] + equity_row[2]
                if not close_enough(assets_val, combined_val):
                    violations.append((ticker, period_end, 'V01', v01['assets'],
                                        f"Tổng tài sản ({v01['assets']}={assets_val}) != "
                                        f"{v01['liab']}+{v01['equity']} ({combined_val})."))

    # 4. Scale sanity on the assets total, using the normalized VND value
    if v01:
        assets_row = by_code.get(v01['assets'])
        if assets_row and assets_row[3] is not None:
            vnd = assets_row[3]
            if not (PLAUSIBLE_TOTAL_VND_MIN <= vnd <= PLAUSIBLE_TOTAL_VND_MAX):
                violations.append((ticker, period_end, 'SCALE', v01['assets'],
                                    f"Tổng tài sản quy đổi VNĐ = {vnd} — nằm ngoài khoảng hợp lý "
                                    f"[{PLAUSIBLE_TOTAL_VND_MIN}, {PLAUSIBLE_TOTAL_VND_MAX}], "
                                    f"nghi ngờ lỗi đơn vị (unit='{assets_row[4]}')."))

    # 5. NULL visibility (not necessarily an error — report as INFO, doesn't fail exit code)
    null_codes = [c for c, r in by_code.items() if r[2] is None]
    if null_codes:
        violations.append((ticker, period_end, 'INFO_NULL', ','.join(null_codes),
                            f"value_current NULL ở các mã: {', '.join(null_codes)} — "
                            f"kiểm tra đây có phải khoảng trống đã biết/chủ đích không."))


def validate_income_statement_period(conn, ticker, bs_scheme, period_end, violations):
    """Income statement (B02) — report_type='income_statement' rows only.

    bs_scheme is the ticker's BALANCE SHEET scheme from tracked_companies
    (e.g. 'TT200_DN'); this maps it to the income-statement dict scheme via
    IS_SCHEME_FOR_BS_SCHEME. A bank/CTCK/insurance ticker has no mapping yet
    (B02 KB gap, see IS_SCHEME_FOR_BS_SCHEME's comment) — flagged as
    SCHEME/out_of_scope rather than silently skipped, so it's visible instead
    of looking like "checked, 0 issues"."""
    is_scheme = IS_SCHEME_FOR_BS_SCHEME.get(bs_scheme)
    if not is_scheme:
        violations.append((ticker, period_end, 'SCHEME', '—',
                            f"income_statement scheme cho {ticker} (bs_scheme={bs_scheme}) chưa có trong "
                            f"IS_SCHEME_FOR_BS_SCHEME — B02 cho ngân hàng/CTCK/bảo hiểm ngoài phạm vi KB hiện tại, "
                            f"báo out_of_scope thay vì áp công thức TT200_DN sai chỗ."))
        return

    rows = conn.execute(text(
        "SELECT line_code, line_label, value_current, value_current_vnd, unit "
        "FROM listed_company_financials WHERE ticker = :t AND period_end = :p "
        "AND report_type = 'income_statement'"
    ), dict(t=ticker, p=period_end)).fetchall()
    by_code = {r[0]: r for r in rows}

    sign_by_code = {r[0]: r[1] for r in conn.execute(text(
        "SELECT line_code, sign_convention FROM bctc_line_code_dict WHERE code_scheme = :s"
    ), dict(s=is_scheme)).fetchall()}

    # 1. Sign convention (same rule as balance sheet — most B02 lines are
    # 'positive' even when they represent an expense/deduction, because the
    # FORMULA subtracts them rather than the ledger storing them negative;
    # see the sign list built alongside IS_SCHEME_FOR_BS_SCHEME above).
    for code, (_, label, cur, _, _) in by_code.items():
        if cur is None:
            continue
        conv = sign_by_code.get(code)
        if conv == 'negative' and cur > 0:
            violations.append((ticker, period_end, 'SIGN', code,
                                f"{code} ({label}) = {cur} — PHẢI ÂM theo bctc_line_code_dict "
                                f"(scheme={is_scheme}) nhưng đang dương."))
        elif conv == 'positive' and cur < 0:
            violations.append((ticker, period_end, 'SIGN', code,
                                f"{code} ({label}) = {cur} — PHẢI DƯƠNG theo bctc_line_code_dict "
                                f"(scheme={is_scheme}) nhưng đang âm."))

    # 2. Explicit add/subtract formulas (V03/V04)
    orientation_neg = _income_statement_orientation_negative(by_code)
    for target, operands in IS_FORMULAS.get(is_scheme, []):
        if target not in by_code or by_code[target][2] is None:
            continue
        def _eff_weight(w):
            return -w if (orientation_neg and w == -1) else w
        present = [(c, _eff_weight(w)) for c, w, _opt in operands if c in by_code and by_code[c][2] is not None]
        # Only REQUIRED operands being absent triggers INFO_NULL — an absent
        # optional operand (e.g. 24) legitimately contributes 0 and is simply
        # not counted, not reported as "missing".
        missing = [c for c, _w, opt in operands
                   if not opt and (c not in by_code or by_code[c][2] is None)]
        if not present:
            continue
        computed = sum((by_code[c][2] * w for c, w in present), Decimal(0))
        target_val = by_code[target][2]
        if close_enough(computed, target_val):
            continue
        formula_str = " ".join(f"{'+' if w > 0 else '-'}{c}" for c, w, _opt in operands)
        if missing:
            violations.append((ticker, period_end, 'INFO_NULL', target,
                                f"{target} ({formula_str}) = {target_val}, tính từ {len(present)} mã có = "
                                f"{computed} (lệch {abs(computed - target_val)}) — nhưng còn thiếu mã "
                                f"{', '.join(missing)} chưa trích, nên KHÔNG kết luận là sai số học."))
        else:
            violations.append((ticker, period_end, 'ARITHMETIC', target,
                                f"{target} ({formula_str}) = {target_val}, đủ mã tính = {computed} "
                                f"(lệch {abs(computed - target_val)}) — ĐÂY LÀ LỖI THẬT, không phải do thiếu trích."))

    # 3. NULL visibility
    null_codes = [c for c, r in by_code.items() if r[2] is None]
    if null_codes:
        violations.append((ticker, period_end, 'INFO_NULL', ','.join(null_codes),
                            f"value_current NULL ở các mã: {', '.join(null_codes)} — "
                            f"kiểm tra đây có phải khoảng trống đã biết/chủ đích không."))


def main():
    requested = sys.argv[1:]
    violations = []
    with engine.connect() as conn:
        tickers = get_tickers(conn, requested)
        for ticker in tickers:
            validate_ticker(conn, ticker, violations)

    hard_violations = [v for v in violations if v[2] != 'INFO_NULL']
    info = [v for v in violations if v[2] == 'INFO_NULL']

    if not violations:
        print(f"OK — {len(tickers)} ticker(s), không có vi phạm nào.")
        return 0

    print(f"Kiểm tra {len(tickers)} ticker(s): {len(hard_violations)} vi phạm, {len(info)} cảnh báo NULL.\n")
    for ticker, period_end, kind, code, detail in violations:
        print(f"[{kind:11s}] {ticker:6s} {str(period_end):12s} {code:12s} {detail}")

    return 1 if hard_violations else 0


if __name__ == '__main__':
    sys.exit(main())
