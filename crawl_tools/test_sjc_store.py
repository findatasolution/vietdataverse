"""Tests for the SJC write-path guards (crawl_tools/sjc_store.py).

These are the only validation the two SJC crawlers run, so they are the whole
safety net for the number the site publishes. gold_validation.py's cross-brand
median rule no longer applies here: that rule needs >=3 brands on one page and
the table holds SJC alone since 2026-09-14. The cross-source comparison below
replaces it, and covers strictly more — two unrelated sites cannot agree on a
wrong figure, whereas the median rule inverted whenever bad rows were the
majority (see CLAUDE.md, "Gold table was reduced to SJC alone").
"""
from datetime import datetime

import pytest

from crawl_tools.sjc_store import (
    CROSS_SOURCE_TOLERANCE,
    ImplausibleQuote,
    check_plausible,
    compare_sources,
    report,
)

T = datetime(2026, 9, 14, 6, 1, 59)


# ── check_plausible: the pre-insert guard ─────────────────────────────────────

@pytest.mark.parametrize("buy,sell", [
    (143_200_000, 146_200_000),   # the real quote on 2026-09-14
    (34_000_000, 34_500_000),     # 2015-era level, still inside the floor
    (188_000_000, 191_000_000),   # the 2026 peak
])
def test_accepts_real_quotes(buy, sell):
    check_plausible(buy, sell)


@pytest.mark.parametrize("label,buy,sell", [
    # The exact shape of the 2026-07-18 outage, where the source itself printed
    # 14,450 instead of 144,500.
    ("digit dropped",   14_320_000,    14_620_000),
    ("digit added",  1_432_000_000, 1_462_000_000),
    ("columns swapped", 146_200_000,  143_200_000),
    ("absurd spread",   143_200_000,  165_000_000),
    ("zero",                      0,            0),
])
def test_rejects_impossible_quotes(label, buy, sell):
    with pytest.raises(ImplausibleQuote):
        check_plausible(buy, sell)


# ── compare_sources: the rule that catches wrong-but-plausible numbers ────────

def test_agreeing_sources_produce_no_disagreement():
    others = [("giavang.org", 143_200_000, 146_200_000, T)]
    assert compare_sources("24h.com.vn", 143_200_000, 146_200_000, others) == []


def test_small_drift_is_tolerated():
    """One site updating minutes before the other must not cry wolf."""
    drift = 1 + CROSS_SOURCE_TOLERANCE * 0.5
    others = [("giavang.org", 143_200_000 * drift, 146_200_000 * drift, T)]
    assert compare_sources("24h.com.vn", 143_200_000, 146_200_000, others) == []


def test_catches_a_buy_price_disagreement():
    others = [("giavang.org", 120_000_000, 146_200_000, T)]
    found = compare_sources("24h.com.vn", 143_200_000, 146_200_000, others)
    assert len(found) == 1 and found[0].startswith("buy:")


def test_catches_a_sell_price_disagreement():
    """Regression: the comparison once looked at buy only, so a wrong sell —
    the number a buyer actually pays — passed silently."""
    others = [("giavang.org", 143_200_000, 120_000_000, T)]
    found = compare_sources("24h.com.vn", 143_200_000, 146_200_000, others)
    assert len(found) == 1 and found[0].startswith("sell:")


def test_no_other_source_yet_is_not_a_disagreement():
    assert compare_sources("24h.com.vn", 143_200_000, 146_200_000, []) == []


# ── report(): a disagreement must turn the unit red ───────────────────────────

def _result(disagreements, compared_with=("giavang.org",)):
    return {"date": "2026-09-14", "source": "24h.com.vn",
            "buy": 143_200_000, "sell": 146_200_000,
            "compared_with": list(compared_with), "disagreements": disagreements}


def test_agreement_exits_zero():
    assert report(_result([])) == 0


def test_disagreement_exits_non_zero():
    assert report(_result(["sell: 24h.com.vn says 1 but giavang.org says 2 (…)"])) == 1


def test_unverified_day_still_exits_zero():
    """First crawler of the day has nothing to compare against. That is normal,
    not a failure — the second crawler does the comparison moments later."""
    assert report(_result([], compared_with=())) == 0
