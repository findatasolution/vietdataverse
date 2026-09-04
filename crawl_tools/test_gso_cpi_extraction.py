"""Regression tests for crawl_gso_cpi.py's layer1_structured() regex extraction.

Every fixture below is real NSO prose (flattened get_text output), captured
from bulletins that caused a real production bug: 2026-07 and 2026-08 both
stored cpi_yoy_pct=4.45% (different months, same wrong number) because the
regex anchored on "CPI" inside the year-to-date sentence ("Bình quân tám
tháng năm 2026, CPI tăng 4,45%...") instead of the month's own sentence. A
DB audit against these same source pages (2026-09-05) found 5 more months
silently wrong the same way, dating back to 2025-05 — see BACKLOG.md.

Run: python -m pytest crawl_tools/test_gso_cpi_extraction.py -v
"""
import os

# layer1_structured() is a pure function, but the module it lives in creates
# a DB engine at import time (crawl_gso_cpi.py is a script, not a library).
# SQLAlchemy's create_engine() doesn't actually connect until a query runs,
# so a syntactically-valid placeholder is enough to import the module
# without a real database.
os.environ.setdefault('CRAWLING_BOT_DB', 'postgresql://test:test@localhost/test')

from crawl_tools.crawl_gso_cpi import layer1_structured


def test_august_2026_yoy_not_year_to_date_average():
    """The bug that started this file: both figures ('4,89%' for the month,
    '4,45%' for the year-to-date average) share the same "% so với cùng kỳ
    năm trước" tail in the same sentence block — the month's own figure must
    win, not whichever happens to be textually closer to a naive anchor."""
    text = (
        "Chỉ số giá tiêu dùng, chỉ số giá vàng và chỉ số giá đô la Mỹ tháng "
        "Tám và 8 tháng năm 2026\n"
        "Chỉ số giá tiêu dùng (CPI)\n"
        "tháng Tám tăng 0,47% so với tháng trước; tăng 3,57% so với tháng "
        "12/2025 và tăng 4,89% so với cùng kỳ năm trước. Bình quân tám "
        "tháng năm 2026, CPI tăng 4,45% so với cùng kỳ năm trước; lạm phát "
        "cơ bản tăng 4,24%.\n"
        "Chỉ số giá vàng\n"
        "tháng Tám giảm 0,65% so với tháng trước; tăng 16,98% so với cùng "
        "kỳ năm 2025; giảm 6,27% so với tháng 12/2025. Bình quân tám tháng "
        "năm 2026, chỉ số giá vàng tăng 46,98% so với cùng kỳ năm trước.\n"
        "Chỉ số giá đô la Mỹ\n"
        "tháng Tám giảm 0,38% so với tháng trước; giảm 0,36% so với cùng "
        "kỳ năm 2025; giảm 0,38% so với tháng 12/2025. Bình quân tám tháng "
        "năm 2026, chỉ số giá đô la Mỹ tăng 1,31% so với cùng kỳ năm trước."
    )
    result = layer1_structured(text, '2026-08')
    assert result['cpi_mom_pct'] == 0.47
    assert result['cpi_yoy_pct'] == 4.89, (
        f"got {result.get('cpi_yoy_pct')} — likely matched the 4.45% "
        "year-to-date average instead of the month's own 4.89%")
    assert result['gold_mom_pct'] == -0.65, (
        f"got {result.get('gold_mom_pct')} — likely matched the 46.98% "
        "year-to-date average instead of the month's own -0.65%")
    assert result['usd_mom_pct'] == -0.38


def test_july_2026_uses_tinh_chung_not_binh_quan_for_ytd():
    """NSO phrases the year-to-date figure as "Tính chung N tháng..." in
    this bulletin instead of "Bình quân N tháng..." — both must be excluded
    or this passes by accident (the month sentence happens to come first)
    rather than by construction."""
    text = (
        "Chỉ số giá tiêu dùng (CPI)\n"
        "tháng Bảy giảm 0,12% so với tháng trước; tăng 3,08% so với tháng "
        "12/2025 và tăng 4,45% so với cùng kỳ năm trước. Tính chung bảy "
        "tháng năm 2026, CPI tăng 4,39% so với cùng kỳ năm trước; lạm phát "
        "cơ bản tăng 4,19%."
    )
    result = layer1_structured(text, '2026-07')
    assert result['cpi_mom_pct'] == -0.12
    assert result['cpi_yoy_pct'] == 4.45


def test_may_2025_yoy_in_a_separate_sentence_from_mom():
    """A third phrasing: mom% and yoy% are in two different sentences (mom%
    sentence has no 'so với cùng kỳ' at all), and the correct yoy% (3.24%)
    is textually FARTHER from the CPI anchor than the wrong year-to-date
    average (3.21%) that follows it — this is the actual 2025-05 production
    bug, confirmed 2026-09-05 by reading the live source page by hand."""
    text = (
        "Chỉ số giá tiêu dùng (CPI)\n"
        "tháng 5/2025 tăng 0,16% so với tháng trước chủ yếu do giá thuê "
        "nhà, vật liệu bảo dưỡng nhà ở, điện sinh hoạt và ăn uống ngoài "
        "gia đình tăng. CPI tháng Năm tăng 1,53% so với tháng 12/2024; "
        "tăng 3,24% so với cùng kỳ năm trước. Bình quân năm tháng đầu năm "
        "2025, CPI tăng 3,21% so với cùng kỳ năm trước; lạm phát cơ bản "
        "tăng 3,10%."
    )
    result = layer1_structured(text, '2025-05')
    assert result['cpi_mom_pct'] == 0.16
    assert result['cpi_yoy_pct'] == 3.24, (
        f"got {result.get('cpi_yoy_pct')} — this is the confirmed "
        "2025-05 production bug (DB had 3.21%, the 5-month average, "
        "until corrected 2026-09-05)")


def test_reversed_phrasing_comparison_leads_subject_follows():
    """NSO occasionally leads with the comparison instead of the subject:
    "So với cùng kỳ năm trước, CPI tháng Mười Hai tăng 3,48%." — this is
    what the second cpi_yoy_pct pattern (not the primary one) exists for."""
    text = (
        "Chỉ số giá tiêu dùng (CPI)\n"
        "tháng Mười Hai tăng 0,19% so với tháng trước do giá lương thực, "
        "thực phẩm và ăn uống ngoài gia đình tăng. So với cùng kỳ năm "
        "trước, CPI tháng Mười Hai tăng 3,48%. CPI bình quân quý IV/2025 "
        "tăng 3,44% so với cùng kỳ năm trước."
    )
    result = layer1_structured(text, '2025-12')
    assert result['cpi_mom_pct'] == 0.19
    assert result['cpi_yoy_pct'] == 3.48


def test_combined_title_line_does_not_leak_into_any_field():
    """The page's own title/heading lists all three indices together and
    must never be mistaken for a content sentence by any of the three
    anchors (cpi/tiêu dùng, vàng, đô la)."""
    text = (
        "Chỉ số giá tiêu dùng (CPI), chỉ số giá vàng và chỉ số giá đô la "
        "Mỹ tháng Tám và 8 tháng năm 2026\n"
        "Chỉ số giá tiêu dùng (CPI)\n"
        "tháng Tám tăng 0,47% so với tháng trước; tăng 4,89% so với cùng "
        "kỳ năm trước.\n"
        "Chỉ số giá vàng\n"
        "tháng Tám giảm 0,65% so với tháng trước.\n"
        "Chỉ số giá đô la Mỹ\n"
        "tháng Tám giảm 0,38% so với tháng trước."
    )
    result = layer1_structured(text, '2026-08')
    assert result['cpi_mom_pct'] == 0.47
    assert result['gold_mom_pct'] == -0.65
    assert result['usd_mom_pct'] == -0.38
