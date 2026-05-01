"""
Daily Data Quality Check Agent
Runs every day at 09:00 VN (02:00 UTC) — after all crawlers finish.
Checks each table for freshness, nulls, out-of-range values, duplicates,
then sends an HTML email report to findatasolution@gmail.com.
"""

import sys
import os
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

# ── DB connections ────────────────────────────────────────────────────────────
CRAWLING_BOT_DB     = os.getenv('CRAWLING_BOT_DB')
CRAWLING_CORP_DB    = os.getenv('CRAWLING_CORP_DB')
GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')
USER_DB             = os.getenv('USER_DB')

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
REPORT_TO = 'findatasolution@gmail.com'

TODAY  = date.today()
CUTOFF = TODAY - timedelta(days=1)

issues: list[dict]    = []
summaries: list[dict] = []


def eng(db_url: str | None, label: str):
    if not db_url:
        issues.append({'table': '—', 'db': label, 'check': 'env',
                       'detail': f'{label} env var not set', 'severity': 'CRITICAL'})
        return None
    return create_engine(db_url)


ENGINES = {
    'CRAWLING_BOT_DB':     eng(CRAWLING_BOT_DB,     'CRAWLING_BOT_DB'),
    'CRAWLING_CORP_DB':    eng(CRAWLING_CORP_DB,     'CRAWLING_CORP_DB'),
    'GLOBAL_INDICATOR_DB': eng(GLOBAL_INDICATOR_DB,  'GLOBAL_INDICATOR_DB'),
    'USER_DB':             eng(USER_DB,              'USER_DB'),
}

# ── Table catalogue ───────────────────────────────────────────────────────────
# (table_name, db_key, date_col, period_type, numeric_cols, valid_range)
# period_type: 'date' = daily (check T-1), 'month'/'quarter' = skip freshness
TABLES = [
    # ── Macro / BOT DB ────────────────────────────────────────────────────────
    ('vn_macro_gold_daily',       'CRAWLING_BOT_DB',
     'date', 'date',
     ['buy_price', 'sell_price'],
     (50_000_000, 200_000_000)),

    ('vn_macro_silver_daily',     'CRAWLING_BOT_DB',
     'date', 'date',
     ['buy_price', 'sell_price'],
     (500_000, 5_000_000)),

    ('vn_macro_termdepo_daily',   'CRAWLING_BOT_DB',
     'date', 'date',
     ['term_1m', 'term_3m', 'term_6m', 'term_12m'],
     (0.1, 20.0)),

    ('vn_macro_fxrate_daily',     'CRAWLING_BOT_DB',
     'date', 'date',
     ['usd_vnd_rate'],
     (20_000, 35_000)),

    ('vn_gso_cpi_monthly',        'CRAWLING_BOT_DB',
     'period', 'month',
     ['cpi_mom', 'cpi_yoy'],
     (-5.0, 30.0)),

    ('vn_gso_gdp_quarterly',      'CRAWLING_BOT_DB',
     'year', 'quarter',
     ['gdp_billion_vnd', 'growth_yoy_pct'],
     (-10.0, 1_000_000)),

    # ── Corp DB ───────────────────────────────────────────────────────────────
    ('vn30_ohlcv_daily',          'CRAWLING_CORP_DB',
     'date', 'date',
     ['open', 'high', 'low', 'close', 'volume'],
     (1_000, 500_000)),

    # ── Global DB ────────────────────────────────────────────────────────────
    ('global_macro',              'GLOBAL_INDICATOR_DB',
     'date', 'date',
     ['gold_price', 'silver_price', 'nasdaq_price'],
     (0, 1_000_000)),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def flag(table, db, check, detail, severity='WARNING'):
    issues.append({'table': table, 'db': db, 'check': check,
                   'detail': detail, 'severity': severity})


def check_table(table, db_key, period_col, period_type, numeric_cols, valid_range):
    engine = ENGINES.get(db_key)
    if engine is None:
        return

    row_count = null_counts = dup_count = range_issues = 0
    freshness_ok = True

    with engine.connect() as conn:
        # 1. Row count
        try:
            row_count = conn.execute(
                text(f'SELECT COUNT(*) FROM {table}')
            ).scalar()
        except Exception as e:
            flag(table, db_key, 'table_exists', str(e), 'CRITICAL')
            return

        if row_count == 0:
            flag(table, db_key, 'empty_table', 'Table has 0 rows', 'CRITICAL')

        # 2. Freshness — skip monthly/quarterly when today isn't EOM
        if period_type == 'date':
            cutoff = CUTOFF.isoformat()
            recent = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {period_col} >= :d"),
                {'d': cutoff}
            ).scalar()
            if recent == 0:
                flag(table, db_key, 'freshness',
                     f'No row for {CUTOFF} or today', 'ERROR')
                freshness_ok = False

        # 3. Nulls in required columns
        for col in numeric_cols:
            try:
                n = conn.execute(
                    text(f'SELECT COUNT(*) FROM {table} WHERE {col} IS NULL')
                ).scalar()
                if n:
                    flag(table, db_key, 'null_values',
                         f'{col}: {n} NULL rows', 'WARNING')
                    null_counts += n
            except Exception:
                pass  # column may not exist in all table variants

        # 4. Out-of-range values (sample first numeric col)
        lo, hi = valid_range
        for col in numeric_cols[:2]:
            try:
                n = conn.execute(
                    text(f'SELECT COUNT(*) FROM {table} '
                         f'WHERE {col} IS NOT NULL AND ({col} < :lo OR {col} > :hi)'),
                    {'lo': lo, 'hi': hi}
                ).scalar()
                if n:
                    flag(table, db_key, 'out_of_range',
                         f'{col}: {n} rows outside [{lo}, {hi}]', 'WARNING')
                    range_issues += n
            except Exception:
                pass

        # 5. Duplicates on (period, source) if both columns exist
        try:
            dup_count = conn.execute(
                text(f'SELECT COUNT(*) FROM ('
                     f'  SELECT {period_col}, source, COUNT(*) c '
                     f'  FROM {table} '
                     f'  GROUP BY {period_col}, source '
                     f'  HAVING COUNT(*) > 1'
                     f') t')
            ).scalar()
            if dup_count:
                flag(table, db_key, 'duplicates',
                     f'{dup_count} duplicate (period, source) combos', 'ERROR')
        except Exception:
            pass  # source column may be absent on older tables

    summaries.append({
        'table': table, 'db': db_key,
        'rows': row_count, 'fresh': freshness_ok,
        'nulls': null_counts, 'dups': dup_count,
        'range_issues': range_issues,
    })


# ── User & payment stats from USER_DB ────────────────────────────────────────

def fetch_user_stats() -> dict:
    """
    - active_users : distinct users who made ≥1 API call on CUTOFF (api_call_log)
    - new_signups  : users whose account was created on CUTOFF (users.created_at)
    - paid_orders  : payment_orders with status='paid' and updated on CUTOFF
    - total_users  : all-time user count
    - paid_users   : users with current_plan != 'free'
    """
    stats = {
        'active_users': 'N/A', 'new_signups': 'N/A',
        'paid_orders': 'N/A', 'total_users': 'N/A', 'paid_users': 'N/A',
    }
    engine = ENGINES.get('USER_DB')
    if engine is None:
        return stats
    with engine.connect() as conn:
        cutoff = CUTOFF.isoformat()
        queries = {
            'active_users': text("""
                SELECT COUNT(DISTINCT user_id) FROM api_call_log
                WHERE DATE(created_at) = :d
            """),
            'new_signups': text("""
                SELECT COUNT(*) FROM users
                WHERE DATE(created_at) = :d
            """),
            'paid_orders': text("""
                SELECT COUNT(*) FROM payment_orders
                WHERE status = 'paid' AND DATE(updated_at) = :d
            """),
            'total_users': text("SELECT COUNT(*) FROM users"),
            'paid_users':  text("SELECT COUNT(*) FROM users WHERE current_plan != 'free'"),
        }
        for key, q in queries.items():
            try:
                params = {'d': cutoff} if ':d' in str(q) else {}
                stats[key] = conn.execute(q, params).scalar() or 0
            except Exception:
                pass
    return stats


# ── Sales action suggestions ──────────────────────────────────────────────────

def sales_actions(stats: dict) -> list[str]:
    actions = []
    total = stats.get('total_users', 0)
    paid  = stats.get('paid_users', 0)
    active = stats.get('active_users', 0)

    if isinstance(total, int) and isinstance(paid, int) and total > 0:
        free_pct = round((total - paid) / total * 100)
        if free_pct > 80:
            actions.append(
                f'{free_pct}% users on free plan ({total - paid}/{total}) — '
                f'send upgrade campaign to active free users'
            )

    if isinstance(active, int) and active > 0 and isinstance(paid, int):
        if active > paid * 2:
            actions.append(
                f'{active} active users yesterday but only {paid} paid — '
                f'consider triggered upsell email to heavy free users'
            )

    new = stats.get('new_signups', 0)
    if isinstance(new, int) and new > 0:
        actions.append(
            f'{new} new signup(s) on {CUTOFF} — send onboarding email within 24h'
        )

    if not actions:
        actions.append('No specific sales actions needed today')
    return actions


# ── Run all checks ────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"Data Quality Check — run {TODAY}, cutoff {CUTOFF}")
print(f"{'='*60}\n")

for args in TABLES:
    print(f"  Checking {args[0]} …")
    check_table(*args)

print("  Fetching user & payment stats …")
user_stats = fetch_user_stats()

n_critical = sum(1 for i in issues if i['severity'] == 'CRITICAL')
n_error    = sum(1 for i in issues if i['severity'] == 'ERROR')
n_warning  = sum(1 for i in issues if i['severity'] == 'WARNING')

print(f"\nResult: {n_critical} CRITICAL / {n_error} ERROR / {n_warning} WARNING")
print(f"Users active T-1: {user_stats['active_users']} | New signups: {user_stats['new_signups']} | Paid orders: {user_stats['paid_orders']}")

# ── Build HTML report ─────────────────────────────────────────────────────────

STATUS_COLOR = {'CRITICAL': '#c0392b', 'ERROR': '#e67e22', 'WARNING': '#f1c40f'}
STATUS_BG    = {'CRITICAL': '#fdecea', 'ERROR': '#fef3e2', 'WARNING': '#fefce8'}

overall_color = '#27ae60'
overall_label = 'ALL CLEAR'
if n_warning:
    overall_color = '#f39c12'; overall_label = 'WARNINGS'
if n_error:
    overall_color = '#e67e22'; overall_label = 'ERRORS'
if n_critical:
    overall_color = '#c0392b'; overall_label = 'CRITICAL'


def summary_rows():
    rows = []
    for s in summaries:
        ok_icon  = '✅' if s['fresh'] else '❌'
        nul_icon = '✅' if s['nulls'] == 0 else '⚠️'
        dup_icon = '✅' if s['dups'] == 0 else '❌'
        rng_icon = '✅' if s['range_issues'] == 0 else '⚠️'
        rows.append(f"""
        <tr>
          <td><code>{s['table']}</code></td>
          <td style="text-align:center">{s['rows']:,}</td>
          <td style="text-align:center">{ok_icon}</td>
          <td style="text-align:center">{nul_icon} {s['nulls']}</td>
          <td style="text-align:center">{dup_icon} {s['dups']}</td>
          <td style="text-align:center">{rng_icon} {s['range_issues']}</td>
        </tr>""")
    return '\n'.join(rows)


def issue_rows():
    if not issues:
        return '<tr><td colspan="5" style="text-align:center;color:#27ae60">No issues found 🎉</td></tr>'
    rows = []
    for i in issues:
        c = STATUS_COLOR.get(i['severity'], '#333')
        bg = STATUS_BG.get(i['severity'], '#fff')
        rows.append(f"""
        <tr style="background:{bg}">
          <td><strong style="color:{c}">{i['severity']}</strong></td>
          <td><code>{i['table']}</code></td>
          <td>{i['db']}</td>
          <td>{i['check']}</td>
          <td>{i['detail']}</td>
        </tr>""")
    return '\n'.join(rows)


_actions = sales_actions(user_stats)

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body  {{ font-family: -apple-system, Arial, sans-serif; color: #222;
           max-width: 780px; margin: 0 auto; padding: 24px; }}
  h2   {{ margin-bottom: 2px; color: #1a1a2e; }}
  h3   {{ margin: 22px 0 6px; border-bottom: 2px solid #eee; padding-bottom: 4px; }}
  ul   {{ margin: 6px 0; padding-left: 20px; line-height: 1.9; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 16px; font-size: 13px; }}
  th   {{ background: #2c3e50; color: #fff; padding: 8px 10px; text-align: left; }}
  td   {{ border-bottom: 1px solid #e0e0e0; padding: 7px 10px; }}
  code {{ background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: 12px; }}
  .badge {{ display:inline-block; padding: 5px 14px; border-radius: 16px;
            color:#fff; font-weight:bold; font-size:14px; background:{overall_color}; }}
  .kpi  {{ display:inline-block; background:#f4f6f8; border-radius:8px;
           padding:10px 18px; margin:4px 8px 4px 0; text-align:center; min-width:90px; }}
  .kpi-n {{ font-size:22px; font-weight:bold; color:#2c3e50; }}
  .kpi-l {{ font-size:11px; color:#888; margin-top:2px; }}
</style>
</head>
<body>

<h2>🗄️ Viet Dataverse — Daily Report</h2>
<p style="color:#888; margin-top:2px; font-size:13px">
  Report date: <strong>{TODAY.strftime('%A, %d %B %Y')}</strong>
  &nbsp;|&nbsp; Data cutoff: <strong>{CUTOFF}</strong>
  &nbsp;|&nbsp; {datetime.utcnow().strftime('%H:%M UTC')}
  &nbsp;|&nbsp; <span class="badge">{overall_label}</span>
</p>

<h3>👤 No. User Visited</h3>
<div>
  <div class="kpi"><div class="kpi-n">{user_stats['active_users']}</div><div class="kpi-l">Active users (T-1)</div></div>
  <div class="kpi"><div class="kpi-n">{user_stats['new_signups']}</div><div class="kpi-l">New signups</div></div>
  <div class="kpi"><div class="kpi-n">{user_stats['total_users']}</div><div class="kpi-l">Total users</div></div>
  <div class="kpi"><div class="kpi-n">{user_stats['paid_users']}</div><div class="kpi-l">Paid users</div></div>
</div>

<h3>💳 No. Payments</h3>
<div>
  <div class="kpi"><div class="kpi-n" style="color:#27ae60">{user_stats['paid_orders']}</div><div class="kpi-l">Orders paid on {CUTOFF}</div></div>
</div>

<h3>🚀 Action to Push Sales</h3>
<ul>
{''.join(f"<li>{a}</li>" for a in _actions)}
</ul>

<h3>📥 Ingestion Tools</h3>
<p style="color:#888;font-size:12px;margin:0 0 4px">
  {n_critical} CRITICAL &nbsp; {n_error} ERROR &nbsp; {n_warning} WARNING
</p>
<table>
  <thead>
    <tr><th>Table</th><th>Rows</th><th>Fresh ({CUTOFF})?</th><th>Nulls</th><th>Dups</th><th>Range</th></tr>
  </thead>
  <tbody>{summary_rows()}</tbody>
</table>

<h3>🔍 Data Quality Check</h3>
<table>
  <thead>
    <tr><th>Severity</th><th>Table</th><th>Database</th><th>Check</th><th>Detail</th></tr>
  </thead>
  <tbody>{issue_rows()}</tbody>
</table>

<p style="color:#ccc; font-size:11px; border-top:1px solid #eee; margin-top:20px; padding-top:10px">
  Auto-generated by Viet Dataverse DQ agent · {TODAY}
</p>
</body>
</html>"""

# ── Send email ────────────────────────────────────────────────────────────────

if not SMTP_USER or not SMTP_PASS:
    print("WARNING: SMTP_USER / SMTP_PASS not set — skipping email send.")
    print("\n--- HTML report preview (first 500 chars) ---")
    print(html[:500])
    sys.exit(0 if n_critical == 0 else 1)

subject_prefix = f"[{'CRITICAL' if n_critical else 'ERROR' if n_error else 'OK'}]"
subject = f"{subject_prefix} Viet Dataverse DQ Report — {TODAY}"

msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From']    = SMTP_USER
msg['To']      = REPORT_TO
msg.attach(MIMEText(html, 'html'))

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, REPORT_TO, msg.as_string())
    print(f"Email sent to {REPORT_TO}")
except Exception as e:
    print(f"ERROR sending email: {e}")
    sys.exit(1)

# Exit non-zero when there are critical issues so GitHub marks the run red
sys.exit(1 if n_critical else 0)
