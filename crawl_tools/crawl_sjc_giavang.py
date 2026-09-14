"""
SJC gold price — source 2 of 2: giavang.org.

Pairs with crawl_sjc_24h.py. Two unrelated sites are read for the same number
because every single-source check this project had (range, freshness, internal
consistency) passed happily while the published price was wrong for weeks — two
sites do not invent the same wrong figure.

Chosen after sjc.com.vn itself returned 403 to server requests (2026-09-14) and
24h.com.vn's historical lookup proved to serve placeholder data.
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from sjc_store import ImplausibleQuote, report, store_sjc

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

SOURCE = "giavang.org"
URL = "https://giavang.org/trong-nuoc/sjc/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}


def _to_vnd(text_value: str) -> float:
    """'143.200' (x1000đ/lượng, as the page labels it) -> 143200000.0"""
    digits = re.sub(r"[^\d]", "", text_value)
    if not digits:
        raise LookupError(f"no digits in {text_value!r}")
    return float(digits) * 1000


def fetch_sjc():
    """Return (buy, sell) in VND/lượng from the 'Giá vàng Miếng' block.

    Layout: an <h2> 'Giá vàng Miếng' followed by two boxes — .box-cgre holds
    'Mua vào', .box-cred holds 'Bán ra' — each with a .gold-price span. The page
    also lists ring gold further down, hence anchoring on that heading rather
    than taking the first price on the page.
    """
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    heading = soup.find(
        lambda tag: tag.name == "h2" and "Giá vàng Miếng" in tag.get_text()
    )
    if heading is None:
        raise LookupError("no 'Giá vàng Miếng' heading — page layout changed?")

    block = heading.find_parent(class_="gold-price-box") or heading.parent
    buy_box = block.find(class_="box-cgre")
    sell_box = block.find(class_="box-cred")
    if not buy_box or not sell_box:
        raise LookupError("buy/sell boxes not found under 'Giá vàng Miếng'")

    buy_el = buy_box.find(class_="gold-price")
    sell_el = sell_box.find(class_="gold-price")
    if not buy_el or not sell_el:
        raise LookupError("no .gold-price inside the buy/sell boxes")

    # The span holds the number plus a <small> unit label; drop the label.
    for el in (buy_el, sell_el):
        for small in el.find_all("small"):
            small.decompose()

    return _to_vnd(buy_el.get_text(strip=True)), _to_vnd(sell_el.get_text(strip=True))


def main() -> int:
    print(f"--- SJC via {SOURCE} ---")
    try:
        buy, sell = fetch_sjc()
    except (requests.RequestException, LookupError) as exc:
        print(f"  FAILED to read {SOURCE}: {exc}")
        return 1
    try:
        return report(store_sjc(SOURCE, buy, sell))
    except ImplausibleQuote as exc:
        print(f"  REJECTED (not stored): {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
