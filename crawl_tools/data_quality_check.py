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

def last_business_day(d):
    """Most recent Mon–Fri strictly before `d`.

    Market tables (HSX/VN30, VN-Index) have no weekend rows by construction, so
    comparing them against a plain T-1 made every Monday run fail: T-1 is Sunday.
    That false ERROR fired 2 days out of 7 and is part of why the daily report
    was ignored."""
    d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

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
# (table, db_key, date_col, period_type, numeric_cols, valid_range, dup_key, market_days)
#
# dup_key: the table's REAL business key. The check used to group by
# (period, source) for every table, but `source` is a constant per crawler
# ('24h.com.vn' for all gold rows), so it reported one "duplicate" per extra
# brand/ticker/bank on the same day — 4019 for gold, 2730 for vn30_ohlcv, none
# of them real. Grouping by the key the unique index actually enforces gives 0.
#
# market_days: table only has Mon–Fri rows, so freshness compares against the
# last business day rather than T-1.
TABLES = [
    # ── Macro / BOT DB ────────────────────────────────────────────────────────
    ('vn_macro_gold_daily',       'CRAWLING_BOT_DB',
     'date', 'date',
     ['buy_price', 'sell_price'],
     # Floor is 15M, not 50M: gold legitimately traded at ~20M/lượng in 2009,
     # the first year this table covers. A 50M floor flagged 21k rows of
     # correct history.
     (15_000_000, 250_000_000),
     ('date', 'type'), False),

    ('vn_macro_silver_daily',     'CRAWLING_BOT_DB',
     'date', 'date',
     ['buy_price', 'sell_price'],
     (500_000, 5_000_000),
     ('date', 'source'), False),

    ('vn_macro_termdepo_daily',   'CRAWLING_BOT_DB',
     'date', 'date',
     ['term_1m', 'term_3m', 'term_6m', 'term_12m'],
     (0.1, 20.0),
     ('date', 'bank_code'), False),

    ('vn_macro_fxrate_daily',     'CRAWLING_BOT_DB',
     'date', 'date',
     ['usd_vnd_rate'],
     (20_000, 35_000),
     ('date', 'bank', 'type'), False,
     # The table holds one row per currency; usd_vnd_rate is populated only on
     # the USD row, so an unscoped NULL check flagged 9,178 correct EUR/JPY/…
     # rows every day.
     "type = 'USD'"),

    ('vn_macro_sbv_rate_daily',   'CRAWLING_BOT_DB',
     'date', 'date',
     ['ls_quadem'],
     (0.0, 30.0),
     ('date',), True,
     # Rows before the daily interbank feed began are policy-decision records
     # (refinancing/rediscount only) and legitimately have no overnight rate.
     'refinancing_rate IS NULL'),

    ('vn_macro_vnindex_daily',    'CRAWLING_BOT_DB',
     'date', 'date',
     ['close'],
     (100.0, 5_000.0),
     ('date',), True),

    ('vn_gso_cpi_monthly',        'CRAWLING_BOT_DB',
     'period', 'month',
     ['cpi_mom_pct', 'cpi_yoy_pct'],
     (-5.0, 30.0),
     ('period',), False),

    ('vn_gso_gdp_quarterly',      'CRAWLING_BOT_DB',
     'year', 'quarter',
     ['gdp_billion_vnd', 'growth_yoy_pct'],
     (-10.0, 1_000_000),
     ('year',), False),

    # ── Corp DB ───────────────────────────────────────────────────────────────
    ('vn30_ohlcv_daily',          'CRAWLING_CORP_DB',
     'date', 'date',
     # Prices are quoted in THOUSAND VND (close ranges 1.29–236), so the old
     # [1000, 500000] range flagged all 73,307 rows — a 100% hit rate, which is
     # a broken threshold, not a data problem.
     ['open', 'high', 'low', 'close'],
     (0.5, 1_000.0),
     ('ticker', 'date'), True),

    ('vn30_ratio_daily',          'CRAWLING_CORP_DB',
     'date', 'date',
     # pe/pb silently went 100% NULL on 2026-05-15 when both upstream ratio
     # sources broke, and nothing noticed because this table was not checked.
     ['pe', 'pb', 'roe', 'eps'],
     (-1_000.0, 10_000.0),
     ('ticker', 'date'), True),

    # ── Global DB ────────────────────────────────────────────────────────────
    ('global_macro',              'GLOBAL_INDICATOR_DB',
     'date', 'date',
     ['gold_price', 'silver_price', 'nasdaq_price', 'sp500_price', 'dowjones_price'],
     (0, 1_000_000),
     ('date',), False),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def flag(table, db, check, detail, severity='WARNING'):
    issues.append({'table': table, 'db': db, 'check': check,
                   'detail': detail, 'severity': severity})


def check_table(table, db_key, period_col, period_type, numeric_cols, valid_range,
                dup_key=None, market_days=False, null_filter=None):
    engine = ENGINES.get(db_key)
    if engine is None:
        return

    # Probe the connection first so a single bad credential (e.g. a rotated Neon
    # password not synced to GitHub secrets) flags one DB instead of crashing the
    # whole run and blinding every other freshness check.
    try:
        engine.connect().close()
    except Exception as e:
        flag(table, db_key, 'db_connection',
             f'Cannot connect to {db_key}: {str(e).splitlines()[0][:160]}', 'CRITICAL')
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

        # 2. Freshness
        if period_type == 'date':
            cut = last_business_day(TODAY) if market_days else CUTOFF
            recent = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {period_col} >= :d"),
                {'d': cut.isoformat()}
            ).scalar()
            if recent == 0:
                # SBV publishes its interbank series with a lag of several days
                # and the crawler can only read the newest record the API
                # returns (pageSize=1), so a gap here is the source's cadence,
                # not a broken pipeline. Reported, but not as an ERROR.
                sev = 'WARNING' if table == 'vn_macro_sbv_rate_daily' else 'ERROR'
                flag(table, db_key, 'freshness',
                     f'No row for {cut} or later', sev)
                freshness_ok = False
        elif period_type == 'month':
            # Monthly reports for month M publish early in M+1, so by mid-month the
            # previous month must exist. Allow a 2-month lag before flagging (tolerates
            # source delay) — period stored as 'YYYY-MM', lexicographic compare is safe.
            fy, fm = TODAY.year, TODAY.month - 2
            while fm <= 0:
                fm += 12
                fy -= 1
            floor_ym = f"{fy:04d}-{fm:02d}"
            try:
                latest = conn.execute(text(f"SELECT MAX({period_col}) FROM {table}")).scalar()
            except Exception:
                latest = None
            if not latest or str(latest) < floor_ym:
                flag(table, db_key, 'freshness',
                     f'Latest {period_col}={latest}, expected ≥ {floor_ym}', 'ERROR')
                freshness_ok = False

        # 3. Nulls in required columns — RECENT rows only.
        #
        # This check answers "is the pipeline filling this column today?", not
        # "has every row since 2002 been complete". Scoping it to a recent window
        # stops long-closed historical gaps (PNJ stopped publishing a buy price
        # between 2022 and 2024; CPI has 17 missing months across 23 years) from
        # re-reporting forever, which is what turned the daily mail into noise.
        # It still catches a live outage: vn30_ratio's pe/pb went 100% NULL on
        # 2026-05-15 and would fire here on day one.
        if period_type == 'date':
            window = f"{period_col} >= CURRENT_DATE - 90"
        else:
            # 'YYYY-MM' / 'YYYY' strings — lexicographic compare is safe
            window = f"{period_col} >= '{(TODAY.year - 2):04d}'"
        scope = f"{window} AND ({null_filter})" if null_filter else window
        for col in numeric_cols:
            try:
                n = conn.execute(
                    text(f'SELECT COUNT(*) FROM {table} WHERE {col} IS NULL AND {scope}')
                ).scalar()
                total = conn.execute(
                    text(f'SELECT COUNT(*) FROM {table} WHERE {scope}')
                ).scalar()
                # A couple of gaps is normal — US indices have no Sunday or
                # market-holiday row while gold futures do, which produced three
                # standing warnings for correct data. A column that has largely
                # stopped filling is the real signal.
                if n and total and (n / total) >= 0.10:
                    flag(table, db_key, 'null_values',
                         f'{col}: {n}/{total} ({n*100//total}%) NULL in recent rows', 'WARNING')
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

        # 5. Duplicates on the table's REAL business key (see TABLES.dup_key)
        key = dup_key or (period_col,)
        cols = ', '.join(key)
        try:
            dup_count = conn.execute(
                text(f'SELECT COUNT(*) FROM ('
                     f'  SELECT {cols} '
                     f'  FROM {table} '
                     f'  GROUP BY {cols} '
                     f'  HAVING COUNT(*) > 1'
                     f') t')
            ).scalar()
            if dup_count:
                flag(table, db_key, 'duplicates',
                     f'{dup_count} duplicate ({cols}) combos', 'ERROR')
        except Exception:
            pass  # a key column may be absent on older table variants

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
    try:
        engine.connect().close()
    except Exception as e:
        flag('—', 'USER_DB', 'db_connection',
             f'Cannot connect to USER_DB: {str(e).splitlines()[0][:160]}', 'CRITICAL')
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
