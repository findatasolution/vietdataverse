"""Student OTP delivery — regression for 2026-09-30.

The OTP went through a Gmail SMTP login whose app password had been rejected
since 2026-09-09, and the router echoed the raw `535 ... BadCredentials` text to
students. `deliver_otp` must report failure as False (never raise, never claim
success), so the router can return a generic 503 and release the rate-limit slot.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "be"))

from routers.student_verify import OTP_SEND_FAILED_DETAIL, deliver_otp  # noqa: E402
from services.email_service import EmailError  # noqa: E402


def test_sent_mail_is_success():
    calls = []

    def send(**kw):
        calls.append(kw)
        return {"id": "x", "sent": True}

    assert deliver_otp("a@st.ueh.edu.vn", "123456", send=send) is True
    assert calls[0]["template"] == "student_otp"
    assert calls[0]["ctx"]["otp_code"] == "123456"


def test_dev_mode_is_failure_not_success():
    # email_service returns sent=False when RESEND_API_KEY is unset: the mail
    # was dropped, and the student would wait for a code that never comes.
    assert deliver_otp("a@st.ueh.edu.vn", "1", send=lambda **kw: {"sent": False}) is False


def test_provider_error_is_failure_and_does_not_raise():
    def send(**kw):
        raise EmailError("Resend API 403: domain not verified")

    assert deliver_otp("a@st.ueh.edu.vn", "1", send=send) is False


def test_user_facing_detail_carries_no_provider_text():
    for leak in ("535", "smtp", "gmail", "Resend", "http"):
        assert leak.lower() not in OTP_SEND_FAILED_DETAIL.lower()


def test_template_renders_the_code():
    import services.email_service as es
    html = es._jinja_env.get_template("student_otp.html").render(otp_code="987654", ttl_minutes=10)
    assert "987654" in html and "10 phút" in html
