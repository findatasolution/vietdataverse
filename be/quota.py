"""
Quota & rate-limit layer cho API key auth.

Chính sách (đã quyết định):
  - Free tier KHÔNG có API access (chỉ user_level='premium_developer' mới được
    generate key qua /api/v1/developer/generate-key).
  - premium_developer / dev_monthly  → 10,000 req / tháng
  - premium_developer / dev_yearly   → 100,000 req / tháng
  - admin                            → unlimited
  - Burst rate-limit token-bucket in-memory per-process: 10 req/s cho
    premium_developer, 100 req/s cho admin. Khi scale lên multi-worker
    migrate sang Postgres advisory lock / Redis.
  - Quota month reset theo timezone Asia/Ho_Chi_Minh (business VN).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import text

try:
    from zoneinfo import ZoneInfo
    VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
except Exception:  # pragma: no cover — fallback cho môi trường thiếu tzdata
    VN_TZ = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# Plan → quota mapping
# ---------------------------------------------------------------------------

# Default theo user_level (dùng khi không biết plan cụ thể)
QUOTA_BY_LEVEL = {
    "premium_developer": {"monthly": 10_000,  "burst_per_sec": 10},
    "admin":             {"monthly": None,    "burst_per_sec": 100},   # None = unlimited
}

# Override theo plan cụ thể (đọc từ users.current_plan)
QUOTA_BY_PLAN = {
    "dev_monthly": {"monthly": 10_000,  "burst_per_sec": 10},
    "dev_yearly":  {"monthly": 100_000, "burst_per_sec": 20},
}


def get_quota(user_level: str, plan: Optional[str]) -> Optional[dict]:
    """Trả về quota config cho user, hoặc None nếu tier không có API access."""
    if plan and plan in QUOTA_BY_PLAN:
        return QUOTA_BY_PLAN[plan]
    return QUOTA_BY_LEVEL.get(user_level)


# ---------------------------------------------------------------------------
# Quota month helper (Asia/Ho_Chi_Minh)
# ---------------------------------------------------------------------------

def current_quota_month() -> str:
    """'YYYY-MM' theo giờ VN — dùng làm key reset counter hàng tháng."""
    return datetime.now(VN_TZ).strftime("%Y-%m")


def next_month_reset_at() -> datetime:
    """00:00 ngày 1 tháng sau theo giờ VN — cho header X-RateLimit-Reset."""
    now = datetime.now(VN_TZ)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1,
                           hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1,
                       hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# In-memory burst token bucket (per user_id)
# ---------------------------------------------------------------------------

@dataclass
class _Bucket:
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)


_BUCKETS: dict[int, _Bucket] = {}
_BUCKETS_LOCK = threading.Lock()


def _check_burst(user_id: int, burst_per_sec: int) -> bool:
    """Token bucket: capacity=burst, refill=burst/s. True nếu OK, False nếu cạn."""
    if burst_per_sec <= 0:
        return True
    now = time.monotonic()
    with _BUCKETS_LOCK:
        b = _BUCKETS.get(user_id)
        if b is None:
            b = _Bucket(tokens=float(burst_per_sec), last_refill=now)
            _BUCKETS[user_id] = b
        # refill
        elapsed = now - b.last_refill
        b.tokens = min(float(burst_per_sec), b.tokens + elapsed * burst_per_sec)
        b.last_refill = now
        if b.tokens >= 1.0:
            b.tokens -= 1.0
            return True
        return False


# ---------------------------------------------------------------------------
# Main entry point: check + consume
# ---------------------------------------------------------------------------

@dataclass
class QuotaResult:
    allowed: bool
    reason: Optional[str]          # "no_access" | "burst" | "monthly" | None
    monthly_limit: Optional[int]   # None = unlimited
    used_this_month: int
    remaining: Optional[int]
    reset_at: datetime
    burst_per_sec: int


def check_and_consume(
    conn,
    *,
    user_id: int,
    user_level: str,
    plan: Optional[str],
) -> QuotaResult:
    """
    Gọi trong cùng transaction với middleware auth. Raises no exception — trả
    QuotaResult để middleware tự map sang HTTPException.

    - Nếu tier không có API access → QuotaResult(allowed=False, reason='no_access').
    - Nếu cạn burst → allowed=False, reason='burst'.
    - Nếu cạn monthly → allowed=False, reason='monthly'.
    - Nếu OK → allowed=True, INCREMENT counter và trả remaining.
    """
    quota = get_quota(user_level, plan)
    reset_at = next_month_reset_at()

    if quota is None:
        return QuotaResult(
            allowed=False, reason="no_access",
            monthly_limit=0, used_this_month=0, remaining=0,
            reset_at=reset_at, burst_per_sec=0,
        )

    monthly_limit = quota["monthly"]      # None = unlimited
    burst = quota["burst_per_sec"]

    # 1. Burst check (in-memory)
    if not _check_burst(user_id, burst):
        # Đọc used để trả về header — không tăng counter
        used = _read_used(conn, user_id)
        remaining = None if monthly_limit is None else max(0, monthly_limit - used)
        return QuotaResult(
            allowed=False, reason="burst",
            monthly_limit=monthly_limit, used_this_month=used,
            remaining=remaining, reset_at=reset_at, burst_per_sec=burst,
        )

    # 2. Monthly quota check + atomic increment
    qmonth = current_quota_month()

    # UPSERT + increment atomically; nếu cạn thì rollback
    row = conn.execute(text("""
        INSERT INTO api_usage_monthly (user_id, quota_month, request_count, updated_at)
        VALUES (:uid, :qm, 1, NOW())
        ON CONFLICT (user_id, quota_month)
        DO UPDATE SET request_count = api_usage_monthly.request_count + 1,
                      updated_at    = NOW()
        RETURNING request_count
    """), {"uid": user_id, "qm": qmonth}).fetchone()
    used = row[0] if row else 1

    if monthly_limit is not None and used > monthly_limit:
        # Đã increment rồi — rollback bằng decrement để giữ counter chính xác
        conn.execute(text("""
            UPDATE api_usage_monthly
            SET request_count = request_count - 1
            WHERE user_id = :uid AND quota_month = :qm
        """), {"uid": user_id, "qm": qmonth})
        return QuotaResult(
            allowed=False, reason="monthly",
            monthly_limit=monthly_limit, used_this_month=monthly_limit,
            remaining=0, reset_at=reset_at, burst_per_sec=burst,
        )

    remaining = None if monthly_limit is None else max(0, monthly_limit - used)
    return QuotaResult(
        allowed=True, reason=None,
        monthly_limit=monthly_limit, used_this_month=used,
        remaining=remaining, reset_at=reset_at, burst_per_sec=burst,
    )


def _read_used(conn, user_id: int) -> int:
    qmonth = current_quota_month()
    row = conn.execute(text("""
        SELECT request_count FROM api_usage_monthly
        WHERE user_id = :uid AND quota_month = :qm
    """), {"uid": user_id, "qm": qmonth}).fetchone()
    return int(row[0]) if row else 0


def read_usage(conn, user_id: int, user_level: str, plan: Optional[str]) -> dict:
    """Cho /key-info hiển thị dashboard usage — không consume."""
    quota = get_quota(user_level, plan)
    used = _read_used(conn, user_id)
    if quota is None:
        return {
            "monthly_limit": 0, "used_this_month": used, "remaining": 0,
            "reset_at": next_month_reset_at().isoformat(),
            "plan": plan, "burst_per_sec": 0,
        }
    limit = quota["monthly"]
    remaining = None if limit is None else max(0, limit - used)
    return {
        "monthly_limit": limit, "used_this_month": used,
        "remaining": remaining,
        "reset_at": next_month_reset_at().isoformat(),
        "plan": plan, "burst_per_sec": quota["burst_per_sec"],
    }
