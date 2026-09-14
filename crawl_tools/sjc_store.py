"""
Shared persistence + sanity rules for the two SJC gold crawlers.

There are deliberately two independent crawlers for one number — SJC's quoted
buy/sell price — reading two unrelated sites (crawl_sjc_24h.py against
24h.com.vn, crawl_sjc_giavang.py against giavang.org). Both call store_sjc()
here, so the write path, the plausibility rules and the cross-source comparison
exist in exactly one place.

Why two sources at all: through 2026-09 this project shipped a chart that
disagreed with reality for weeks, and every layer that was supposed to catch it
looked at the data in isolation — a frozen price is still in range, still
"fresh", still internally consistent. A second, unrelated source is the one
check that catches a wrong-but-plausible number, because two sites do not
invent the same wrong figure.

They are NOT primary/backup: each writes its own row (uq_vn_gold_date_type_source),
and the read path in be/generate_static_data.py chooses which one to publish.
"""
import os
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, text

# SJC bar gold, VND per lượng. Wide on purpose: this is the "someone dropped or
# added a digit" guard, not a forecast. 2015 lows were ~34M; the 2026 peak so
# far is ~188M.
MIN_PRICE = 20_000_000
MAX_PRICE = 500_000_000

# Buy must be below sell, and the spread is normally 2-4M. A spread far outside
# that means the two columns were swapped or a row was misread.
MAX_SPREAD = 15_000_000

# How far the two sources may differ before it is worth shouting about. They
# quote the same company's published price, so in practice they agree exactly;
# a small tolerance absorbs one site updating minutes before the other.
CROSS_SOURCE_TOLERANCE = 0.02  # 2%


class ImplausibleQuote(ValueError):
    """Parsed numbers that cannot be a real SJC quote — never stored."""


def check_plausible(buy: float, sell: float) -> None:
    if not (MIN_PRICE <= buy <= MAX_PRICE):
        raise ImplausibleQuote(f"buy {buy:,.0f} outside {MIN_PRICE:,}-{MAX_PRICE:,}")
    if not (MIN_PRICE <= sell <= MAX_PRICE):
        raise ImplausibleQuote(f"sell {sell:,.0f} outside {MIN_PRICE:,}-{MAX_PRICE:,}")
    if sell < buy:
        raise ImplausibleQuote(f"sell {sell:,.0f} below buy {buy:,.0f} — columns swapped?")
    if sell - buy > MAX_SPREAD:
        raise ImplausibleQuote(f"spread {sell - buy:,.0f} exceeds {MAX_SPREAD:,}")


def get_engine():
    url = os.getenv("CRAWLING_BOT_DB")
    if not url:
        sys.exit("CRAWLING_BOT_DB not set")
    return create_engine(url)


def store_sjc(source: str, buy: float, sell: float, date_str: Optional[str] = None) -> dict:
    """Validate, upsert today's SJC row for `source`, and compare against the
    other source. Returns a small report the caller prints.

    Every run upserts. There is deliberately no "skip if a row already exists"
    guard: that guard, present in three separate places at once, is what pinned
    the published price to the morning quote for 75 days (see CLAUDE.md).
    """
    check_plausible(buy, sell)

    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    crawl_time = datetime.now()
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO vn_macro_gold_daily
                    (date, type, buy_price, sell_price, crawl_time, source, group_name)
                VALUES (:date, 'SJC', :buy, :sell, :crawl_time, :source, 'commodity')
                ON CONFLICT (date, type, source) DO UPDATE SET
                    buy_price  = EXCLUDED.buy_price,
                    sell_price = EXCLUDED.sell_price,
                    crawl_time = EXCLUDED.crawl_time
            """),
            {"date": date_str, "buy": buy, "sell": sell,
             "crawl_time": crawl_time, "source": source},
        )

        others = conn.execute(
            text("""
                SELECT source, buy_price, sell_price, crawl_time
                FROM vn_macro_gold_daily
                WHERE date = :date AND type = 'SJC' AND source <> :source
            """),
            {"date": date_str, "source": source},
        ).fetchall()

    disagreements = []
    for other_source, other_buy, _other_sell, other_time in others:
        delta = abs(buy - float(other_buy)) / float(other_buy)
        if delta > CROSS_SOURCE_TOLERANCE:
            disagreements.append(
                f"{source} says {buy:,.0f} but {other_source} says {float(other_buy):,.0f} "
                f"({delta * 100:.1f}% apart, other read at {other_time:%H:%M})"
            )

    return {"date": date_str, "source": source, "buy": buy, "sell": sell,
            "compared_with": [o[0] for o in others], "disagreements": disagreements}


def report(result: dict) -> int:
    """Print the result; return the process exit code.

    A disagreement exits non-zero so the unit goes red and the journal shows it.
    The row is still written — the number may well be correct, and dropping it
    would leave the day empty rather than merely disputed.
    """
    print(f"  {result['source']}: buy {result['buy']:,.0f} | sell {result['sell']:,.0f} "
          f"({result['date']})")
    if result["compared_with"]:
        if result["disagreements"]:
            for line in result["disagreements"]:
                print(f"  DISAGREEMENT: {line}")
            return 1
        print(f"  cross-checked against {', '.join(result['compared_with'])} — agree")
    else:
        print("  no other source has today's row yet — nothing to cross-check")
    return 0
