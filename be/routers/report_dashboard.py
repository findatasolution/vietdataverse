"""Internal report — logins / users / API usage / experience feedback.
Viewable on prod at /api/v1/report?key=<secret> (REPORT_SECRET, or WEBHOOK_INTERNAL_SECRET as fallback).
Pageview/visit counts live in Google Analytics — not stored server-side."""
import os
import html as _html

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from core.engines import get_engine_user

router = APIRouter()


def _authorized(key: str) -> bool:
    expected = os.getenv("REPORT_SECRET") or os.getenv("WEBHOOK_INTERNAL_SECRET")
    return bool(expected) and key == expected


def _scalar(conn, sql, default=0):
    try:
        v = conn.execute(text(sql)).scalar()
        return v if v is not None else default
    except Exception:
        return default


def _rows(conn, sql):
    try:
        return conn.execute(text(sql)).fetchall()
    except Exception:
        return []


def _esc(v):
    return _html.escape(str(v)) if v is not None else "—"


def _card(label, value, sub=""):
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f'<div class="card"><div class="lbl">{label}</div><div class="val">{value}</div>{sub_html}</div>'


@router.get("/api/v1/report", response_class=HTMLResponse)
async def report(key: str = ""):
    if not _authorized(key):
        raise HTTPException(status_code=403, detail="Forbidden")

    conn = get_engine_user().connect()
    try:
        users_total = _scalar(conn, "SELECT COUNT(*) FROM users")
        users_7d = _scalar(conn, "SELECT COUNT(*) FROM users WHERE created_at > now() - interval '7 days'")
        admins = _scalar(conn, "SELECT COUNT(*) FROM users WHERE is_admin = TRUE")
        logged_in_users = _scalar(conn, "SELECT COUNT(*) FROM users WHERE COALESCE(login_count,0) > 0")

        logins_total = _scalar(conn, "SELECT COUNT(*) FROM login_events")
        logins_7d = _scalar(conn, "SELECT COUNT(*) FROM login_events WHERE at > now() - interval '7 days'")
        login_distinct = _scalar(conn, "SELECT COUNT(DISTINCT user_id) FROM login_events")

        api_keys = _scalar(conn, "SELECT COUNT(*) FROM api_keys")
        api_calls = _scalar(conn, "SELECT COUNT(*) FROM api_call_log")
        api_calls_7d = _scalar(conn, "SELECT COUNT(*) FROM api_call_log WHERE at > now() - interval '7 days'")

        fb_total = _scalar(conn, "SELECT COUNT(*) FROM experience_feedback")
        fb_avg = _scalar(conn, "SELECT ROUND(AVG(rating)::numeric, 2) FROM experience_feedback WHERE rating IS NOT NULL", "—")
        fb_rating = _rows(conn, "SELECT rating, COUNT(*) FROM experience_feedback WHERE rating IS NOT NULL GROUP BY rating ORDER BY rating DESC")
        fb_group = _rows(conn, "SELECT COALESCE(user_group, '(không chọn)'), COUNT(*) FROM experience_feedback GROUP BY user_group ORDER BY 2 DESC")
        fb_recent = _rows(conn, "SELECT created_at, rating, user_group, looking_for, improvement, page_url FROM experience_feedback ORDER BY created_at DESC LIMIT 40")
    finally:
        conn.close()

    cards = "".join([
        _card("Người dùng", users_total, f"+{users_7d} trong 7 ngày · {logged_in_users} đã đăng nhập · {admins} admin"),
        _card("Lượt đăng nhập", logins_total, f"+{logins_7d} trong 7 ngày · {login_distinct} người khác nhau"),
        _card("API keys", api_keys, f"{api_calls} lượt gọi · +{api_calls_7d} trong 7 ngày"),
        _card("Góp ý", fb_total, f"Điểm TB: {fb_avg} ★"),
    ])

    rating_rows = "".join(f"<tr><td>{'★' * int(r[0])} ({r[0]})</td><td>{r[1]}</td></tr>" for r in fb_rating) or "<tr><td colspan=2>Chưa có</td></tr>"
    group_rows = "".join(f"<tr><td>{_esc(r[0])}</td><td>{r[1]}</td></tr>" for r in fb_group) or "<tr><td colspan=2>Chưa có</td></tr>"
    recent_rows = "".join(
        f"<tr><td>{_esc(str(r[0])[:16])}</td><td>{('★'*int(r[1])) if r[1] else '—'}</td><td>{_esc(r[2])}</td>"
        f"<td>{_esc(r[3])}</td><td>{_esc(r[4])}</td></tr>"
        for r in fb_recent
    ) or "<tr><td colspan=5>Chưa có góp ý nào (widget chưa deploy hoặc chưa ai gửi).</td></tr>"

    html = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Viet Dataverse — Báo cáo nội bộ</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; background:#f5f4ed; color:#141413; margin:0; padding:24px; }}
  h1 {{ font-size:22px; margin:0 0 4px; }} .muted {{ color:#87867f; font-size:13px; margin:0 0 20px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:14px; margin-bottom:26px; }}
  .card {{ background:#faf9f5; border:1px solid #f0eee6; border-radius:12px; padding:16px 18px; }}
  .card .lbl {{ font-size:12px; color:#87867f; text-transform:uppercase; letter-spacing:.04em; }}
  .card .val {{ font-size:30px; font-weight:600; margin-top:4px; }}
  .card .sub {{ font-size:12px; color:#5e5d59; margin-top:6px; }}
  h2 {{ font-size:16px; margin:24px 0 10px; }}
  table {{ width:100%; border-collapse:collapse; background:#faf9f5; border:1px solid #f0eee6; border-radius:10px; overflow:hidden; font-size:13px; }}
  th,td {{ text-align:left; padding:8px 12px; border-bottom:1px solid #f0eee6; vertical-align:top; }}
  th {{ background:#efeee7; color:#5e5d59; font-weight:500; }}
  .two {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
  @media(max-width:640px){{ .two {{ grid-template-columns:1fr; }} }}
  .note {{ background:#faf1ec; border:1px solid #f0d9cd; border-radius:10px; padding:12px 14px; font-size:13px; color:#5e5d59; margin-top:22px; }}
</style></head><body>
<h1>Viet Dataverse — Báo cáo nội bộ</h1>
<p class="muted">Số liệu từ USER_DB (thời gian thực). Lượt truy cập / pageviews nằm ở Google Analytics.</p>
<div class="cards">{cards}</div>
<div class="two">
  <div><h2>Phân bố sao</h2><table><tr><th>Đánh giá</th><th>Số lượt</th></tr>{rating_rows}</table></div>
  <div><h2>Nhóm người dùng (Góp ý)</h2><table><tr><th>Nhóm</th><th>Số lượt</th></tr>{group_rows}</table></div>
</div>
<h2>Góp ý gần đây</h2>
<table><tr><th>Thời gian</th><th>Sao</th><th>Nhóm</th><th>Đang tìm gì</th><th>Cải thiện gì</th></tr>{recent_rows}</table>
<div class="note"><strong>Lượt truy cập (pageviews):</strong> không lưu ở server — xem tại
<a href="https://analytics.google.com/" target="_blank" rel="noopener">Google Analytics</a> (property vietdataverse.online).
Báo cáo này chỉ đếm những gì backend ghi nhận: đăng ký, đăng nhập, gọi API, và góp ý.</div>
</body></html>"""
    return HTMLResponse(content=html)
