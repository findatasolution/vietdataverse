"""Crawl world refined-product / crude futures → Bronze (R2) → Silver (fuel_world_daily).

Free proxies for the MOPS reference window:
  BRENT = BZ=F (crude), RBOB = RB=F (US gasoline). SGGO (Singapore Gasoil, the closest
  diesel proxy) needs a LICENSED feed for the commercial product — see
  docs/research/2026-07-10-fuel-forecast-feasibility.md §2.3 — so it is a stub here.

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


# Per-instrument sane ranges — units differ: Brent USD/barrel (~20-200),
# RBOB USD/gallon (~0.5-10), SGGO USD/barrel.
_BOUNDS = {"BRENT": (20.0, 200.0), "RBOB": (0.5, 10.0), "SGGO": (20.0, 300.0)}


def validate(rows: list[dict]) -> bool:
    if not rows:
        return False
    lo, hi = _BOUNDS.get(rows[0]["instrument"], (0.0, 1e9))
    return all(lo <= r["close"] <= hi for r in rows)


def store(engine, rows: list[dict], source: str) -> None:
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO fuel_world_daily
                    (period, instrument, close, crawl_time, source, group_name)
                VALUES (:period, :instrument, :close, :ct, :src, 'commodity')
                ON CONFLICT (instrument, period) DO UPDATE SET
                    close = EXCLUDED.close, crawl_time = EXCLUDED.crawl_time
            """), {"period": r["period"], "instrument": r["instrument"],
                   "close": r["close"], "ct": now, "src": source})
        conn.commit()


def crawl_instrument(ticker: str, instrument: str, engine) -> int:
    import yfinance as yf
    series = yf.download(ticker, period="1y", progress=False, auto_adjust=True)["Close"]
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


def main() -> None:
    engine = _engine()
    total = 0
    for instrument, ticker in INSTRUMENTS.items():
        total += crawl_instrument(ticker, instrument, engine)
    print(f"done: {total} world rows")


if __name__ == "__main__":
    main()
