"""The container's timezone must not be able to move a paid plan's expiry.

Background: every DB timestamp in this project is naive UTC, because Neon's
sessions run on `TimeZone = GMT` and libpq takes its zone from `PGTZ`, never
from `TZ`. `datetime.now()` on the Python side is *local*, so it matched only
because `Dockerfile`/`docker-compose.yml` set no `TZ`. Setting
`TZ=Asia/Ho_Chi_Minh` — natural for a Vietnamese product — would have expired
every plan 7 hours early with nothing to show for it in a log.

These tests fail if that accident is ever relied on again.
"""
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]

# Files whose clock a database reads back. `premium_expiry` alone is compared
# both in Python (middleware, payment) and in SQL (`routers/admin.py`'s
# `premium_expiry < NOW()`), so UTC is the only value that can satisfy both.
UTC_ONLY_FILES = [
    "be/middleware.py",
    "be/payment.py",
    "be/services/subscription.py",
    "be/services/credit.py",
    "be/services/api_entitlement.py",
    "be/routers/student_verify.py",
    "be/routers/seller.py",
    "be/routers/knowledge.py",
]

_LOCAL_CLOCK = re.compile(r"datetime\.now\(\s*\)")
_DEPRECATED_UTC = re.compile(r"datetime\.utcnow\(\)")


def _run(code: str, tz: str | None) -> str:
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO / "be")}
    if tz:
        env["TZ"] = tz
    return subprocess.run([sys.executable, "-c", code], env=env, check=True,
                          capture_output=True, text=True).stdout.strip()


_PROBE = (
    "import time, datetime\n"
    "try: time.tzset()\n"
    "except AttributeError: pass\n"
    "from core.timeutils import utcnow\n"
    "print(utcnow().isoformat(), datetime.datetime.now().isoformat())\n"
)


def test_utcnow_is_identical_under_any_tz():
    """Asia/Ho_Chi_Minh and UTC must produce the same instant."""
    vn_utcnow, vn_localnow = _run(_PROBE, "Asia/Ho_Chi_Minh").split()
    utc_utcnow, _ = _run(_PROBE, "UTC").split()

    import datetime as dt
    drift = abs(dt.datetime.fromisoformat(vn_utcnow) - dt.datetime.fromisoformat(utc_utcnow))
    assert drift < dt.timedelta(seconds=30), f"utcnow() moved with TZ: {drift}"

    # And it must genuinely differ from the local clock under VN time —
    # otherwise the test above would pass on a machine that is already UTC
    # while proving nothing.
    offset = dt.datetime.fromisoformat(vn_localnow) - dt.datetime.fromisoformat(vn_utcnow)
    assert dt.timedelta(hours=6, minutes=45) < offset < dt.timedelta(hours=7, minutes=15), (
        f"expected datetime.now() to sit +7h under Asia/Ho_Chi_Minh, got {offset}")


def test_no_local_clock_where_a_database_compares_it():
    """Guard against reintroducing `datetime.now()` on a DB-facing path.

    A helper-free `datetime.now()` is not wrong everywhere — `be/main.py`'s
    health payload and `be/quota.py`'s deliberate `datetime.now(VN_TZ)` are
    both fine. It is wrong in exactly these files, so the check names them.
    """
    offenders = []
    for rel in UTC_ONLY_FILES:
        src = (REPO / rel).read_text()
        for pattern, label in ((_LOCAL_CLOCK, "datetime.now()"),
                               (_DEPRECATED_UTC, "datetime.utcnow()")):
            for m in pattern.finditer(src):
                line = src.count("\n", 0, m.start()) + 1
                offenders.append(f"{rel}:{line} uses {label} — use core.timeutils.utcnow()")
    assert not offenders, "\n".join(offenders)
