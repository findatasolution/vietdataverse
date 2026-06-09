"""
Cloudflare R2 storage client (S3-compatible).

Required env vars:
    R2_ACCOUNT_ID           — Cloudflare account ID
    R2_ACCESS_KEY_ID        — R2 access key
    R2_SECRET_ACCESS_KEY    — R2 secret key
    R2_BUCKET_KNOWLEDGE     — bucket name for knowledge assets

All functions raise ValueError (not silent) when env vars are missing,
so callers can show a clear error instead of crashing.
"""

import hashlib
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_REQUIRED_VARS = (
    "R2_ACCOUNT_ID",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_BUCKET_KNOWLEDGE",
)


def _get_client():
    """
    Build and return a boto3 S3 client pointed at Cloudflare R2.
    Raises ValueError if any required env var is missing.
    """
    missing = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise ValueError(
            f"R2 not configured — missing env vars: {', '.join(missing)}"
        )

    import boto3  # lazy import — only fail at call time, not module load time

    account_id = os.environ["R2_ACCOUNT_ID"]
    endpoint    = f"https://{account_id}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _bucket() -> str:
    bucket = os.getenv("R2_BUCKET_KNOWLEDGE", "")
    if not bucket:
        raise ValueError("R2_BUCKET_KNOWLEDGE env var is not set")
    return bucket


# ── Public interface ──────────────────────────────────────────────────────────

def upload_file(file_bytes: bytes, file_key: str, content_type: str) -> str:
    """
    Upload raw bytes to R2 under the given object key.

    Args:
        file_bytes:   Raw file content.
        file_key:     R2 object key, e.g. "knowledge/crewai-vietnam-macro-v1.md".
        content_type: MIME type, e.g. "text/markdown" or "application/json".

    Returns:
        file_key unchanged (for storage in DB).

    Raises:
        ValueError if R2 env vars are missing.
    """
    client = _get_client()
    client.put_object(
        Bucket=_bucket(),
        Key=file_key,
        Body=file_bytes,
        ContentType=content_type,
    )
    logger.info("R2 upload OK: key=%s size=%d", file_key, len(file_bytes))
    return file_key


def compute_sha256(file_bytes: bytes) -> str:
    """Return hex SHA-256 of file_bytes for integrity storage."""
    return hashlib.sha256(file_bytes).hexdigest()


def generate_download_url(file_key: str, expiry_secs: int = 86400, force_download: bool = True) -> str:
    """
    Generate a presigned GET URL for a private R2 object.

    Args:
        file_key:       R2 object key.
        expiry_secs:    URL validity in seconds (default 24 h).
        force_download: if True, set Content-Disposition: attachment so browser downloads
                        instead of rendering inline (avoids UTF-8 encoding issues for .md).

    Returns:
        Presigned URL string.

    Raises:
        ValueError if R2 env vars are missing.
    """
    client = _get_client()
    # Extract filename from key for Content-Disposition
    filename = file_key.split("/")[-1] if file_key else "download"

    params = {"Bucket": _bucket(), "Key": file_key}
    if force_download:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        # Also force UTF-8 charset for text content
        params["ResponseContentType"] = "text/plain; charset=utf-8"

    url = client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expiry_secs,
    )
    return url


def generate_preview(file_key: str, preview_pct: int, fmt: str) -> str:
    """
    Download the file from R2 and return a truncated preview string.

    Rules:
        .md   — return the first (preview_pct %) of lines.
        .json — parse as JSON, return the first (preview_pct %) of top-level keys.
        .yaml — return the first (preview_pct %) of lines (same as .md).

    Args:
        file_key:    R2 object key.
        preview_pct: 0–40 (percentage of content to surface).
        fmt:         "md" | "json" | "yaml"

    Returns:
        String preview content.

    Raises:
        ValueError if R2 env vars are missing or fmt is unsupported.
    """
    if preview_pct <= 0:
        return ""

    client = _get_client()
    response = client.get_object(Bucket=_bucket(), Key=file_key)
    raw_bytes: bytes = response["Body"].read()

    if fmt == "json":
        try:
            data = json.loads(raw_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ""

        if not isinstance(data, dict):
            # If it's an array or scalar, fall back to raw line preview
            lines = raw_bytes.decode("utf-8", errors="replace").splitlines()
            cutoff = max(1, len(lines) * preview_pct // 100)
            return "\n".join(lines[:cutoff])

        all_keys = list(data.keys())
        cutoff   = max(1, len(all_keys) * preview_pct // 100)
        preview_dict = {k: data[k] for k in all_keys[:cutoff]}
        return json.dumps(preview_dict, ensure_ascii=False, indent=2)

    elif fmt in ("md", "yaml"):
        text  = raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()
        if not lines:
            return ""
        cutoff = max(1, len(lines) * preview_pct // 100)
        return "\n".join(lines[:cutoff])

    else:
        raise ValueError(f"Unsupported format for preview generation: {fmt!r}")
