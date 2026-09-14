"""Tests for the retrospective SJC reconciler.

Every fixture below is real data from webgia.com, because each of the five
verdicts was discovered by running this tool against production history — none
of them were imagined up front. The carry-forward and unconfirmed cases in
particular started life as false ERRORs.
"""
import pytest

from crawl_tools.reconcile_sjc import _to_vnd, classify

M = 1_000_000

# 2026-07-13: SJC moved twice.
JUL13 = [("09:20", 145.9 * M, 148.9 * M), ("17:06", 145.4 * M, 148.4 * M)]
# 2026-07-14: one change, and it landed at 18:35 — after our last crawl.
JUL14 = [("18:35", 144.5 * M, 147.5 * M)]


def test_closing_quote_is_ok():
    assert classify(145.4 * M, 148.4 * M, JUL13)[0] == "ok"


def test_morning_quote_on_a_day_that_moved_is_stale():
    """The 75-day freeze bug's exact shape: a real quote, but not the day's last."""
    verdict, detail = classify(145.9 * M, 148.9 * M, JUL13, prev_close=(146.9 * M, 149.9 * M))
    assert verdict == "stale"
    assert "09:20" in detail and "145.4" in detail


def test_previous_close_is_carry_forward_not_fabrication():
    """SJC's first change on 2026-07-14 came at 18:35, after the last crawl, so
    the price in effect nearly all day was 13/07's close. Storing it is correct.
    Reported as a false ERROR until this case was added."""
    verdict, _ = classify(145.4 * M, 148.4 * M, JUL14, prev_close=(145.4 * M, 148.4 * M))
    assert verdict == "carry_forward"


def test_value_matching_nothing_is_fabricated():
    """The real 2026-07-14 row: 144.1/147.1 is neither that day's only quote nor
    the previous close."""
    verdict, _ = classify(144.1 * M, 147.1 * M, JUL14, prev_close=(145.4 * M, 148.4 * M))
    assert verdict == "fabricated"


def test_no_change_day_matching_previous_close_is_ok():
    assert classify(144.5 * M, 147.5 * M, [], prev_close=(144.5 * M, 147.5 * M))[0] == "ok"


def test_no_change_day_differing_is_only_unconfirmed():
    """An empty archive day is absence of evidence. It must not be an ERROR: the
    archive may simply be missing the entry."""
    verdict, detail = classify(145.5 * M, 148.5 * M, [], prev_close=(144.5 * M, 147.5 * M))
    assert verdict == "unconfirmed"
    assert "check by hand" in detail


def test_no_data_without_a_previous_close_is_not_a_finding():
    assert classify(144.5 * M, 147.5 * M, [], prev_close=None)[0] == "no_data"


def test_tolerance_absorbs_rounding_but_not_a_real_gap():
    # 100k on ~144M is rounding; 600k is a genuine SJC adjustment step.
    assert classify(144.6 * M, 147.6 * M, JUL14, prev_close=None)[0] == "ok"
    assert classify(143.9 * M, 146.9 * M, JUL14, prev_close=None)[0] == "fabricated"


@pytest.mark.parametrize("raw,want", [
    ("142.000", 142_000_000),
    ("141.400 (-600)", 141_400_000),   # the change annotation must be dropped
    ("142.400 (+1000)", 142_400_000),
])
def test_price_parsing(raw, want):
    assert _to_vnd(raw) == want
