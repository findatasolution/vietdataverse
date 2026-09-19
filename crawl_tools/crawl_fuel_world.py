"""Crawl world refined-product / crude futures → Bronze (R2) → Silver (fuel_world_daily).

Free proxies for the MOPS reference window:
  BRENT = BZ=F (crude), RBOB = RB=F (US gasoline). SGGO (Singapore Gasoil, the closest
  diesel proxy) needs a LICENSED feed for the commercial product — see
  docs/research/2026-07-10-fuel-forecast-feasibility.md §2.3 — so it is a stub here.

HISTORY (read before changing the framing again):
  structural-v1 used these tickers to predict the LEVEL of the Singapore MOPS
  price and then ran it through the Nghị định 80 formula. It lost to random walk
  and was deleted 2026-09-10. A 2026-09-19 experiment found the opposite framing
  does work: the cycle-over-cycle CHANGE in the Brent 7-day window average,
  observed BEFORE the announcement, beats random walk on the change in retail
  price. That is the only use this table has ever earned — do not reinstate the
  level-on-level version.

Pattern (CLAUDE.md): land raw first, validate before insert, ON CONFLICT UPSERT,
explicit commit, sys.exit(1) on invalid data.
"""
import json
import math
import os
import sys
from datetime import datetime, timezone, date
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fuel_raw_store as raw_store

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

INSTRUMENTS = {"BRENT": "BZ=F", "RBOB": "RB=F"}  # SGGO deferred (licensed feed)


def _engine():
    db_url = os.getenv("FUEL_FORECAST_DB")
    if not db_url:
        sys.exit("FUEL_FORECAST_DB not set")
    return create_engine(db_url)


def to_world_rows(close_series, instrument: str) -> list[dict]:
    """Normalize a pandas Close series → list of {period, instrument, close}, skipping NaN."""
    rows = []
    for ts, value in close_series.items():
        try:
            v = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(v):
            continue
        period = ts.date() if hasattr(ts, "date") else ts
        rows.append({"period": period, "instrument": instrument, "close": v})
    return rows


# Per-instrument sane ranges. Units differ: Brent USD/barrel, RBOB USD/gallon,
# SGGO USD/barrel.
#
# Widened 2026-09-19 when the history went from 2y to max. The old floors (20.0
# Brent, 0.5 RBOB) were set against a 2-year window and rejected the real April
# 2020 COVID crash — Brent genuinely settled at 19.33 on 2020-04-21 and RBOB at
# 0.41 on 2020-03-23. Five real rows failed validation and, because validate()
# is all-or-nothing, the entire backfill was discarded.
#
# The floors stay far enough above zero, and the ceilings far enough above the
# 2008 peak (Brent 146.08) and the 2022 peak (RBOB 4.28), to still catch the
# failure these bounds exist for: a dropped or added digit, which moves a value
# by 10x. Do not narrow them back to whatever the recent window happens to span.
_BOUNDS = {"BRENT": (5.0, 250.0), "RBOB": (0.2, 15.0), "SGGO": (5.0, 400.0)}


def validate(rows: list[dict]) -> bool:
    if not rows:
        return False
    lo, hi = _BOUNDS.get(rows[0]["instrument"], (0.0, 1e9))
    return all(lo <= r["close"] <= hi for r in rows)


# One round trip per row was fine for a 2-year pull (~500 rows) and is not fine
# for the full history (~6,500 per ticker): against Neon it ran for minutes inside
# a single open transaction. Batched executemany + a commit per chunk keeps each
# transaction short.
_CHUNK = 500


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """Last value wins per (instrument, period). PURE.

    Needed because ON CONFLICT DO UPDATE cannot touch the same key twice inside
    one executemany batch -- Postgres raises "ON CONFLICT DO UPDATE command
    cannot affect row a second time". A single duplicated day in the source feed
    therefore aborts the whole transaction, which is what discarded the entire
    first full-history backfill on 2026-09-19.
    """
    out = {}
    for r in rows:
        out[(r["instrument"], r["period"])] = r
    return list(out.values())


def store(engine, rows: list[dict], source: str) -> None:
    now = datetime.now(timezone.utc)
    rows = dedupe_rows(rows)
    stmt = text("""
        INSERT INTO fuel_world_daily
            (period, instrument, close, crawl_time, source, group_name)
        VALUES (:period, :instrument, :close, :ct, :src, 'commodity')
        ON CONFLICT (instrument, period) DO UPDATE SET
            close = EXCLUDED.close, crawl_time = EXCLUDED.crawl_time
    """)
    with engine.connect() as conn:
        for i in range(0, len(rows), _CHUNK):
            conn.execute(stmt, [
                {"period": r["period"], "instrument": r["instrument"],
                 "close": r["close"], "ct": now, "src": source}
                for r in rows[i:i + _CHUNK]])
            conn.commit()


def crawl_instrument(ticker: str, instrument: str, engine) -> int:
    import yfinance as yf
    # "max", not "2y" (changed 2026-09-19). The 2y window was an arbitrary limit that
    # started this table at 2024-07-12 while fuel_price_cycle goes back to 2022-01-21,
    # so only 74 of 117 cycles had world-price features and the model could not be
    # trained on the rest. Yahoo serves BZ=F from 2007 and RB=F from 2000; the whole
    # series is ~6,500 rows per ticker, upserted, which is cheap once a day.
    series = yf.download(ticker, period="max", progress=False, auto_adjust=True)["Close"]
    if hasattr(series, "squeeze"):
        series = series.squeeze("columns") if getattr(series, "ndim", 1) > 1 else series
    payload = json.dumps({str(k): (None if v is None else float(v))
                          for k, v in series.items()}, default=str).encode()
    raw_store.land_raw(payload, "fuel_world", f"yfinance:{ticker}", "json", "application/json", 200)
    rows = to_world_rows(series, instrument)
    if not validate(rows):
        sys.exit(f"validation failed for {instrument} ({ticker})")
    store(engine, rows, f"yfinance:{ticker}")
    print(f"stored {len(rows)} rows for {instrument}")
    return len(rows)


def crawl_sggo(*_args, **_kwargs):
    raise NotImplementedError(
        "SGGO (Singapore Gasoil) needs a licensed feed (ICE/CME/Platts) for the commercial "
        "product — see feasibility §2.3. Do NOT scrape investing.com in production."
    )


# Futures trade on weekdays; a long weekend plus a holiday is the worst normal
# case. Past this, the series really has stopped advancing.
STALE_AFTER_DAYS = 6


def staleness_report(newest_by_instrument: dict, today) -> list[str]:
    """Instruments whose newest stored day is older than STALE_AFTER_DAYS. PURE.

    This exists because the crawl can succeed, write rows, and exit 0 while the
    data stops advancing — yfinance returning its cached/stale history upserts
    happily over identical rows. That is exactly how the MOIT crawl reported
    green for two months with a frozen table (CLAUDE.md, "MOIT re-files
    bulletins"). Row counts cannot see it; only the newest date can.
    """
    stale = []
    for instrument, newest in sorted(newest_by_instrument.items()):
        if newest is None:
            stale.append(f"{instrument}: no rows at all")
        elif (today - newest).days > STALE_AFTER_DAYS:
            stale.append(f"{instrument}: newest is {newest}, "
                         f"{(today - newest).days} days old")
    return stale


def newest_periods(engine) -> dict:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT instrument, max(period) FROM fuel_world_daily GROUP BY instrument"
        )).fetchall()
    found = {i: p for i, p in rows}
    return {inst: found.get(inst) for inst in INSTRUMENTS}


def main() -> None:
    engine = _engine()
    total = 0
    for instrument, ticker in INSTRUMENTS.items():
        total += crawl_instrument(ticker, instrument, engine)
    print(f"done: {total} world rows")

    stale = staleness_report(newest_periods(engine), date.today())
    if stale:
        sys.exit("STALE: " + "; ".join(stale))
    print("freshness OK")


if __name__ == "__main__":
    main()
