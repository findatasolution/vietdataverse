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
CRAWLING_BOT_DB    = os.getenv('CRAWLING_BOT_DB')
CRAWLING_CORP_DB   = os.getenv('CRAWLING_CORP_DB')
GLOBAL_INDICATOR_DB = os.getenv('GLOBAL_INDICATOR_DB')

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')          # sender Gmail address
SMTP_PASS = os.getenv('SMTP_PASS')          # Gmail App Password
REPORT_TO = 'findatasolution@gmail.com'

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)

issues: list[dict] = []   # {table, db, check, detail, severity}
summaries: list[dict] = []


def eng(db_url: str | None, label: str):
    if not db_url:
        issues.append({'table': '—', 'db': label, 'check': 'env',
                       'detail': f'{label} env var not set', 'severity': 'CRITICAL'})
        return None
    return create_engine(db_url)


ENGINES = {
    'CRAWLING_BOT_DB':    eng(CRAWLING_BOT_DB,    'CRAWLING_BOT_DB'),
    'CRAWLING_CORP_DB':   eng(CRAWLING_CORP_DB,   'CRAWLING_CORP_DB'),
    'GLOBAL_INDICATOR_DB': eng(GLOBAL_INDICATOR_DB, 'GLOBAL_INDICATOR_DB'),
}

# ── Table catalogue ───────────────────────────────────────────────────────────
# (table_name, db_key, period_col, period_type, numeric_cols, valid_range)
TABLES = [
    # ── Macro / BOT DB ────────────────────────────────────────────────────────
    ('vn_macro_gold_daily',       'CRAWLING_BOT_DB',
     'period', 'date',
     ['btmc_buy', 'btmc_sell', 'sjc_buy', 'sjc_sell'],
     (50_000_000, 200_000_000)),

    ('vn_macro_silver_daily',     'CRAWLING_BOT_DB',
     'period', 'date',
     ['buy_price', 'sell_price'],
     (500_000, 5_000_000)),

    ('vn_macro_termdepo_daily',   'CRAWLING_BOT_DB',
     'period', 'date',
     ['term_1m', 'term_3m', 'term_6m', 'term_12m'],
     (0.1, 20.0)),

    ('vn_macro_sbv_rate_daily',   'CRAWLING_BOT_DB',
     'period', 'date',
     ['usd_buy', 'usd_sell'],
     (20_000, 35_000)),

    ('vn_gso_cpi_monthly',        'CRAWLING_BOT_DB',
     'period', 'month',
     ['cpi_mom', 'cpi_yoy'],
     (-5.0, 30.0)),

    ('vn_gso_gdp_quarterly',      'CRAWLING_BOT_DB',
     'period', 'quarter',
     ['gdp_growth'],
     (-10.0, 20.0)),

    # ── Corp DB ───────────────────────────────────────────────────────────────
    ('vn30_ohlcv_daily',          'CRAWLING_CORP_DB',
     'period', 'date',
     ['open', 'high', 'low', 'close', 'volume'],
     (1_000, 500_000)),

    # ── Global DB ────────────────────────────────────────────────────────────
    ('global_macro',              'GLOBAL_INDICATOR_DB',
     'period', 'date',
     ['value'],
     (-1_000_000, 1_000_000)),
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
            cutoff = YESTERDAY.isoformat()
            recent = conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {period_col} >= :d"),
                {'d': cutoff}
            ).scalar()
            if recent == 0:
                flag(table, db_key, 'freshness',
                     f'No row for {YESTERDAY} or today', 'ERROR')
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


# ── Run all checks ────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"Data Quality Check — {TODAY}")
print(f"{'='*60}\n")

for args in TABLES:
    print(f"  Checking {args[0]} …")
    check_table(*args)

n_critical = sum(1 for i in issues if i['severity'] == 'CRITICAL')
n_error    = sum(1 for i in issues if i['severity'] == 'ERROR')
n_warning  = sum(1 for i in issues if i['severity'] == 'WARNING')

print(f"\nResult: {n_critical} CRITICAL / {n_error} ERROR / {n_warning} WARNING")

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


html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, Arial, sans-serif; color: #222; margin: 0; padding: 20px; }}
  h2   {{ margin-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; font-size: 13px; }}
  th   {{ background: #2c3e50; color: #fff; padding: 8px 10px; text-align: left; }}
  td   {{ border-bottom: 1px solid #e0e0e0; padding: 7px 10px; }}
  tr:hover td {{ background: #f5f5f5; }}
  code {{ background: #f0f0f0; padding: 1px 4px; border-radius: 3px; font-size: 12px; }}
  .badge {{ display:inline-block; padding: 6px 14px; border-radius: 20px;
            color:#fff; font-weight:bold; font-size:15px; background:{overall_color}; }}
</style>
</head>
<body>
<h2>🗄️ Viet Dataverse — Daily Data Quality Report</h2>
<p style="color:#666; margin-top:2px">{TODAY.strftime('%A, %d %B %Y')} &nbsp;|&nbsp; Generated at {datetime.utcnow().strftime('%H:%M UTC')}</p>

<p>Overall status: <span class="badge">{overall_label}</span>
&nbsp; <span style="color:{STATUS_COLOR.get('CRITICAL','#c0392b')}">{n_critical} CRITICAL</span>
&nbsp; <span style="color:{STATUS_COLOR.get('ERROR','#e67e22')}">{n_error} ERROR</span>
&nbsp; <span style="color:{STATUS_COLOR.get('WARNING','#f1c40f')}">{n_warning} WARNING</span>
</p>

<h3>Table Summary</h3>
<table>
  <thead>
    <tr>
      <th>Table</th><th>Rows</th><th>Fresh?</th>
      <th>Nulls</th><th>Dups</th><th>Range Issues</th>
    </tr>
  </thead>
  <tbody>{summary_rows()}</tbody>
</table>

<h3>Issue Details</h3>
<table>
  <thead>
    <tr><th>Severity</th><th>Table</th><th>Database</th><th>Check</th><th>Detail</th></tr>
  </thead>
  <tbody>{issue_rows()}</tbody>
</table>

<p style="color:#aaa; font-size:11px; border-top:1px solid #eee; padding-top:10px">
  Auto-generated by Viet Dataverse data-quality-check agent.
  Reply to this email or check GitHub Actions for more details.
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
