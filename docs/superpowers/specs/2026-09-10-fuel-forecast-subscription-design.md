# Platform subscriptions (wallet-billed) + Fuel Forecast gated API — design

Status: approved 2026-09-10 (design confirmed in chat; this doc is the written
record before implementation planning). Extends the existing Agent-Market
wallet (`credit_balance`/`credit_ledger`, see `be/services/credit.py`), does
not replace it.

> **Superseded in two places on 2026-09-12** (product decisions; the rest of
> this doc stands). Root `CLAUDE.md` "Fuel Forecast subscription" is the
> current description.
>
> 1. **Grace period is 2 days, not 3** (`GRACE_PERIOD_DAYS` in
>    `be/services/subscription.py`). Every "3 days" below reads as 2.
> 2. **Cancelling is scheduled, not immediate.** `cancel_subscription()` sets
>    the new `platform_subscriptions.cancel_at_period_end` flag (migration 015)
>    and writes a `cancel_scheduled` event; access runs to `current_period_end`,
>    and `run_billing_cycle`'s new `expire` action then ends it without
>    charging. Still no proration/refund. A row with no paid time left
>    (`past_due`, or `active` past its period end) still cancels outright —
>    scheduling one of those would leave it eligible for the cron's
>    reactivation charge. `POST /subscribe` on a scheduled-to-cancel row is the
>    undo, and charges nothing.

## Problem

Fuel Forecast (`be/fuel/*`, DB `FUEL_FORECAST_DB`) is a working, validated
model (delta-world-v1, see `CLAUDE.md` "Fuel forecast model") with no product
surface at all — no API route, no page, no way to charge for it. The decision
this session: sell it as a monthly subscription, billed by deducting straight
from the same wallet users already top up for Agent Market (PayOS → credits),
not a separate payment flow. This is also meant to be the **first of possibly
several** "platform API data" subscription products, not fuel-forecast-only —
so the primitive (catalog + subscription + billing) is generic even though
only one product uses it today.

## Decisions

| Question | Decision | Why |
|---|---|---|
| Payment rail | Deduct from existing wallet (`credit_balance`/`credit_ledger`), not a new PayOS recurring-charge flow | Explicit user instruction — "trừ thẳng vào ví", reusing what Agent Market already has, no new payment integration. |
| Plans | Free (no subscription row) + one paid tier "Advanced", 60 credits/mo (60.000đ), displayed with list price 120 credits struck through (50% launch discount) | User: "sub có 1 loại thôi là free và advanced plan (60k discount 50%)". |
| Free-tier scope | Historical prices + `base` scenario only, no low/high band, no `k`/R²/skill breakdown | Matches the locked/unlocked split already prototyped in the artifact demo this session. |
| Insufficient balance at renewal | `past_due` for 3 days, daily retry, auto-cancel if still unpaid after grace | User: "Grace period 3 ngày (Recommended)" — avoids forcing a manual re-subscribe for a user who tops up a day late. |
| Scope of this build | Build the generic subscription engine **and** the gated Fuel Forecast endpoint together | User: "Làm cả 2" — fuel-forecast is the only consumer today, no value in stopping short of wiring it. |
| Billing history | Dedicated event log + endpoint + UI section, not a filtered view of `credit_ledger` | User pushed back on reusing wallet/transactions — `credit_ledger` only records money that actually moved, so a failed/insufficient-balance renewal attempt (a real, user-relevant event) would be invisible in it. |
| Refunds on cancel | None — no proration | User confirmed this is fine as-is. |
| Legal (NĐ169) | Out of scope for this build | User confirmed — building the mechanism is not the same as flipping billing on for real customers; BACKLOG's legal gate still applies before that. |
| Product catalog vs Knowledge Market | Separate tables (`platform_products`/`platform_subscriptions`), not reusing `knowledge_products` | `knowledge_products` is a seller-marketplace model (approval workflow, 90/10 revenue split via `seller_earnings`) — a VDV-owned recurring product has neither a seller nor a one-time-purchase shape. Mixing them would force marketplace fields onto a platform product for no reason. |

## Data model (new tables, `USER_DB`/knowledge engine — same DB as `credit_balance`)

```sql
CREATE TABLE platform_products (
  code                 VARCHAR(60) PRIMARY KEY,      -- 'fuel-forecast-advanced'
  name                 TEXT NOT NULL,
  price_credits        INT NOT NULL,                 -- 60
  list_price_credits   INT,                           -- 120, for strikethrough display; NULL = no discount shown
  billing_period_days  INT NOT NULL DEFAULT 30,
  active               BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE platform_subscriptions (
  id                 SERIAL PRIMARY KEY,
  user_id            INT NOT NULL,
  product_code       VARCHAR(60) NOT NULL REFERENCES platform_products(code),
  status             VARCHAR(20) NOT NULL,            -- 'active' | 'past_due' | 'cancelled'
  current_period_end TIMESTAMP NOT NULL,
  grace_until        TIMESTAMP,                       -- set when status='past_due'; NULL otherwise
  created_at         TIMESTAMP NOT NULL DEFAULT NOW(),
  cancelled_at       TIMESTAMP,
  UNIQUE (user_id, product_code)                       -- one subscription per user per product
);

CREATE TABLE platform_subscription_events (
  id              SERIAL PRIMARY KEY,
  subscription_id INT NOT NULL REFERENCES platform_subscriptions(id),
  event_type      VARCHAR(20) NOT NULL,   -- 'created'|'charged'|'charge_failed'|'past_due'|'cancelled'|'reactivated'
  amount_credits  INT,                    -- NULL for non-monetary events (past_due, cancelled)
  note            TEXT,
  created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_platform_sub_events_sub ON platform_subscription_events (subscription_id, created_at DESC);
```

`UNIQUE (user_id, product_code)` means re-subscribing after a cancellation
reuses the same row (reset to `active`, new `current_period_end`) rather than
inserting a second one — keeps history on one subscription id.

## Billing engine — `be/services/subscription.py` (same style as `credit.py`)

Reuses the atomic pattern already in `purchase_product()`: `engine.begin()`,
`SELECT ... FOR UPDATE` on the balance row, debit ledger + balance together,
never a bare balance write without a matching ledger row.

```python
def subscribe(user_id: int, product_code: str) -> dict:
    """
    - Raises ValueError if product not found/inactive.
    - If an existing row for (user_id, product_code) is 'cancelled', reactivate it
      (status='active', new current_period_end) instead of inserting a new row.
    - Raises ValueError if already 'active' or 'past_due' for this product.
    - Locks credit_balance FOR UPDATE, raises InsufficientCredits if < price_credits.
    - Debits ledger (kind='subscription_charge', ref_type='subscription', ref_id=<sub id>).
    - Writes platform_subscription_events: 'created' (+ 'charged' with amount).
    Returns: {"subscription_id", "current_period_end", "balance_after"}
    """

def cancel_subscription(user_id: int, product_code: str) -> dict:
    """
    Sets status='cancelled', cancelled_at=now(). No refund/proration (confirmed).
    Writes event 'cancelled'. Idempotent: cancelling an already-cancelled
    subscription is a no-op returning the same state, not an error.
    """

def run_billing_cycle(now: datetime | None = None) -> dict:
    """
    Called by the daily cron. Two passes, both under row locks per subscription
    (not one big transaction — a single stuck row must not block every other
    renewal):

    1. Renewals due: status='active' AND current_period_end <= now.
       - Enough balance -> debit, extend current_period_end by billing_period_days,
         event 'charged'.
       - Not enough -> status='past_due', grace_until = now + 3 days,
         event 'charge_failed'.

    2. Past-due retries: status='past_due'.
       - Enough balance now -> debit, status='active', extend period from now
         (not from the original due date — a late payment buys a fresh 30 days,
         it does not backdate), event 'charged' + 'reactivated'.
       - Still not enough AND now > grace_until -> status='cancelled',
         event 'cancelled' (note: "grace period expired").
       - Still not enough AND within grace -> no-op, no event (avoid spamming
         one event per day of an ongoing shortfall — 'charge_failed' already
         recorded the start of it).

    Returns counts: {"renewed": n, "past_due": n, "cancelled": n} — printed by
    the CLI entrypoint so the cron log always states what happened, never just
    "done" (same "fail loud, log real numbers" lesson from the MOIT crawler fix
    this session — see CLAUDE.md "Fuel (domestic) crawl").
    """

def has_active_subscription(user_id: int | None, product_code: str) -> bool:
    """Pure lookup helper for gating. user_id=None (anonymous) -> False, no query."""

def list_subscription_history(user_id: int, limit=50, offset=0) -> list[dict]:
    """platform_subscription_events joined to platform_subscriptions, filtered
    to this user's subscriptions, newest first."""
```

`InsufficientCredits` reused from `credit.py` (already defined there).

## Cron

New `.github/workflows/subscription-billing.yml`, daily, an odd non-`:00`/`:30`
minute per the repo's own scheduling rule (e.g. `11 3 * * *`), one step:
`python be/services/subscription.py --run-billing-cycle`. The script prints
the returned counts and exits non-zero only on an actual exception (DB
unreachable, etc.) — a normal run with 0 renewals due is success, not silence
about failure, matching the distinction already made for the fuel crawler
(0 renewals is a legitimate outcome; a crashed DB connection is not).

## API — `be/routers/subscription.py`, mount `/api/v1/subscriptions`

```
GET  /api/v1/subscriptions/plans              — list platform_products (public, no auth)
GET  /api/v1/subscriptions/me                 — current user's subscription rows (auth)
POST /api/v1/subscriptions/subscribe {code}   — subscribe (auth)
POST /api/v1/subscriptions/cancel   {code}    — cancel (auth)
GET  /api/v1/subscriptions/history?limit&offset — event history, this user only (auth)
```

Response envelope matches the platform standard already used everywhere else:
`{"success": true, "source": "subscriptions", "count": N, "data": ...}`.

## Fuel Forecast endpoint — `be/routers/fuel_forecast.py`, mount `/api/v1/fuel-forecast`

```
GET /api/v1/fuel-forecast/{fuel}   fuel in {RON95, E5RON92, DO005S}
```

- Reads history from `fuel_price_cycle`, latest run from `fuel_forecast`
  (both already populated by the existing pipeline — no new crawler work).
- `has_active_subscription(user_id, 'fuel-forecast-advanced')`:
  - `False` -> history + `base` scenario rows only, `breakdown` stripped to
    just `disclaimer` (no `k`/`resid_std`/`sigma_world` — those are the paid
    value, per the free-tier scope decision above).
  - `True` -> full response, all 3 scenarios, full breakdown.
- No API-key metering (unlike gold/silver/etc. in `main.py`) — gating is by
  subscription, not by key tier. Auth is **optional** here, unlike `wallet.py`
  — the free tier must work for an anonymous visitor, so this endpoint uses
  `middleware.authenticate_user_optional` (the `reports.py` pattern), not the
  required-auth `authenticate_user` pattern the line above originally said.
  Corrected 2026-09-10 during Task 4's review, which caught this line
  contradicting the plan's own (correct) implementation.

## FE

`fe/pages/fuel-forecast.html`, Settings-adjacent but its own page (matches
neither the Docs nor the Settings template exactly — it's a product page, not
docs and not an account page — closer to a standalone product surface;
follow `13.9` mobile rules and the site's existing header/nav regardless).
Reuses the chart/layout code from the artifact prototype
(`https://claude.ai/code/artifact/4c4d1d04-43e4-484f-a097-4fd3ffe97029`)
almost as-is, swapping the demo toggle for real state:

- On load: `fetchWithAuth('/api/v1/fuel-forecast/RON95')` etc. — response shape
  already tells the page whether it's free or full (breakdown fields present
  or not), so no separate "am I subscribed" check needed to decide what to
  render.
- Lock overlay shows when the response is free-tier; CTA calls
  `POST /subscriptions/subscribe`, then re-fetches.
- New "Lịch sử thanh toán" card, visible once the user has ever subscribed
  (i.e. `GET /subscriptions/me` returns a row for this product, any status):
  renders `GET /subscriptions/history` rows with Vietnamese event labels
  (`created`->"Đăng ký mới", `charged`->"Gia hạn thành công",
  `charge_failed`->"Không đủ số dư — vào grace period",
  `cancelled`->"Huỷ", `reactivated`->"Kích hoạt lại").

## Testing

- `tests/subscription/test_subscription_service.py` (new, mirrors
  `tests/fuel/` structure): pure-logic tests for the billing-cycle state
  machine (renew success, renew-failure-to-past_due, past_due-retry-success,
  past_due-grace-expired-to-cancelled) using a fake clock, not a real DB.
- `subscribe`/`cancel` atomicity tests against a real test DB connection,
  mirroring the existing pattern for `purchase_product`/`refund_purchase` if
  such tests exist for those (check `tests/` for a `credit`/`wallet` test file
  before writing new fixtures from scratch).

## Explicitly out of scope (confirmed with user)

- Prorated refund on mid-cycle cancellation.
- Any change to the NĐ169 legal-review gate or the DESIGN.md "No-Pricing Rule"
  for Open Data — this is a separate, already-B2B-positioned product.
- A generalized "product catalog admin UI" — `platform_products` rows are
  inserted manually (one `INSERT` for `fuel-forecast-advanced`) until a second
  product actually exists to justify UI for managing the catalog.
