"""Tests for the gold/silver plausibility guards.

The gold fixtures are the real values 24h.com.vn published on 2026-07-18 (where DOJI
was a digit short) and 2026-08-07 (a normal day).
"""

from crawl_tools.gold_validation import silver_is_plausible, validate_gold_records


def rec(gold_type, buy, sell):
    return {'date': '2026-07-18', 'type': gold_type, 'buy_price': buy, 'sell_price': sell}


# Exactly what the source served on 2026-07-18 (×1000, as the crawler scales it).
DAY_WITH_SOURCE_TYPO = [
    rec('SJC',         144_500_000, 147_500_000),
    rec('DOJI HN',      14_450_000,  14_750_000),   # source dropped a digit
    rec('DOJI SG',      14_450_000,  14_750_000),   # source dropped a digit
    rec('BTMH',        142_600_000, 146_600_000),
    rec('BTMC VRTL',   142_600_000, 146_600_000),
    rec('BTMC SJC',    142_600_000, 147_500_000),
    rec('Phú Qúy SJC', 144_000_000, 147_500_000),
    rec('PNJ TP.HCM',  142_500_000, 146_500_000),
    rec('PNJ Hà Nội',  142_500_000, 146_500_000),
]

NORMAL_DAY = [
    rec('SJC',         138_000_000, 141_000_000),
    rec('DOJI HN',     138_000_000, 141_000_000),
    rec('BTMH',        137_500_000, 140_500_000),
    rec('PNJ Hà Nội',  137_000_000, 140_000_000),
]


def test_rejects_the_digit_short_rows_that_caused_the_outage():
    kept = validate_gold_records(DAY_WITH_SOURCE_TYPO, log=lambda *_: None)
    kept_types = {r['type'] for r in kept}
    assert 'DOJI HN' not in kept_types
    assert 'DOJI SG' not in kept_types
    assert len(kept) == 7


def test_keeps_every_brand_on_a_normal_day():
    kept = validate_gold_records(NORMAL_DAY, log=lambda *_: None)
    assert len(kept) == len(NORMAL_DAY)


def test_rejects_the_2024_pnj_wrong_product_line():
    """PNJ Hà Nội sat at ~30M while every other brand was ~84M (Nov–Dec 2024)."""
    day = [
        rec('SJC',        84_000_000, 85_500_000),
        rec('DOJI HN',    83_700_000, 85_200_000),
        rec('PNJ TP.HCM', 84_000_000, 85_200_000),
        rec('PNJ Hà Nội', 30_740_000, 32_140_000),  # in range, but way off median
    ]
    kept = validate_gold_records(day, log=lambda *_: None)
    assert 'PNJ Hà Nội' not in {r['type'] for r in kept}
    assert len(kept) == 3


def test_median_rule_skipped_when_too_few_brands():
    """With <3 brands the median is meaningless — range check alone applies."""
    day = [rec('SJC', 138_000_000, 141_000_000), rec('DOJI HN', 90_000_000, 92_000_000)]
    assert len(validate_gold_records(day, log=lambda *_: None)) == 2


def test_rejects_none_and_zero_prices():
    day = [
        rec('SJC',        138_000_000, 141_000_000),
        rec('DOJI HN',    138_000_000, 141_000_000),
        rec('BTMH',       137_500_000, 140_500_000),
        rec('PNJ Hà Nội',           0,  74_700_000),   # the 2022–2024 zero-buy rows
        rec('Phú Qúy SJC',       None,        None),
    ]
    kept_types = {r['type'] for r in validate_gold_records(day, log=lambda *_: None)}
    assert kept_types == {'SJC', 'DOJI HN', 'BTMH'}


def test_silver_bounds():
    quiet = lambda *_: None
    assert silver_is_plausible('giabac.vn', 2_262_000, 2_332_000, log=quiet)
    assert not silver_is_plausible('giabac.vn', 226_200, 233_200, log=quiet)      # digit short
    assert not silver_is_plausible('giabac.vn', 22_620_000, 23_320_000, log=quiet)  # digit extra
    assert not silver_is_plausible('giabac.vn', None, 2_332_000, log=quiet)
