import os

# CORS
_raw_cors_origins = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "https://vietdataverse.online,https://www.vietdataverse.online,http://localhost:3000,http://127.0.0.1:5500"
)
ALLOW_ORIGINS = [o.strip() for o in _raw_cors_origins.split(",") if o.strip()]

# Allowlists for exchange rate endpoint (prevents column-name injection)
ALLOWED_BANKS = frozenset(["SBV", "BID", "TCB", "VCB", "ACB", "VPB", "MBB", "STB", "TPB", "HDB"])
ALLOWED_CURRENCIES = frozenset([
    "USD", "EUR", "JPY", "GBP", "CNY", "AUD", "SGD",
    "KRW", "THB", "CAD", "CHF", "HKD", "NZD", "TWD", "MYR"
])
