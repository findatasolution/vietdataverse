"""
File security scan — Phase 1: custom rules only.
ClamAV deferred to Phase 2.

Checks (in order):
  1. File size (max 10 MB)
  2. Empty file guard
  3. Extension whitelist
  4. Magic byte signatures (reject executables, archives)
  5. UTF-8 decode check (all allowed formats must be text)
  6. Regex scan for common secrets / credentials
"""
import hashlib
import os
import re
from typing import Any

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTS = {".md", ".json", ".yaml", ".yml", ".csv", ".txt"}

# Magic byte → human-readable label. Keys are checked as prefix of file bytes.
MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x4d\x5a",          "PE executable (Windows)"),
    (b"\x7f\x45\x4c\x46", "ELF executable (Linux)"),
    (b"\xca\xfe\xba\xbe", "Mach-O executable (macOS)"),
    (b"\x50\x4b\x03\x04", "ZIP archive (may contain executables)"),
    (b"\x1f\x8b\x08",     "gzip archive"),
    (b"\x42\x5a\x68",     "bzip2 archive"),
    (b"\x52\x61\x72\x21", "RAR archive"),
    (b"\x25\x50\x44\x46", "PDF file"),          # PDFs not in allowed exts anyway
]

# (compiled regex, label) pairs for secret detection
SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"AKIA[0-9A-Z]{16}"),                                         "AWS Access Key ID"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH |DSA |EC |PGP )?PRIVATE KEY"), "Private key block"),
    (re.compile(r"sk-[a-zA-Z0-9]{32,}"),                                      "OpenAI API key"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"),                                      "GitHub PAT"),
    (re.compile(r"xox[baprs]-[0-9a-zA-Z-]+"),                                 "Slack token"),
    (re.compile(r"AIza[0-9A-Za-z\-_]{35}"),                                   "Google API key"),
    (re.compile(
        r"""(?:api[_-]?key|password|secret|token)[\s:=]+['"][a-zA-Z0-9_\-]{20,}['"]""",
        re.IGNORECASE,
    ), "Suspicious credential assignment"),
    (re.compile(r"postgres(?:ql)?://[^:]+:[^@]+@"),                          "PostgreSQL DSN with credentials"),
    (re.compile(r"mysql://[^:]+:[^@]+@"),                                     "MySQL DSN with credentials"),
]


def compute_sha256(data: bytes) -> str:
    """Return hex SHA-256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def scan_file(data: bytes, filename: str) -> dict[str, Any]:
    """
    Run all Phase 1 security checks on file bytes.

    Returns:
        {
          "result":  "clean" | "infected" | "error",
          "detail":  dict with reason/detected fields,
          "sha256":  str (hex),
          "scanner": "custom_rules"
        }
    """
    sha = compute_sha256(data)
    scanner = "custom_rules"

    def _infected(reason: str, **extra) -> dict:
        detail: dict[str, Any] = {"reason": reason}
        detail.update(extra)
        return {"result": "infected", "detail": detail, "sha256": sha, "scanner": scanner}

    # 1. Size check
    if len(data) > MAX_FILE_SIZE:
        return _infected(f"File too large: {len(data):,} bytes (max {MAX_FILE_SIZE:,})")

    # 2. Empty file
    if len(data) == 0:
        return _infected("Empty file")

    # 3. Extension check
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTS:
        return _infected(f"Extension not allowed: '{ext}' — accepted: {sorted(ALLOWED_EXTS)}")

    # 4. Magic byte check
    for sig, label in MAGIC_SIGNATURES:
        if data.startswith(sig):
            return _infected(f"Suspicious magic bytes: {label}")

    # 5. UTF-8 decode (all our formats must be valid text)
    try:
        text_content = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _infected(f"Not valid UTF-8 text: {exc}")

    # 6. Secret regex scan
    detected = []
    for pattern, label in SECRET_PATTERNS:
        matches = pattern.findall(text_content)
        if matches:
            detected.append({"type": label, "count": len(matches)})

    if detected:
        return _infected("File contains potential secrets or credentials", detected=detected)

    return {
        "result":  "clean",
        "detail":  {
            "size":    len(data),
            "ext":     ext,
            "scanner": scanner,
        },
        "sha256":  sha,
        "scanner": scanner,
    }


# ============================================================
# Extended checks for zero-admin pipeline
# ============================================================

def check_format_validity(data: bytes, ext: str) -> dict:
    """Parse based on extension to verify file integrity. Returns {result, detail}."""
    import json
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"result": "infected", "detail": {"reason": "Not valid UTF-8"}}

    ext = ext.lower().lstrip(".")
    if ext == "json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            return {"result": "infected", "detail": {"reason": f"Invalid JSON: {e.msg}"}}
    elif ext in ("yaml", "yml"):
        try:
            import yaml
            yaml.safe_load(text)
        except Exception as e:
            return {"result": "infected", "detail": {"reason": f"Invalid YAML: {e}"}}
    elif ext == "csv":
        try:
            import csv
            import io
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if len(rows) < 2:
                return {"result": "infected", "detail": {"reason": "CSV too short (< 2 rows)"}}
        except Exception as e:
            return {"result": "infected", "detail": {"reason": f"Invalid CSV: {e}"}}
    # md / txt: no parser, accepted if UTF-8
    return {"result": "clean", "detail": {"format": ext}}


def check_min_content(data: bytes, description: str) -> dict:
    """Min content guard: file >= 100 bytes, description >= 50 chars."""
    if len(data) < 100:
        return {"result": "infected", "detail": {"reason": "File too small (< 100 bytes)"}}
    if len((description or "").strip()) < 50:
        return {"result": "infected", "detail": {"reason": "Description too short (< 50 chars)"}}
    return {"result": "clean", "detail": {"size": len(data), "desc_len": len(description)}}
