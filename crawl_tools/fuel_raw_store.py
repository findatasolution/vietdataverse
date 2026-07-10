"""Bronze landing helper — write immutable raw payloads (+ provenance sidecar)
to the Cloudflare R2 raw zone (`R2_BUCKET_RAW`).

Keeping raw fetches separate from parsing gives replayability (re-parse without
re-fetching), auditability (sha256 + source_url + fetch_ts), and clean backfills.
See docs/research/fuel-price-forecast-design.md §5.
"""
import hashlib
import json
import os
from datetime import datetime, timezone


def raw_key(source: str, fetch_ts: datetime, ext: str) -> str:
    """Partitioned, timestamped object key: raw/{source}/{yyyy}/{mm}/{dd}/{ISO}.{ext}"""
    d = fetch_ts.astimezone(timezone.utc)
    return f"raw/{source}/{d:%Y/%m/%d}/{d:%Y-%m-%dT%H-%M-%SZ}.{ext}"


def _upload(body: bytes, key: str, content_type: str) -> None:
    import boto3  # lazy import — only needed when actually landing

    client = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    client.put_object(
        Bucket=os.environ["R2_BUCKET_RAW"], Key=key, Body=body, ContentType=content_type
    )


def land_raw(payload: bytes, source: str, source_url: str, ext: str,
             content_type: str, http_status: int) -> str:
    """Upload the payload and a `<key>.meta.json` provenance sidecar. Returns the object key."""
    ts = datetime.now(timezone.utc)
    key = raw_key(source, ts, ext)
    _upload(payload, key, content_type)
    meta = {
        "source_url": source_url,
        "fetch_ts": ts.isoformat(),
        "http_status": http_status,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    _upload(json.dumps(meta).encode(), key + ".meta.json", "application/json")
    return key
