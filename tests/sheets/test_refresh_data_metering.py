"""One refresh-data request must cost exactly one quota unit.

The Sheets template's whole quota promise (1 call per load, ~720/month for a
file left open) rests on this. refresh-data gathers nine datasets by calling
their handlers in-process; if any of those went back through the metering
middleware, one load would cost ten. This drives the real app and counts.
"""
import os

# CI runs without secrets. be/database.py refuses to import without a URL; the
# engine is lazy, and every handler that would touch it is stubbed below, so a
# placeholder that can never connect is enough.
os.environ.setdefault("CRAWLING_BOT_DB", "postgresql://ci:ci@127.0.0.1:1/none")

import pytest
from fastapi.responses import Response
from fastapi.testclient import TestClient

import middleware
from routers import market_data, vn30_data


@pytest.fixture
def client(monkeypatch):
    consumed = []

    async def fake_auth(request, api_key):
        # Stands in for _auth_via_api_key, which is where check_and_consume
        # increments the monthly counter — one call here is one unit spent.
        consumed.append(request.url.path)
        request.state.user = {"user_id": 1, "api_key_id": 1, "user_level": "free"}
        return True

    async def noop_log(*args, **kwargs):
        return None

    async def fake_handler(request, **kwargs):
        return Response(content="date,a\n2026-09-29,1.5\n", media_type="text/csv")

    monkeypatch.setattr(middleware, "_auth_via_api_key", fake_auth)
    monkeypatch.setattr(middleware, "_log_api_call", noop_log)
    for name in ("get_gold_data", "get_silver_data", "get_sbv_interbank_data",
                 "get_sbv_central_rate", "get_term_deposit_data", "get_global_macro_data"):
        monkeypatch.setattr(market_data, name, fake_handler)
    for name in ("get_macro_cpi", "get_macro_gdp", "get_macro_trade"):
        monkeypatch.setattr(vn30_data, name, fake_handler)

    from main import app
    # No `with`: startup hooks touch real databases; the request path does not.
    yield TestClient(app), consumed


def test_one_refresh_is_one_quota_unit(client):
    c, consumed = client
    r = c.get("/api/v1/excel/refresh-data?period=1y&format=csv&api_key=k&_r=2")
    assert r.status_code == 200
    body = r.text.splitlines()
    assert body[0].startswith("dataset,")
    assert {line.split(",")[0] for line in body[1:]} == {
        "gold", "silver", "interbank", "fx", "deposit", "global", "cpi", "gdp", "trade"}
    assert consumed == ["/api/v1/excel/refresh-data"]
