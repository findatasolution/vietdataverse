"""GA4 Reporting API client — OAuth refresh-token auth (not a service account;
GCP org policy `iam.disableServiceAccountKeyCreation` blocks service-account
key downloads on this project, see CLAUDE.md if that ever needs revisiting)."""

import os
from datetime import date
from functools import lru_cache

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest
from google.oauth2.credentials import Credentials

GA4_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")
_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]

_PERIOD_RANGES = {
    "24h": {"start_date": "yesterday", "end_date": "today"},
    "7d":  {"start_date": "7daysAgo", "end_date": "today"},
    "ytd": {"start_date": f"{date.today().year}-01-01", "end_date": "today"},
}


def is_configured() -> bool:
    return bool(
        GA4_PROPERTY_ID
        and os.getenv("GA4_OAUTH_REFRESH_TOKEN")
        and os.getenv("GA4_OAUTH_CLIENT_ID")
        and os.getenv("GA4_OAUTH_CLIENT_SECRET")
    )


@lru_cache(maxsize=1)
def _client() -> BetaAnalyticsDataClient:
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GA4_OAUTH_REFRESH_TOKEN"),
        client_id=os.getenv("GA4_OAUTH_CLIENT_ID"),
        client_secret=os.getenv("GA4_OAUTH_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=_SCOPES,
    )
    return BetaAnalyticsDataClient(credentials=creds)


def get_traffic_summary(period: str) -> dict:
    """Site-wide active users / pageviews / sessions / new users for one
    _REPORT_PERIODS-style period key (24h/7d/ytd, see routers/admin.py)."""
    date_range = _PERIOD_RANGES.get(period, _PERIOD_RANGES["7d"])
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="newUsers"),
        ],
        date_ranges=[DateRange(**date_range)],
    )
    response = _client().run_report(request)
    if not response.rows:
        return {"active_users": 0, "pageviews": 0, "sessions": 0, "new_users": 0}
    row = response.rows[0]
    return {
        "active_users": int(row.metric_values[0].value),
        "pageviews":    int(row.metric_values[1].value),
        "sessions":     int(row.metric_values[2].value),
        "new_users":    int(row.metric_values[3].value),
    }
