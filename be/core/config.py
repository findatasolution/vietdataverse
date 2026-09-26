import os

# ── Pricing constants ──────────────────────────────────────────────────────────
# Hardcoded for MVP; revisit when FX volatility exceeds 3%
USD_VND_RATE = 25500       # 1 USD = 25,500 VND
VND_PER_CREDIT = 1000      # 1 credit = 1,000 VND
# Derived: $1 = 25.5 credits → always ceil() when debiting buyer

# CORS
_raw_cors_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "https://vietdataverse.online,https://www.vietdataverse.online,http://localhost:3000,http://localhost:5500,http://localhost:8000,http://localhost:8080,http://127.0.0.1:5500,http://127.0.0.1:8080"
)
# The Office Add-in host allowlist was dropped on 2026-09-25 with the Excel
# flow. It included "null", which Office desktop sideload sends as its Origin —
# a value any sandboxed iframe or file:// page can also send, so keeping it for
# a feature that no longer exists would widen CORS for nothing.
ALLOW_ORIGINS = [o.strip() for o in _raw_cors_origins.split(",") if o.strip()]

# Allowlists for exchange rate endpoint (prevents column-name injection)
ALLOWED_BANKS = frozenset(["SBV", "BID", "TCB", "VCB", "ACB", "VPB", "MBB", "STB", "TPB", "HDB"])
ALLOWED_CURRENCIES = frozenset([
    "USD", "EUR", "JPY", "GBP", "CNY", "AUD", "SGD",
    "KRW", "THB", "CAD", "CHF", "HKD", "NZD", "TWD", "MYR"
])
