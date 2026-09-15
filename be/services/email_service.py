"""Email service via Resend API. Multi-template with Jinja2.

If RESEND_API_KEY is empty or 'DEV_MODE_LOG_ONLY' → log to console instead of sending.
"""
import logging
import os
from pathlib import Path
from typing import Optional

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SENDER_FROM = os.getenv("EMAIL_FROM", "Viet Dataverse <onboarding@resend.dev>")

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


class EmailError(Exception):
    pass


def _is_dev_mode() -> bool:
    return (not RESEND_API_KEY) or RESEND_API_KEY == "DEV_MODE_LOG_ONLY"


def send_email(
    to: str,
    subject: str,
    template: str,
    ctx: dict,
    reply_to: Optional[str] = None,
) -> dict:
    """Render template + send via Resend. In dev mode, log to console.

    Args:
        to: recipient email
        subject: email subject line
        template: template name (without .html), e.g. 'verify'
        ctx: variables for Jinja2 render
        reply_to: optional Reply-To header
    """
    try:
        tmpl = _jinja_env.get_template(f"{template}.html")
        html = tmpl.render(**ctx)
    except Exception as e:
        raise EmailError(f"Template render failed for '{template}': {e}")

    if _is_dev_mode():
        logger.info(
            f"[EMAIL DEV MODE]\n  to: {to}\n  subject: {subject}\n  template: {template}\n  "
            f"html_preview: {html[:300]}..."
        )
        return {"id": "dev-mode", "to": to, "template": template}

    payload = {
        "from": SENDER_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        resp = requests.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )
    except requests.RequestException as e:
        raise EmailError(f"Resend API request failed: {e}")

    if resp.status_code >= 400:
        raise EmailError(f"Resend API {resp.status_code}: {resp.text[:200]}")

    return resp.json()
