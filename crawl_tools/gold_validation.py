"""Plausibility guards for domestic gold & silver prices.

Kept in its own module (rather than inline in crawl_gold_silver.py) so the rules can
be unit-tested without running the crawler.

Why these exist: on 2026-07-18 the source itself published DOJI as "14,450" instead of
"144,500" — a tenth of the real price. Nothing validated before insert, so the bad value
reached the public chart and the API and sat there for 20 days.
"""

# Sanity bounds for one tael (lượng) in VND. Wide enough to survive years of price
# drift, tight enough to catch a missing or extra digit.
GOLD_MIN_VND = 20_000_000
GOLD_MAX_VND = 500_000_000
SILVER_MIN_VND = 300_000
SILVER_MAX_VND = 20_000_000

# A brand further than this from the same-day median across all brands is a source
# typo, not a real spread — real inter-brand spread stays within a few percent.
GOLD_MEDIAN_TOLERANCE = 0.15

# Below this many brands the median is not trustworthy, so the outlier rule is skipped.
MIN_BRANDS_FOR_MEDIAN = 3


def validate_gold_records(records, log=print):
    """Return the subset of `records` that is plausible.

    Two passes:
      1. absolute range — catches a dropped or extra digit outright
      2. cross-brand median — catches a digit error that still lands in range,
         e.g. one brand at 30M while every other brand sits at 84M
    """
    def implausible(value):
        return value is None or not (GOLD_MIN_VND <= value <= GOLD_MAX_VND)

    in_range = []
    for record in records:
        bad = [
            f"{field}={'null' if record[field] is None else format(record[field], ',.0f')}"
            for field in ('buy_price', 'sell_price')
            if implausible(record[field])
        ]
        if bad:
            log(f"  REJECT (range) {record['type']}: {', '.join(bad)}")
            continue
        in_range.append(record)

    if len(in_range) < MIN_BRANDS_FOR_MEDIAN:
        return in_range

    buys = sorted(r['buy_price'] for r in in_range)
    median_buy = buys[len(buys) // 2]

    kept = []
    for record in in_range:
        deviation = abs(record['buy_price'] - median_buy) / median_buy
        if deviation > GOLD_MEDIAN_TOLERANCE:
            log(f"  REJECT (outlier) {record['type']}: buy={record['buy_price']:,.0f} "
                f"is {deviation*100:.0f}% off same-day median {median_buy:,.0f}")
            continue
        kept.append(record)
    return kept


def silver_is_plausible(label, buy, sell, log=print):
    """True when both sides of a silver quote sit inside the plausible band."""
    for field, value in (('buy', buy), ('sell', sell)):
        if value is None or not (SILVER_MIN_VND <= value <= SILVER_MAX_VND):
            log(f"  REJECT (range) {label} {field}={value} "
                f"outside [{SILVER_MIN_VND:,.0f}, {SILVER_MAX_VND:,.0f}]")
            return False
    return True
