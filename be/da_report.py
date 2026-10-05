"""DA report — data quality + web performance + funnels, as one markdown page.

Run:  python be/da_report.py [--days 30] [--out report.md]

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


# ── 2. Web performance (GA4) ─────────────────────────────────────────────────
def _ga():
    from core import ga4
    from google.analytics.data_v1beta.types import (DateRange, Dimension, Metric,
                                                    RunReportRequest)
    if not ga4.is_configured():
        raise RuntimeError("GA4 env vars chưa đặt")
    client, prop = ga4._client(), f"properties/{ga4.GA4_PROPERTY_ID}"

    def run(dims, mets, days, limit=50):
        r = client.run_report(RunReportRequest(
            property=prop, dimensions=[Dimension(name=d) for d in dims],
            metrics=[Metric(name=m) for m in mets],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            limit=limit))
        return [([v.value for v in row.dimension_values],
                 [float(v.value) for v in row.metric_values]) for row in r.rows]
    return run


def section_web(days, run):
    w(f"## 2. Hiệu quả web ({days} ngày, GA4)\n")
    t = run([], ["activeUsers", "newUsers", "sessions", "screenPageViews",
                 "engagementRate"], days)
    if t:
        u, n, s, pv, er = t[0][1]
        w(f"Người dùng **{u:.0f}** (mới {n:.0f}) · session **{s:.0f}** · pageview "
          f"**{pv:.0f}** · tỉ lệ tương tác **{er * 100:.0f}%**\n")
    w("| Kênh | Session | Tương tác | Thời gian TB (s) |")
    w("|---|---|---|---|")
    rows = run(["sessionDefaultChannelGroup"],
               ["sessions", "engagementRate", "averageSessionDuration"], days)
    for (ch,), (s, er, dur) in sorted(rows, key=lambda r: -r[1][0]):
        w(f"| {ch} | {s:.0f} | {er * 100:.0f}% | {dur:.0f} |")
    w("")
    w("**Trang xem nhiều nhất:**")
    pages = run(["pagePath"], ["screenPageViews"], days)
    for (p,), (v,) in sorted(pages, key=lambda r: -r[1][0])[:10]:
        w(f"- `{p}` — {v:.0f}")
    w("")


# ── 3. Funnels ───────────────────────────────────────────────────────────────
def section_funnels(days, run):
    w(f"## 3. Phễu ({days} ngày)\n")

    if run:
        ev = {name: cnt for (name,), (cnt,) in run(["eventName"], ["eventCount"], days, 200)}
        pv = {p: v for (p,), (v,) in run(["pagePath"], ["screenPageViews"], days, 500)}
        pricing = sum(v for p, v in pv.items() if "pricing" in p)
        steps = [("Lượt vào lần đầu (first_visit)", ev.get("first_visit", 0)),
                 ("Mở chi tiết bộ dữ liệu", ev.get("dataset_detail_view", 0)),
                 ("Tải dữ liệu thành công", ev.get("dataset_download_success", 0)),
                 ("Xem trang giá", pricing),
                 ("Bấm thanh toán (begin_checkout)", ev.get("begin_checkout", 0)),
                 ("Chuyển sang PayOS", ev.get("checkout_redirect", 0))]
        w("### 3a. Phễu website (GA4 — đếm sự kiện, không phải người)\n")
        w("| Bước | Số | So với bước trước |")
        w("|---|---|---|")
        prev = None
        for name, n in steps:
            w(f"| {name} | {n:.0f} | {pct(n, prev) if prev is not None else '—'} |")
            prev = n
        w("")
        sheets_pv = sum(v for p, v in pv.items() if "google-sheets" in p)
        copies = ev.get("sheets_template_copy", 0)
    else:
        sheets_pv = copies = None

    w("### 3b. Phễu báo cáo tự động — Google Sheets (người dùng thật, đã loại nội bộ & test)\n")
    with get_engine_user().connect() as c:
        internal = [r[0] for r in c.execute(
            text("SELECT user_id FROM users WHERE email = ANY(:e)"),
            {"e": list(INTERNAL_EMAILS)})]
        p = {"since": f"{days} days", "int": internal or [-1], "ep": SHEETS_ENDPOINT}
        q = lambda sql: c.execute(text(sql), p).scalar() or 0  # noqa: E731
        signups = q("SELECT COUNT(*) FROM users WHERE created_at > NOW() - CAST(:since AS interval) "
                    "AND user_id <> ALL(:int)")
        keyed = q("SELECT COUNT(DISTINCT user_id) FROM api_keys WHERE created_at > NOW() - "
                  "CAST(:since AS interval) AND user_id <> ALL(:int)")
        used = q("SELECT COUNT(DISTINCT user_id) FROM api_call_log WHERE endpoint = :ep AND "
                 "status_code = 200 AND at > NOW() - CAST(:since AS interval) AND user_id <> ALL(:int)")
        repeat = q("SELECT COUNT(*) FROM (SELECT user_id, COUNT(DISTINCT at::date) d FROM api_call_log "
                   "WHERE endpoint = :ep AND status_code = 200 AND at > NOW() - CAST(:since AS interval) "
                   "AND user_id <> ALL(:int) GROUP BY user_id) x WHERE d >= 3")
        capped = q("SELECT COUNT(DISTINCT user_id) FROM api_call_log WHERE status_code = 429 AND "
                   "at > NOW() - CAST(:since AS interval) AND user_id <> ALL(:int)")
        anon = q("SELECT COUNT(*) FROM api_call_log WHERE endpoint = :ep AND status_code = 401 "
                 "AND at > NOW() - CAST(:since AS interval)")
        paid = q("SELECT COUNT(DISTINCT user_id) FROM payment_orders WHERE status = 'paid' AND "
                 "created_at > NOW() - CAST(:since AS interval) AND user_id <> ALL(:int)")
        paid_vnd = q("SELECT COALESCE(SUM(amount),0) FROM payment_orders WHERE status = 'paid' AND "
                     "created_at > NOW() - CAST(:since AS interval) AND user_id <> ALL(:int)")
    steps = [("Xem trang hướng dẫn Google Sheets (pageview GA4)", sheets_pv),
             ("Bấm tạo bản sao template (GA4)", copies),
             ("Đăng ký tài khoản", signups),
             ("Tạo API key", keyed),
             ("File Sheets gọi dữ liệu thành công (≥1 lần)", used),
             ("Dùng đều (≥3 ngày khác nhau)", repeat),
             ("Chạm hết quota (429)", capped),
             ("Trả tiền (PayOS paid)", paid)]
    w("| Bước | Số | So với bước trước |")
    w("|---|---|---|")
    prev = None
    for name, n in steps:
        shown = "—" if n is None else f"{n:.0f}"
        w(f"| {name} | {shown} | {pct(n, prev) if prev and n is not None else '—'} |")
        prev = n if n is not None else prev
    w("")
    w(f"Doanh thu thật kỳ này: **{paid_vnd:,.0f}đ** · lượt gọi Sheets bị 401 (key sai/thiếu): {anon}\n")
    w("_Ghi chú: trang độc lập (google-sheets, developer, pricing…) chỉ được gắn GA "
      "từ 2026-10-05, và sự kiện `sheets_template_copy` cũng bắt đầu từ ngày đó — "
      "kỳ báo cáo chứa ngày trước đó sẽ đếm thiếu hai bước đầu._\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out")
    args = ap.parse_args()

    w(f"# Báo cáo DA — {date.today():%d/%m/%Y} ({args.days} ngày gần nhất)\n")
    section_data_quality()
    try:
        run = _ga()
        section_web(args.days, run)
    except Exception as exc:
        run = None
        w(f"## 2. Hiệu quả web\n\n**GA4 không đọc được:** {str(exc)[:160]}\n"
          "(refresh token hết hạn → chạy lại luồng consent, xem CLAUDE.md mục GA4)\n")
    section_funnels(args.days, run)

    report = "\n".join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)
    print(report)


if __name__ == "__main__":
    main()
