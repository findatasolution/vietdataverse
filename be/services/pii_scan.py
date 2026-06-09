"""PII detection for Vietnam (CCCD, CMND, phone, email). Block upload if detected."""
import re
from typing import Dict

# CCCD (12 digits, issued since 2021)
PATTERN_CCCD = re.compile(r"(?<!\d)\d{12}(?!\d)")
# CMND old (9 digits)
PATTERN_CMND = re.compile(r"(?<!\d)\d{9}(?!\d)")
# VN phone: +84 or 0, then mobile prefix (3|5|7|8|9), then 8 digits
PATTERN_PHONE_VN = re.compile(r"(?:\+84|0)(?:3|5|7|8|9)\d{8}\b")
# Email (info-level, high threshold)
PATTERN_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

# Block if count >= threshold
THRESHOLDS = {
    "CCCD": 1,        # 1 CCCD = fail
    "CMND": 3,        # 3+ CMND (9 digits có nhiều false positive)
    "VN phone": 5,    # 5+ phone numbers
    "Email": 20,      # 20+ emails (contact info OK)
}


def scan_pii(text: str) -> Dict:
    """Detect VN PII in text. Returns {result, detected, failed, scanner}."""
    if not isinstance(text, str):
        return {"result": "clean", "detected": [], "scanner": "pii_regex"}

    counts = {
        "CCCD": len(PATTERN_CCCD.findall(text)),
        "CMND": len(PATTERN_CMND.findall(text)),
        "VN phone": len(PATTERN_PHONE_VN.findall(text)),
        "Email": len(PATTERN_EMAIL.findall(text)),
    }

    # Subtract CCCD (12 digits) from CMND (9 digits) false positives
    # CCCD already matches non-digit boundaries so they don't double-count

    detected = []
    failed = []
    for pii_type, count in counts.items():
        if count > 0:
            detected.append({"type": pii_type, "count": count})
            if count >= THRESHOLDS[pii_type]:
                failed.append({
                    "type": pii_type,
                    "count": count,
                    "threshold": THRESHOLDS[pii_type],
                })

    if failed:
        return {
            "result": "infected",
            "detected": detected,
            "failed": failed,
            "scanner": "pii_regex",
            "reason": "Contains PII above threshold",
        }
    return {"result": "clean", "detected": detected, "scanner": "pii_regex"}
