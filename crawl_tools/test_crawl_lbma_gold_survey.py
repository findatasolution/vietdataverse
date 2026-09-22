"""Tests for the LBMA gold forecast survey parsers.

Fixtures below are trimmed, whitespace-collapsed excerpts of the real pages
fetched 2026-09-22 (annual 2026 survey, mid-year 2026 snapshot) — not
invented text. No network access; parse_annual/parse_midyear are pure
functions over already-fetched text.
"""
import pytest

from crawl_tools.crawl_lbma_gold_survey import SourceMismatch, parse_annual, parse_midyear

ANNUAL_2026_TEXT = (
    "Key Takeaways Gold outlook: Gold outlook : Of all four metals, analysts gave more "
    "conservative price forecast increases for gold. The gold price for 2026 is predicted "
    "to see gains averaging at $4,741.97 across the year. However, the forecast trading "
    "range is $3,700 (from $3,450 to $7,150), up 103% from the actual range in 2025 of "
    "$1816 (and up 256% from the 2025 forecast range of $1,040). The current gold price "
    "of $4,666.85 (as at 19 January) is currently closer to the lowest low of $3,500.00 "
    "than the highest high of $7,1500.00 – but it's all to play for. Most bearish : Rob... "
    "layout/blocks/forecast/_summary Summary of the analysts' commentary Gold forecast "
    "Of the 28 analysts forecasting in the gold category, a staggering 22 of them expect "
    "gold to hit prices higher than $5,000.00 this year."
)

MIDYEAR_2026_TEXT = (
    "Publications Alchemist Press August 11, 2026 Gold Price: LBMA Snapshot Survey of "
    "Professional Analysts Post Copy link layout/blocks/body/_text Gold is forecast to "
    "price at around $4,500 at year-end according to the average of a survey of 16 "
    "professional analysts conducted, during July, by LBMA. The highest year-end number "
    "from the survey was $5,100, the lowest $3,879. During the first seven months of 2026, "
    "the gold price recorded unusually high volatility."
)

URL = "https://example.org/fixture"


def test_parses_the_real_annual_2026_fixture():
    row = parse_annual(ANNUAL_2026_TEXT, 2026, URL)
    assert row["avg_price"] == 4741.97
    assert row["low_price"] == 3450.0
    assert row["high_price"] == 7150.0
    assert row["n_analysts"] == 28
    assert row["published_date"].isoformat() == "2026-01-19"
    assert row["survey_type"] == "annual"
    assert row["survey_year"] == 2026


def test_parses_the_real_midyear_2026_fixture():
    row = parse_midyear(MIDYEAR_2026_TEXT, URL)
    assert row["avg_price"] == 4500.0
    assert row["low_price"] == 3879.0
    assert row["high_price"] == 5100.0
    assert row["n_analysts"] == 16
    assert row["published_date"].isoformat() == "2026-08-11"
    assert row["survey_type"] == "midyear"
    # survey_year comes from the publish-date stamp, not from any explicit
    # year in the forecast sentence (which only ever says "year-end").
    assert row["survey_year"] == 2026


def test_annual_rejects_a_year_the_page_does_not_state():
    """The lesson from the 196 fake gold rows: a caller-supplied year must be
    confirmed by the page's own text, not assumed from the URL alone."""
    with pytest.raises(SourceMismatch):
        parse_annual(ANNUAL_2026_TEXT, 2027, URL)


def test_annual_missing_analyst_count_is_a_mismatch():
    truncated = ANNUAL_2026_TEXT.split("layout/blocks/forecast")[0]
    with pytest.raises(SourceMismatch):
        parse_annual(truncated, 2026, URL)


def test_midyear_missing_publish_date_is_a_mismatch():
    truncated = MIDYEAR_2026_TEXT.replace("August 11, 2026 Gold Price: LBMA Snapshot Survey of Professional Analysts", "")
    with pytest.raises(SourceMismatch):
        parse_midyear(truncated, URL)


def test_price_ordering_is_sane_on_both_fixtures():
    for row in (parse_annual(ANNUAL_2026_TEXT, 2026, URL), parse_midyear(MIDYEAR_2026_TEXT, URL)):
        assert row["low_price"] <= row["avg_price"] <= row["high_price"]
