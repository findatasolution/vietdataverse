"""DA report — data quality + web performance + funnels, as one markdown page.

Run:  python be/da_report.py [--out report.md]   (every table: last 7 days + all time)

Used by the `da` agent (.claude/agents/da.md). Read-only: it never writes to
any database and never sends mail (the DQ email channel has been dead since
2026-09-09 — a report nobody receives is how outages went unnoticed).

Three sections:
1. Data quality — freshness of every crawl table (same thresholds as the admin
   Data Health tab, imported, so the two cannot disagree) + the network-free
   SJC structural audit.
2. Web performance — GA4 traffic, channels, engagement.
3. Funnels — site funnel from GA4 events, and the **auto-report funnel**
   (Google Sheets template → API key → refresh-data calls → quota hit → paid),
   which is what VDV actually sells.

Counts exclude internal accounts (INTERNAL_EMAILS) and test fixtures (negative
user ids in KNOWLEDGE_MARKET_DB) — on 2026-10-04 those were the *only*
"subscribers", and counting them reads as revenue that does not exist.
"""

import argparse
import os
import sys
from datetime import date, datetime

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))
sys.path.insert(0, os.path.join(ROOT, "be"))
sys.path.insert(0, os.path.join(ROOT, "crawl_tools"))

from sqlalchemy import text  # noqa: E402

from core.engines import get_engine_crawl, get_engine_user  # noqa: E402

INTERNAL_EMAILS = ("npdhien2806@gmail.com", "findatasolution@gmail.com")
SHEETS_ENDPOINT = "/api/v1/excel/refresh-data"  # path baked into customers' Sheets copies

out: list[str] = []
w = out.append


def pct(a, b):
    return "—" if not b else f"{a / b * 100:.0f}%"


# ── 1. Data quality ──────────────────────────────────────────────────────────
def section_data_quality():
    from routers.admin_report import DATA_HEALTH_TABLES, _ENGINES
    w("## 1. Chất lượng dữ liệu\n")
    w("| Bộ dữ liệu | Bảng | Mới nhất | Tuổi (ngày) | Ngưỡng | Trạng thái |")
    w("|---|---|---|---|---|---|")
    bad = []
    for key, table, expr, label, _cad, max_age in DATA_HEALTH_TABLES:
        try:
            with _ENGINES[key]().connect() as c:
                latest = c.execute(text(f"SELECT {expr} FROM {table}")).scalar()
            if latest is None:
                status, age = "EMPTY", None
            else:
                d = latest.date() if isinstance(latest, datetime) else latest
                age = (date.today() - d).days
                status = ("ok" if age <= max_age else
                          "LATE" if age <= max_age * 2 else "STALE")
        except Exception as exc:  # report, don't crash the whole report
            latest, age, status = None, None, f"ERROR {str(exc)[:60]}"
        if status != "ok":
            bad.append(label)
        w(f"| {label} | `{table}` | {latest} | {age if age is not None else '—'} | {max_age} | {status} |")
    w("")
    w(f"**Bất thường:** {', '.join(bad) if bad else 'không có'}\n")

    try:
        from reconcile_sjc import structural_audit
        issues = structural_audit(get_engine_crawl(), log=lambda *a, **k: None)
        w(f"**Audit cấu trúc vàng SJC:** {len(issues)} vấn đề")
        for i in issues[:10]:
            w(f"- {i}")
        w("")
    except Exception as exc:
        w(f"**Audit cấu trúc vàng SJC:** không chạy được ({str(exc)[:80]})\n")


# ── periods ──────────────────────────────────────────────────────────────────
# Every table shows both: the last week (what changed) and all time (where we
# stand). `None` days = all time.
PERIODS = [("Tuần (7 ngày)", 7), ("Toàn thời gian", None)]
GA_EPOCH = "2020-01-01"  # before the GA4 property existed — means "all"


def _since(days):
    return f"{days} days" if days else "100 years"


def funnel_table(steps, base="prev"):
    """steps: [(label, [value per period])] → markdown table.

    base="prev": % of the step above (a strict funnel, each step a subset).
    base="top":  % of the first step — for the traffic funnel, whose steps are
    not nested (a visitor can log in without opening a chart), so a
    step-to-step ratio would print >100%."""
    head = " | ".join(f"{lbl} | %" for lbl, _ in PERIODS)
    w(f"| Bước | {head} |")
    w("|---|" + "---|---|" * len(PERIODS))
    prev = [None] * len(PERIODS)
    for label, vals in steps:
        cells = []
        for i, v in enumerate(vals):
            shown = "—" if v is None else f"{v:,.0f}"
            ref = prev[i] if base == "prev" else steps[0][1][i]
            first = label == steps[0][0]
            cells.append(f"{shown} | {pct(v, ref) if ref and v is not None and not first else '—'}")
            if v is not None:
                prev[i] = v
        w(f"| {label} | {' | '.join(cells)} |")
    w("")


# ── 2. Web performance (GA4) ─────────────────────────────────────────────────
def _ga():
    from core import ga4
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Metric,
                                                    RunReportRequest)
    if not ga4.is_configured():
        raise RuntimeError("GA4 env vars chưa đặt")
    client, prop = ga4._client(), f"properties/{ga4.GA4_PROPERTY_ID}"

    def run(dims, mets, days, limit=500):
        start = f"{days}daysAgo" if days else GA_EPOCH
        r = client.run_report(RunReportRequest(
            property=prop, dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
            date_ranges=[DateRange(start_date=start, end_date="today")],
            limit=limit))
        return [([v.value for v in row.dimension_values],
                 [float(v.value) for v in row.metric_values]) for row in r.rows]
    return run


def section_web(run):
    w("## 2. Hiệu quả web (GA4)\n")
    w("| Chỉ số | " + " | ".join(l for l, _ in PERIODS) + " |")
    w("|---|" + "---|" * len(PERIODS))
    tots = []
    for _, d in PERIODS:
        t = run([], ["activeUsers", "newUsers", "sessions", "screenPageViews",
                     "engagementRate", "averageSessionDuration"], d)
        tots.append(t[0][1] if t else [0] * 6)
    for i, name in enumerate(["Người dùng", "Người dùng mới", "Session", "Pageview"]):
        w(f"| {name} | " + " | ".join(f"{t[i]:,.0f}" for t in tots) + " |")
    w("| Tỉ lệ tương tác | " + " | ".join(f"{t[4] * 100:.0f}%" for t in tots) + " |")
    w("| Thời gian TB/session (s) | " + " | ".join(f"{t[5]:.0f}" for t in tots) + " |")
    w("")

    w("**Nguồn traffic (người dùng · tỉ lệ tương tác):**\n")
    w("| Kênh | " + " | ".join(l for l, _ in PERIODS) + " |")
    w("|---|" + "---|" * len(PERIODS))
    per = [{ch: (u, er) for (ch,), (u, er) in
            run(["sessionDefaultChannelGroup"], ["activeUsers", "engagementRate"], d)}
           for _, d in PERIODS]
    for ch in sorted(per[-1], key=lambda c: -per[-1][c][0]):
        w(f"| {ch} | " + " | ".join(
            f"{p[ch][0]:.0f} · {p[ch][1] * 100:.0f}%" if ch in p else "—" for p in per) + " |")
    w("")

    w("**Trang xem nhiều nhất (tuần):**")
    for (pg,), (v,) in sorted(run(["pagePath"], ["screenPageViews"], 7),
                              key=lambda r: -r[1][0])[:10]:
        w(f"- `{pg}` — {v:.0f}")
    w("")


# ── 3. Funnels ───────────────────────────────────────────────────────────────
def _ga_users(run, d):
    """Distinct users per event and per page path — funnels count people, not
    events (one visitor opening 5 charts is one person, not 5)."""
    ev = {n: u for (n,), (u,) in run(["eventName"], ["totalUsers"], d)}
    pages = {p: u for (p,), (u,) in run(["pagePath"], ["totalUsers"], d)}
    total = run([], ["activeUsers"], d)
    return ev, pages, (total[0][1][0] if total else 0)


def _db_counts(d):
    with get_engine_user().connect() as c:
        internal = [r[0] for r in c.execute(
            text("SELECT user_id FROM users WHERE email = ANY(:e)"),
            {"e": list(INTERNAL_EMAILS)})]
        p = {"since": _since(d), "int": internal or [-1], "ep": SHEETS_ENDPOINT}
        q = lambda sql: c.execute(text(sql), p).scalar() or 0  # noqa: E731
        win = "NOW() - CAST(:since AS interval)"
        return dict(
            signups=q(f"SELECT COUNT(*) FROM users WHERE created_at > {win} AND user_id <> ALL(:int)"),
            keyed=q(f"SELECT COUNT(DISTINCT user_id) FROM api_keys WHERE created_at > {win} "
                    "AND user_id <> ALL(:int)"),
            used=q(f"SELECT COUNT(DISTINCT user_id) FROM api_call_log WHERE endpoint = :ep AND "
                   f"status_code = 200 AND at > {win} AND user_id <> ALL(:int)"),
            repeat=q("SELECT COUNT(*) FROM (SELECT user_id, COUNT(DISTINCT at::date) d FROM "
                     f"api_call_log WHERE endpoint = :ep AND status_code = 200 AND at > {win} "
                     "AND user_id <> ALL(:int) GROUP BY user_id) x WHERE d >= 3"),
            capped=q(f"SELECT COUNT(DISTINCT user_id) FROM api_call_log WHERE status_code = 429 "
                     f"AND at > {win} AND user_id <> ALL(:int)"),
            anon=q(f"SELECT COUNT(*) FROM api_call_log WHERE endpoint = :ep AND status_code = 401 "
                   f"AND at > {win}"),
            paid=q(f"SELECT COUNT(DISTINCT user_id) FROM payment_orders WHERE status = 'paid' AND "
                   f"created_at > {win} AND user_id <> ALL(:int)"),
            paid_vnd=q(f"SELECT COALESCE(SUM(amount),0) FROM payment_orders WHERE status = 'paid' "
                       f"AND created_at > {win} AND user_id <> ALL(:int)"),
        )


def section_funnels(run):
    w("## 3. Phễu\n")
    db = [_db_counts(d) for _, d in PERIODS]
    ga = [_ga_users(run, d) for _, d in PERIODS] if run else None

    def pages_users(g, needle):
        return sum(u for p, u in g[1].items() if needle in p)

    if ga:
        w("### 3a. Phễu traffic (số người, GA4 + DB)\n")
        funnel_table([
            ("Người truy cập", [g[2] for g in ga]),
            ("Có tương tác (ở lại, cuộn, click)", [g[0].get("user_engagement", 0) for g in ga]),
            ("Mở chi tiết một bộ dữ liệu", [g[0].get("dataset_detail_view", 0) for g in ga]),
            ("Tải dữ liệu thành công", [g[0].get("dataset_download_success", 0) for g in ga]),
            ("Đăng nhập", [g[0].get("login", 0) for g in ga]),
            ("Xem trang giá", [pages_users(g, "pricing") for g in ga]),
            ("Bấm thanh toán", [g[0].get("begin_checkout", 0) for g in ga]),
            ("Trả tiền (PayOS paid, khách thật)", [x["paid"] for x in db]),
        ], base="top")
        w("_% ở phễu traffic = so với số người truy cập. GA4 không loại được lượt "
          "truy cập của chính chủ — chỉ bước trả tiền (DB) là đã loại nội bộ._\n")

    w("### 3b. Phễu báo cáo tự động — Google Sheets (đã loại nội bộ & test)\n")
    funnel_table([
        ("Xem trang hướng dẫn Google Sheets",
         [pages_users(g, "google-sheets") for g in ga] if ga else [None] * len(PERIODS)),
        ("Bấm tạo bản sao template",
         [g[0].get("sheets_template_copy", 0) for g in ga] if ga else [None] * len(PERIODS)),
        ("Đăng ký tài khoản", [x["signups"] for x in db]),
        ("Tạo API key", [x["keyed"] for x in db]),
        ("File Sheets gọi dữ liệu thành công", [x["used"] for x in db]),
        ("Dùng đều (≥3 ngày khác nhau)", [x["repeat"] for x in db]),
        ("Chạm hết quota (429)", [x["capped"] for x in db]),
        ("Trả tiền", [x["paid"] for x in db]),
    ])
    w("Doanh thu thật: " + " · ".join(f"{l} **{x['paid_vnd']:,.0f}đ**"
                                      for (l, _), x in zip(PERIODS, db))
      + f" · lượt gọi Sheets bị 401 (toàn thời gian): {db[-1]['anon']}\n")
    w("_Ghi chú: trang độc lập (google-sheets, developer, pricing…) chỉ có GA từ "
      "2026-10-05, sự kiện `sheets_template_copy` cũng từ ngày đó — số toàn thời "
      "gian của các bước này đếm thiếu. % là so với bước liền trên._\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    args = ap.parse_args()

    w(f"# Báo cáo DA — {date.today():%d/%m/%Y} (tuần + toàn thời gian)\n")
    section_data_quality()
    try:
        run = _ga()
        section_web(run)
    except Exception as exc:
        run = None
        w(f"## 2. Hiệu quả web\n\n**GA4 không đọc được:** {str(exc)[:160]}\n"
          "(refresh token hết hạn → chạy lại luồng consent, xem CLAUDE.md mục GA4)\n")
    section_funnels(run)

    report = "\n".join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)


if __name__ == "__main__":
    main()
