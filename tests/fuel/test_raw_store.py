import hashlib
import json
from datetime import datetime, timezone

import crawl_tools.fuel_raw_store as rs


def test_raw_key_partitioning():
    ts = datetime(2026, 7, 9, 8, 30, tzinfo=timezone.utc)
    key = rs.raw_key("moit_fuel", ts, "html")
    assert key.startswith("raw/moit_fuel/2026/07/09/")
    assert key.endswith(".html")


def test_land_raw_uploads_payload_and_meta(monkeypatch):
    calls = []
    monkeypatch.setattr(rs, "_upload", lambda b, k, ct: calls.append((k, ct, b)))
    payload = b"<html>ok</html>"
    key = rs.land_raw(payload, "moit_fuel", "http://x", "html", "text/html", 200)
    keys = [c[0] for c in calls]
    assert key in keys
    assert key + ".meta.json" in keys
    meta_bytes = next(c[2] for c in calls if c[0].endswith(".meta.json"))
    meta = json.loads(meta_bytes)
    assert meta["sha256"] == hashlib.sha256(payload).hexdigest()
    assert meta["http_status"] == 200
    assert meta["source_url"] == "http://x"
