"""Parse a MOIT fuel price-management announcement page into structured cycle rows.

Source pages look like:
  moit.gov.vn/tin-tuc/...-dieu-hanh-gia-xang-dau-ngay-DD-M-YYYY.html

Two numeric conventions appear on the page and must NOT be confused:
  - World average price uses a COMMA decimal:  "73,582 USD/thùng"  -> 73.582 USD/barrel
  - Retail price uses a DOT thousands sep:      "18.845 đồng/lít"   -> 18845 VND/liter

We extract the three fuels the product covers (kerosene / mazut are ignored):
  RON95    <- "xăng RON95" world price + "Xăng RON95-III" retail
  E5RON92  <- "xăng RON92" world price (blend basis) + "Xăng E5RON92" retail
  DO005S   <- "dầu điêzen 0,05S" world price + "Dầu điêzen 0.05S" retail (đồng/lít)
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup

FUELS = ("RON95", "E5RON92", "DO005S")


@dataclass
class CycleRow:
    fuel: str
    retail_price: int          # VND/L
    base_price: int            # VND/L (Plan 1: approximated by retail; Plan 2 parses giá cơ sở tables)
    world_avg_price: float     # USD/barrel
    bog_contrib: float = 0.0   # VND/L (parsed in Plan 2)
    bog_use: float = 0.0       # VND/L
    taxes: dict = field(default_factory=dict)


def _to_world(num: str) -> float:
    # "73,582" -> 73.582
    return float(num.replace(".", "").replace(",", "."))


def _to_vnd(num: str) -> int:
    # "18.845" -> 18845
    return int(num.replace(".", "").replace(",", ""))


# World-price patterns (comma decimal). Diesel spelling varies: điêzen / diezen / diesel.
_WORLD_PATTERNS = {
    "RON95": r"(\d+,\d+)\s*USD/thùng\s*xăng\s*RON\s*95\b",
    "E5RON92": r"(\d+,\d+)\s*USD/thùng\s*xăng\s*RON\s*92\b",
    "DO005S": r"(\d+,\d+)\s*USD/thùng\s*dầu\s*(?:đi[êe]zen|diesel|diezen)",
}
# Retail patterns (dot thousands, must be đồng/lít not đồng/kg). `[^:]{0,20}:` matches
# only a SHORT grade suffix ("-III", " 0.05S") before the label's colon — this stops the
# pattern from starting at the fuel's mention in the world-price sentence and greedily
# skipping to the wrong retail colon. E10 rollout: gasoline relabelled "E10RON95-III".
_RETAIL_PATTERNS = {
    "RON95": r"Xăng\s*(?:E10\s*)?RON\s*95[^:]{0,20}:\s*không cao hơn\s*([\d.]+)\s*đồng/lít",
    "E5RON92": r"Xăng\s*E5\s*RON\s*92[^:]{0,20}:\s*không cao hơn\s*([\d.]+)\s*đồng/lít",
    "DO005S": r"Dầu\s*(?:đi[êe]zen|diesel|diezen)[^:]{0,20}:\s*không cao hơn\s*([\d.]+)\s*đồng/lít",
}


def parse_moit(html: str, period: date) -> list[CycleRow]:
    # NFC-normalize: MOIT pages mix precomposed/decomposed Vietnamese diacritics,
    # which breaks literal matches (e.g. "không cao hơn") unless normalized.
    text = unicodedata.normalize("NFC", BeautifulSoup(html, "html.parser").get_text("\n"))
    text = " ".join(text.split())

    world: dict[str, float] = {}
    retail: dict[str, int] = {}
    for fuel in FUELS:
        wm = re.search(_WORLD_PATTERNS[fuel], text, re.IGNORECASE)
        if wm:
            world[fuel] = _to_world(wm.group(1))
        rm = re.search(_RETAIL_PATTERNS[fuel], text, re.IGNORECASE)
        if rm:
            retail[fuel] = _to_vnd(rm.group(1))

    rows: list[CycleRow] = []
    for fuel in FUELS:
        if fuel in world and fuel in retail:
            rows.append(CycleRow(
                fuel=fuel,
                retail_price=retail[fuel],
                base_price=retail[fuel],          # Plan 1 approximation
                world_avg_price=world[fuel],
            ))
    return rows
