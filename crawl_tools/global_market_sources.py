"""Fallback market-data sources for the global index crawler."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

import requests


FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_INDEX_SERIES = {
    "nasdaq_price": "NASDAQCOM",
    "sp500_price": "SP500",
    "dowjones_price": "DJIA",
}


def fetch_fred_history(series_id, days=35, session=requests):
    """Return daily FRED observations as ``YYYY-MM-DD -> float``."""
    end = date.today()
    start = end - timedelta(days=days)
    response = session.get(
        FRED_CSV_URL,
        params={
            "id": series_id,
            "cosd": start.isoformat(),
            "coed": end.isoformat(),
        },
        headers={"User-Agent": "VietDataverse/1.0 market-data fallback"},
        timeout=20,
    )
    response.raise_for_status()

    rows = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
    date_column = "observation_date"
    if not rows.fieldnames or not {date_column, series_id}.issubset(rows.fieldnames):
        raise ValueError(f"Unexpected FRED CSV columns for {series_id}: {rows.fieldnames}")

    result = {}
    for row in rows:
        raw_date = (row.get(date_column) or "").strip()
        raw_close = (row.get(series_id) or "").strip()
        if not raw_date or not raw_close or raw_close.lower() in {".", "n/d", "null"}:
            continue
        close = float(raw_close)
        if close > 0:
            result[raw_date] = close

    if not result:
        raise ValueError(f"FRED returned no valid observations for {series_id}")
    return result


def fill_missing_indices(series, fetcher=fetch_fred_history):
    """Fill missing index dates when Yahoo is absent or lags other markets.

    Return ``column -> added dates`` for source attribution.
    """
    reference_dates = set(series.get("gold_price", {})) | set(series.get("silver_price", {}))
    latest_reference = max(reference_dates) if reference_dates else None
    fallback_dates = {}
    for column, series_id in FRED_INDEX_SERIES.items():
        current = series.setdefault(column, {})
        latest_current = max(current) if current else None
        if latest_current and (not latest_reference or latest_current >= latest_reference):
            continue
        added = set()
        for day, close in fetcher(series_id).items():
            if day not in current:
                current[day] = close
                added.add(day)
        if added:
            fallback_dates[column] = added
    return fallback_dates
