"""
SJC gold price — source 1 of 2: 24h.com.vn.

Pairs with crawl_sjc_giavang.py, which reads the same number from an unrelated
site. Both write their own row (see sjc_store.store_sjc) and cross-check each
other; neither is a backup for the other.

Split out of crawl_gold_silver.py on 2026-09-14. That script now handles silver
and global macro only. Keeping gold inside it meant a Yahoo Finance failure
(Yahoo blocks datacenter IPs, so this is routine) exited the whole run non-zero
and buried whether the gold crawl had actually worked.
"""
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from sjc_store import ImplausibleQuote, report, store_sjc

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

SOURCE = "24h.com.vn"
# No ?ngaythang= parameter. Asking that page for a PAST date returns fixed
# placeholder numbers (81,000/83,300 for SJC) rather than that day's prices — a
# backfill through it wrote 196 fake rows into this table, deleted 2026-09-14.
URL = "https://www.24h.com.vn/gia-vang-hom-nay-c425.html"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VietDataverse/1.0)"}


def fetch_sjc():
    """Return (buy, sell) in VND/lượng for the row whose brand cell is exactly 'SJC'.

    The page lists ~9 brands in one table; prices are in thousand VND.
    """
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        if cells[0].get_text(strip=True) != "SJC":
            continue
        buy_span = cells[1].find("span", class_="fixW")
        sell_span = cells[2].find("span", class_="fixW")
        if not buy_span or not sell_span:
            continue
        buy = float(buy_span.get_text(strip=True).replace(".", "").replace(",", "")) * 1000
        sell = float(sell_span.get_text(strip=True).replace(".", "").replace(",", "")) * 1000
        return buy, sell

    raise LookupError("no row with brand cell 'SJC' — page layout changed?")


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
