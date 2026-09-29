"""One clock for everything that touches a database timestamp.

Every `TIMESTAMP` column in this project is naive and holds **UTC**, because
that is what the databases themselves write: Neon runs its sessions on
`TimeZone = GMT`, so `NOW()` — and every `DEFAULT NOW()` — lands in UTC.
libpq takes its session zone from `PGTZ`, never from the container's `TZ`,
so no environment variable can move the SQL side.

The Python side is not so fixed. `datetime.now()` returns *local* time, so it
agrees with those columns only while the process happens to run on UTC. The
backend container does today — `Dockerfile` and `docker-compose.yml` set no
`TZ` — and that accident was the only thing keeping `premium_expiry < now()`
honest. Setting `TZ=Asia/Ho_Chi_Minh`, an entirely natural thing to do for a
Vietnamese product (`integrations/google-sheets/appsscript.json` already
does), would have expired every paid plan 7 hours early, silently. On a
7-day trial that is 4% of the purchase.

So: **`utcnow()` for anything a database will store or compare, always.**
Local time belongs to the presentation layer, and a deliberate zone
(`be/quota.py` counts a quota month in `Asia/Ho_Chi_Minh` on purpose, and
pairs it with `AT TIME ZONE 'Asia/Ho_Chi_Minh'` on the SQL side) belongs to
whoever states it explicitly.

Naive on purpose: the columns are `TIMESTAMP`, not `TIMESTAMPTZ`, and handing
psycopg an aware datetime for a naive column invites a second conversion.
`datetime.utcnow()` would do the same job but is deprecated from Python 3.12.
"""
from datetime import datetime, timezone

__all__ = ["utcnow"]


def utcnow() -> datetime:
    """Current UTC time as a naive `datetime` — identical under any `TZ`."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
