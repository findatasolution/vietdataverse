"""Admin analysis report — the tabs behind /pages/admin.html.

Separate module from `admin.py` on purpose. `admin.py` owns *operations*
(list users, patch a user, reverify an order) and is already ~690 lines; this
owns *analysis* — read-only aggregates that answer "is this business working".
Mixing them would put a 400-line reporting query block in the middle of the file
you open to fix a user's level.

Four endpoints, one per analysis tab. Each is lazily fetched by the page when
its tab is opened, so a tab nobody looks at costs nothing.

Design rules kept throughout:

  * **Never invent a number the data cannot support.** `api_call_log` has no
    duration column, so there is no latency figure anywhere here — an empty
    tile is honest, a fabricated one is not.
  * **Say when something is unmeasurable rather than returning 0.** Every block
    that can be structurally empty carries its own `note`, so the page can
    print "chưa ghi nhận từ <date>" instead of a zero that reads as "nobody
    came".
  * **Read-only.** Nothing here writes, so nothing here needs an audit entry.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import text

from core.engines import (get_engine_user, get_engine_knowledge, get_engine_crawl,
                          get_engine_global, get_engine_corp, get_engine_fuel)
from middleware import authenticate_user
from quota import QUOTA_BY_LEVEL, get_quota
from routers.admin import _REPORT_PERIODS, _require_admin

router = APIRouter()


def _json_response(data: dict) -> Response:
    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    return Response(content=raw, media_type="application/json",
                    headers={"Content-Length": str(len(raw))})


async def _admin_gate(request: Request):
    await authenticate_user(request)
    _require_admin(request)


def _since(period: str) -> str:
    """SQL expression for the start of the report window.

    `period` is validated by FastAPI's regex before it reaches here, and the
    value returned comes from the allowlisted `_REPORT_PERIODS` table — never
    from the request. That is what makes the f-string interpolation below safe;
    keep it that way.
    """
    if period not in _REPORT_PERIODS:
        raise HTTPException(status_code=400, detail="Khoảng thời gian không hợp lệ")
    return _REPORT_PERIODS[period]["since_sql"]


def _rows(conn, sql: str, **params):
    return [dict(r._mapping) for r in conn.execute(text(sql), params).fetchall()]


def _scalar(conn, sql: str, default=0, **params):
    value = conn.execute(text(sql), params).scalar()
    return default if value is None else value


# ===========================================================================
# Tab 1 — Tổng quan: the acquisition funnel
# ===========================================================================

@router.get("/api/v1/admin/report/funnel")
async def report_funnel(request: Request,
                        period: str = Query("7d", pattern="^(24h|7d|ytd)$")):
    """Where people fall out between landing on the site and paying.

    Deliberately NOT the same thing as the KPI strip. The strip answers "how
    many"; this answers "how many survived the previous step" — the only view
    that says where to spend effort. With five users total the absolute numbers
    are tiny, but the shape (12 orders created, 1 paid) is already the single
    most actionable fact the database holds.
    """
    await _admin_gate(request)
    since = _since(period)

    with get_engine_user().connect() as conn:
        signups = _scalar(conn, f"SELECT COUNT(*) FROM users WHERE created_at >= {since}")
        # "Ever" counts, not period counts, for the middle of the funnel: an
        # account created last month that made its first API call today is a
        # conversion, and a period-scoped count would drop it.
        total_users = _scalar(conn, "SELECT COUNT(*) FROM users")
        with_key = _scalar(conn, "SELECT COUNT(DISTINCT user_id) FROM api_keys")
        with_active_key = _scalar(
            conn, "SELECT COUNT(DISTINCT user_id) FROM api_keys WHERE is_active = TRUE")
        # Nested deliberately: a call made with an API KEY, not any call at all.
        # Counting every authenticated call put 4 callers under 1 key-holder and
        # printed "400%" — because an FE session authenticates with a Bearer
        # token and needs no key, so that population is not a subset of the
        # previous step. Browsing the site is not API adoption; it gets its own
        # line below instead of corrupting the funnel.
        called_with_key = _scalar(conn, """
            SELECT COUNT(DISTINCT user_id) FROM api_call_log
            WHERE user_id IS NOT NULL AND api_key_id IS NOT NULL
        """)
        called_via_session = _scalar(conn, """
            SELECT COUNT(DISTINCT user_id) FROM api_call_log
            WHERE user_id IS NOT NULL AND api_key_id IS NULL
        """)
        # Người từng gọi bằng key nhưng hiện không còn hàng nào trong api_keys —
        # key đã bị xoá/thu hồi. Nếu không nói ra, trang sẽ hiện "1 người có key"
        # ngay cạnh "2 người gọi bằng key" và người đọc không hiểu vì sao.
        orphan_key_callers = _scalar(conn, """
            SELECT COUNT(*) FROM (
                SELECT DISTINCT user_id FROM api_call_log
                WHERE user_id IS NOT NULL AND api_key_id IS NOT NULL
                EXCEPT
                SELECT DISTINCT user_id FROM api_keys
            ) t
        """)
        logged_in = _scalar(conn, "SELECT COUNT(*) FROM users WHERE login_count > 0")

        orders_created = _scalar(conn, f"SELECT COUNT(*) FROM payment_orders WHERE created_at >= {since}")
        orders_paid = _scalar(conn, f"SELECT COUNT(*) FROM payment_orders WHERE status='paid' AND created_at >= {since}")
        orders_created_all = _scalar(conn, "SELECT COUNT(*) FROM payment_orders")
        orders_paid_all = _scalar(conn, "SELECT COUNT(*) FROM payment_orders WHERE status='paid'")

        paying_users = _scalar(conn, """
            SELECT COUNT(DISTINCT user_id) FROM payment_orders WHERE status='paid'
        """)

    steps = [
        {"key": "signup", "label": "Đã đăng ký", "value": total_users,
         "note": f"{signups} tài khoản mới trong kỳ"},
        {"key": "logged_in", "label": "Đã đăng nhập ít nhất 1 lần", "value": logged_in},
        {"key": "has_key", "label": "Đã tạo API key", "value": with_key,
         "note": f"{with_active_key} key còn hoạt động"},
        {"key": "called", "label": "Đã gọi API bằng key", "value": called_with_key,
         "note": (f"{called_via_session} người khác chỉ gọi qua phiên đăng nhập trên web "
                  f"(không cần key)"
                  + (f"; {orphan_key_callers} người từng gọi bằng key nay đã bị xoá khỏi api_keys"
                     if orphan_key_callers else ""))},
        {"key": "paid", "label": "Đã thanh toán", "value": paying_users},
    ]
    # Drop-off is computed against the previous step, not against the top:
    # "9 of 10 people who made a key never called" is the sentence that tells
    # you what to fix.
    for i, step in enumerate(steps):
        prev = steps[i - 1]["value"] if i else None
        step["from_prev_pct"] = (round(100.0 * step["value"] / prev, 1)
                                 if prev else None)
        # A funnel percentage above 100 means the two steps are not nested, and
        # the number is meaningless rather than impressive. Guard it here so a
        # future step added in the wrong order shows a blank, not "400%".
        if step["from_prev_pct"] is not None and step["from_prev_pct"] > 100:
            step["from_prev_pct"] = None
            step["warning"] = ("Bậc này không phải tập con của bậc trước — "
                               "tỉ lệ không có nghĩa")

    return _json_response({
        "success": True,
        "period": period,
        "steps": steps,
        "orders": {
            "period": {"created": orders_created, "paid": orders_paid},
            "all_time": {"created": orders_created_all, "paid": orders_paid_all,
                         "paid_pct": (round(100.0 * orders_paid_all / orders_created_all, 1)
                                      if orders_created_all else None)},
        },
    })


# ===========================================================================
# Tab 2 — API
# ===========================================================================

@router.get("/api/v1/admin/report/api")
async def report_api(request: Request,
                     period: str = Query("7d", pattern="^(24h|7d|ytd)$")):
    """Who calls the API, what they call, and who gets turned away.

    The `anonymous` block is the reason this tab exists. Anonymous rejected
    calls were never recorded before 2026-09-23 (api_call_log.user_id was
    NOT NULL — see migration 019), so `first_anonymous_row` is returned
    alongside: a zero here means "not measured yet", and the page must say so
    rather than draw an empty bar.
    """
    await _admin_gate(request)
    since = _since(period)

    with get_engine_user().connect() as conn:
        by_day = _rows(conn, f"""
            SELECT DATE(at) AS day,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status_code < 400) AS ok,
                   COUNT(*) FILTER (WHERE status_code >= 400) AS rejected,
                   COUNT(*) FILTER (WHERE user_id IS NULL) AS anonymous
            FROM api_call_log WHERE at >= {since}
            GROUP BY 1 ORDER BY 1
        """)
        by_endpoint = _rows(conn, f"""
            SELECT endpoint,
                   COUNT(*) AS calls,
                   COUNT(*) FILTER (WHERE status_code < 400) AS ok,
                   COUNT(*) FILTER (WHERE status_code >= 400) AS rejected,
                   COUNT(DISTINCT user_id) AS users
            FROM api_call_log WHERE at >= {since}
            GROUP BY 1 ORDER BY calls DESC LIMIT 25
        """)
        by_status = _rows(conn, f"""
            SELECT status_code, COUNT(*) AS calls
            FROM api_call_log WHERE at >= {since}
            GROUP BY 1 ORDER BY calls DESC
        """)
        # Per-caller usage against their own limit. quota lives in Python, not
        # in SQL, so the join is done here rather than hardcoding tier numbers
        # into a query that would then drift from be/quota.py.
        callers = _rows(conn, f"""
            SELECT u.user_id, u.email, u.user_level, u.current_plan,
                   COUNT(*) AS calls,
                   COUNT(*) FILTER (WHERE acl.status_code >= 400) AS rejected,
                   COUNT(*) FILTER (WHERE acl.api_key_id IS NOT NULL) AS via_key,
                   MAX(acl.at) AS last_call
            FROM api_call_log acl JOIN users u ON u.user_id = acl.user_id
            WHERE acl.at >= {since}
            GROUP BY u.user_id, u.email, u.user_level, u.current_plan
            ORDER BY calls DESC LIMIT 50
        """)
        usage = {r["user_id"]: r["request_count"] for r in _rows(conn, """
            SELECT user_id, request_count FROM api_usage_monthly
            WHERE quota_month = TO_CHAR(NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh', 'YYYY-MM')
        """)}
        anonymous = _rows(conn, f"""
            SELECT endpoint, status_code, COUNT(*) AS calls
            FROM api_call_log
            WHERE at >= {since} AND user_id IS NULL
            GROUP BY 1, 2 ORDER BY calls DESC LIMIT 25
        """)
        first_anon = conn.execute(text(
            "SELECT MIN(at) FROM api_call_log WHERE user_id IS NULL")).scalar()
        total_rows = _scalar(conn, "SELECT COUNT(*) FROM api_call_log")

    for c in callers:
        q = get_quota(c["user_level"], c["current_plan"]) or {}
        limit = q.get("monthly")
        used = usage.get(c["user_id"], 0)
        c["quota_limit"] = limit
        c["quota_used"] = used
        c["quota_pct"] = round(100.0 * used / limit, 1) if limit else None

    return _json_response({
        "success": True,
        "period": period,
        "by_day": by_day,
        "by_endpoint": by_endpoint,
        "by_status": by_status,
        "callers": callers,
        "anonymous": {
            "rows": anonymous,
            "recording_since": first_anon,
            "note": ("Lượt gọi ẩn danh chỉ được ghi từ 2026-09-23 (migration 019). "
                     "Số 0 trước mốc đó nghĩa là KHÔNG ĐO, không phải không có ai gọi."),
        },
        "quota_reference": QUOTA_BY_LEVEL,
        "log_rows_total": total_rows,
    })


# ===========================================================================
# Tab 3 — Tiền
# ===========================================================================

@router.get("/api/v1/admin/report/money")
async def report_money(request: Request,
                       period: str = Query("ytd", pattern="^(24h|7d|ytd)$")):
    """Orders, marketplace and subscriptions — every place money can arrive.

    Reads two databases. The marketplace half lives in KNOWLEDGE_MARKET_DB, and
    that matters: USER_DB carries same-named, permanently empty copies of
    `knowledge_products` / `knowledge_purchases` / `seller_profiles`. Querying
    the wrong one returns 0 with no error, which is exactly how a report ends
    up quietly lying. Verified 2026-09-23: USER_DB copies hold 0 rows,
    KNOWLEDGE_MARKET_DB holds the real ones.
    """
    await _admin_gate(request)
    since = _since(period)

    with get_engine_user().connect() as conn:
        by_status = _rows(conn, f"""
            SELECT status, COUNT(*) AS orders, COALESCE(SUM(amount), 0) AS amount
            FROM payment_orders WHERE created_at >= {since}
            GROUP BY 1 ORDER BY orders DESC
        """)
        by_plan = _rows(conn, f"""
            SELECT plan, status, COUNT(*) AS orders, COALESCE(SUM(amount), 0) AS amount
            FROM payment_orders WHERE created_at >= {since}
            GROUP BY 1, 2 ORDER BY orders DESC
        """)
        recent = _rows(conn, f"""
            SELECT order_code, plan, status, amount, created_at, updated_at
            FROM payment_orders WHERE created_at >= {since}
            ORDER BY created_at DESC LIMIT 25
        """)
        revenue_by_month = _rows(conn, """
            SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM') AS month,
                   COALESCE(SUM(amount), 0) AS amount, COUNT(*) AS orders
            FROM payment_orders WHERE status = 'paid'
            GROUP BY 1 ORDER BY 1
        """)

    marketplace = {"available": False, "note": "KNOWLEDGE_MARKET_DB chưa cấu hình"}
    try:
        with get_engine_knowledge().connect() as conn:
            marketplace = {
                "available": True,
                "products": _scalar(conn, "SELECT COUNT(*) FROM knowledge_products"),
                "sellers": _scalar(conn, "SELECT COUNT(*) FROM seller_profiles"),
                "purchases": _rows(conn, """
                    SELECT COUNT(*) AS purchases,
                           COALESCE(SUM(price_credits), 0) AS credits
                    FROM knowledge_purchases
                """),
                "credit_ledger": _rows(conn, """
                    SELECT kind, COUNT(*) AS entries, COALESCE(SUM(credits), 0) AS credits
                    FROM credit_ledger GROUP BY 1 ORDER BY entries DESC
                """),
                "seller_earnings": _scalar(conn, "SELECT COALESCE(SUM(credits), 0) FROM seller_earnings"),
                "subscriptions": _rows(conn, """
                    SELECT p.product_code, s.status, COUNT(*) AS subs
                    FROM platform_subscriptions s
                    JOIN platform_products p ON p.product_code = s.product_code
                    GROUP BY 1, 2 ORDER BY subs DESC
                """),
                "subscription_events": _rows(conn, """
                    SELECT event, COUNT(*) AS events, MAX(created_at) AS last_at
                    FROM platform_subscription_events GROUP BY 1 ORDER BY events DESC
                """),
                "note": ("Bảng trùng tên trong USER_DB (knowledge_products / "
                         "knowledge_purchases / seller_profiles) rỗng và không dùng — "
                         "dữ liệu thật chỉ nằm ở KNOWLEDGE_MARKET_DB."),
            }
    except Exception as exc:  # pragma: no cover — degraded, never fatal
        marketplace = {"available": False, "note": f"Không đọc được KNOWLEDGE_MARKET_DB: {exc}"}

    return _json_response({
        "success": True,
        "period": period,
        "orders": {"by_status": by_status, "by_plan": by_plan, "recent": recent},
        "revenue_by_month": revenue_by_month,
        "marketplace": marketplace,
    })


# ===========================================================================
# Tab 4 — Data Health
# ===========================================================================

# (engine, table, freshness expression, label, group, max age in days)
#
# `max_age_days` is the point past which the table is STALE — chosen from each
# source's real cadence, not a round number. Where this repo already fixed a
# staleness threshold in a crawler, the same number is used here so the two
# cannot disagree: fuel cycle 17 (CYCLE_STALE_DAYS), fuel world 6
# (WORLD_STALE_DAYS).
#
# The freshness expression is per-table because the time column is not uniform:
# vn_macro_* use `date`, vn_gso_*_monthly use a VARCHAR(7) 'YYYY-MM' `period`,
# fuel gold tables use `run_ts`, and vn_gso_gdp_quarterly has no period column
# at all so it falls back to `crawl_time`. Introspected 2026-09-23 — do not
# assume a column name here, check it.
DATA_HEALTH_TABLES = [
    ("crawl", "vn_macro_gold_daily",      "MAX(date)", "Vàng SJC", "Hàng ngày", 3),
    ("crawl", "vn_macro_silver_daily",    "MAX(date)", "Bạc Phú Quý", "Hàng ngày", 4),
    ("crawl", "vn_macro_sbv_rate_daily",  "MAX(date)", "Tỷ giá & lãi suất SBV", "Hàng ngày", 5),
    ("crawl", "vn_macro_termdepo_daily",  "MAX(date)", "Lãi suất tiền gửi ACB", "Hàng ngày", 5),
    ("crawl", "vn_macro_fxrate_daily",    "MAX(date)", "Tỷ giá VCB", "Hàng ngày", 5),
    # Ngưỡng của nhóm tháng tính trên NGÀY ĐẦU KỲ, không phải ngày công bố: kỳ
    # 2026-08 nghĩa là số liệu tháng 8, NSO công bố đầu tháng 9. Nên ngày
    # 23/9 kỳ mới nhất đã "già" 53 ngày một cách hoàn toàn bình thường. Ngưỡng
    # 45 ngày đặt lúc đầu khiến CPI và IIP báo late ngay ngày đầu — đúng kiểu
    # báo động giả đã làm con DQ agent cũ bị bỏ qua (xem CLAUDE.md). 70 ngày là
    # mốc mà kỳ của tháng trước lẽ ra đã phải về: quá đó mới thực sự có vấn đề.
    ("crawl", "vn_gso_cpi_monthly",       "MAX(TO_DATE(period || '-01', 'YYYY-MM-DD'))", "CPI", "Hàng tháng", 70),
    ("crawl", "vn_gso_iip_monthly",       "MAX(TO_DATE(period || '-01', 'YYYY-MM-DD'))", "IIP", "Hàng tháng", 70),
    ("crawl", "vn_gso_trade_monthly",     "MAX(TO_DATE(period || '-01', 'YYYY-MM-DD'))", "Xuất nhập khẩu", "Hàng tháng", 75),
    # GDP không có cột period — chỉ có crawl_time, nên ô "mới nhất" ở đây là
    # LẦN CRAWL gần nhất chứ không phải quý gần nhất. Nhãn nói rõ để không bị
    # đọc nhầm thành "dữ liệu quý mới về hôm đó".
    ("crawl", "vn_gso_gdp_quarterly",     "MAX(crawl_time)::date", "GDP (theo lần crawl)", "Hàng quý", 120),
    ("global", "global_macro",            "MAX(date)", "Vàng/bạc/NASDAQ thế giới", "Hàng ngày", 5),
    ("global", "global_lbma_gold_forecast", "MAX(crawl_time)::date", "Khảo sát LBMA", "2 lần/năm", 220),
    ("fuel",  "fuel_price_cycle",         "MAX(period)", "Kỳ điều hành giá xăng dầu", "~2 tuần", 17),
    ("fuel",  "fuel_world_daily",         "MAX(period)", "Brent/RBOB", "Hàng ngày", 6),
    ("fuel",  "fuel_forecast",            "MAX(run_ts)::date", "Dự báo xăng dầu", "Theo kỳ", 20),
    ("fuel",  "fuel_backtest",            "MAX(run_ts)::date", "Backtest xăng dầu", "Theo kỳ", 20),
    ("corp",  "vn30_ohlcv_daily",         "MAX(date)", "Giá VN30 (nội bộ)", "Hàng ngày", 5),
    ("corp",  "vn30_ratio_daily",         "MAX(date)", "Chỉ số VN30 (nội bộ)", "Hàng ngày", 5),
]

_ENGINES = {
    "crawl": get_engine_crawl,
    "global": get_engine_global,
    "corp": get_engine_corp,
    "fuel": get_engine_fuel,
}


@router.get("/api/v1/admin/report/data-health")
async def report_data_health(request: Request):
    """Freshness of every crawl table, across all four data databases.

    This is the only place in the product that answers "is the data still
    arriving". The DQ agent's findings go to an HTML email whose mailbox has
    rejected the credentials since 2026-09-09, and everything else is buried in
    GitHub Actions logs. A crawler that silently stops is this project's
    recurring failure — it happened to gold (75 days), to the MOIT fuel
    bulletin (2 months), and to SBV rates — every time discovered by accident.
    """
    await _admin_gate(request)

    groups: dict[str, list] = {}
    for engine_key, table, fresh_expr, label, cadence, max_age in DATA_HEALTH_TABLES:
        entry = {"table": table, "label": label, "db": engine_key,
                 "cadence": cadence, "max_age_days": max_age}
        try:
            with _ENGINES[engine_key]().connect() as conn:
                row = conn.execute(text(f"""
                    SELECT {fresh_expr} AS latest, COUNT(*) AS rows FROM {table}
                """)).first()
            latest, rows = (row[0], row[1]) if row else (None, 0)
            entry["rows"] = rows
            entry["latest"] = latest
            if latest is None:
                entry.update(status="empty", age_days=None)
            else:
                from datetime import date, datetime as _dt
                latest_date = latest.date() if isinstance(latest, _dt) else latest
                age = (date.today() - latest_date).days
                entry["age_days"] = age
                # Two bands, not three: "đang trễ" is the warning you can still
                # ignore for a day, "đứng im" is the one that means a crawler
                # died. A third middle band just makes every row amber.
                entry["status"] = ("ok" if age <= max_age
                                   else "late" if age <= max_age * 2
                                   else "stale")
        except Exception as exc:
            entry.update(status="error", error=str(exc)[:200], rows=None,
                         latest=None, age_days=None)
        groups.setdefault(cadence, []).append(entry)

    flat = [e for items in groups.values() for e in items]
    return _json_response({
        "success": True,
        "groups": groups,
        "summary": {
            "total": len(flat),
            "ok": sum(1 for e in flat if e["status"] == "ok"),
            "late": sum(1 for e in flat if e["status"] == "late"),
            "stale": sum(1 for e in flat if e["status"] == "stale"),
            "error": sum(1 for e in flat if e["status"] == "error"),
            "empty": sum(1 for e in flat if e["status"] == "empty"),
        },
    })
