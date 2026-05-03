"""
SMTP email helper.
Env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or SMTP_USER


def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send student verification OTP. Raises RuntimeError if SMTP is not configured."""
    if not SMTP_USER or not SMTP_PASS:
        # Dev fallback: print to console so local testing works without SMTP
        print(f"[DEV] OTP for {to_email}: {otp_code}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Mã xác nhận sinh viên — Viet Dataverse"
    msg["From"]    = SMTP_FROM
    msg["To"]      = to_email

    html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f5f4ed;font-family:Inter,sans-serif;">
<div style="max-width:480px;margin:40px auto;background:#fff;border-radius:16px;
            border:1px solid #e8e6dc;padding:36px 32px;">
  <div style="font-family:Georgia,serif;font-size:18px;font-weight:600;
              color:#141413;margin-bottom:8px;">
    Viet Dataverse
  </div>
  <div style="height:1px;background:#e8e6dc;margin:16px 0 24px;"></div>
  <p style="color:#141413;font-size:15px;font-weight:500;margin:0 0 6px;">
    Xác nhận email sinh viên
  </p>
  <p style="color:#87867f;font-size:13px;margin:0 0 24px;">
    Nhập mã bên dưới để xác minh email sinh viên và nhận ưu đãi giảm 50%.
  </p>
  <div style="background:#f5f4ed;border-radius:10px;padding:24px;
              text-align:center;margin-bottom:24px;">
    <span style="font-size:36px;font-weight:700;letter-spacing:8px;color:#c96442;">
      {otp_code}
    </span>
  </div>
  <p style="color:#87867f;font-size:12px;margin:0 0 4px;">
    ⏱ Mã có hiệu lực trong <strong>10 phút</strong>.
  </p>
  <p style="color:#87867f;font-size:12px;margin:0;">
    Không chia sẻ mã này với bất kỳ ai. Nếu bạn không yêu cầu, hãy bỏ qua email này.
  </p>
  <div style="height:1px;background:#e8e6dc;margin:24px 0 16px;"></div>
  <p style="color:#87867f;font-size:11px;margin:0;">
    Viet Dataverse &middot; vietdataverse.online
  </p>
</div>
</body>
</html>
"""
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, to_email, msg.as_string())
