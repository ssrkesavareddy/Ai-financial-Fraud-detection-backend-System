import requests
import os
import logging

logger = logging.getLogger(__name__)


def _get_config():
    api_key = os.getenv("BREVO_API_KEY")
    email_from = os.getenv("EMAIL_FROM")
    if not api_key or not email_from:
        raise RuntimeError("Email config missing: BREVO_API_KEY and EMAIL_FROM must be set.")
    return api_key, email_from


def send_email(to_email: str, subject: str, html_content: str):
    try:
        api_key, email_from = _get_config()
    except RuntimeError as e:
        logger.error(f"[EMAIL] Config error: {e}")
        return

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "sender": {"email": email_from},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code not in (200, 201):
            logger.error(f"[EMAIL] Failed to send to {to_email}: {res.status_code} {res.text}")
        else:
            logger.info(f"[EMAIL] Sent '{subject}' to {to_email}")
    except Exception as e:
        logger.error(f"[EMAIL] Exception sending to {to_email}: {e}")


def send_fraud_email(email: str, amount: float, location: str, prob: float, reasons: list[str]):
    reason_html = "".join(f"<li>{r}</li>" for r in reasons)
    html = f"""
    <html><body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
    <div style="max-width:600px;margin:auto;padding:20px;">
      <div style="background:#111827;border-radius:12px;padding:25px;color:white;">
        <h2 style="color:#ef4444;">🚨 Fraud Alert</h2>
        <p style="color:#9ca3af;">Suspicious activity detected on your account.</p>
        <div style="margin:20px 0;padding:15px;background:#1f2937;border-radius:8px;">
          <p><b>Amount:</b> ₹{amount}</p>
          <p><b>Location:</b> {location}</p>
          <p><b>Risk Score:</b> {prob:.2f}</p>
        </div>
        <h3>Reasons:</h3>
        <ul style="color:#d1d5db;">{reason_html}</ul>
        <div style="margin-top:20px;padding:15px;background:#7f1d1d;border-radius:8px;">
          <b>Account Status: BLOCKED</b>
        </div>
        <p style="margin-top:20px;color:#9ca3af;">Please contact support to recover your account.</p>
      </div>
      <p style="text-align:center;color:#6b7280;font-size:12px;">FraudGuard AI © 2026</p>
    </div>
    </body></html>
    """
    send_email(email, "🚨 Fraud Alert — Immediate Action Required", html)


def send_activation_email(email: str, activation_link: str):
    html = f"""
    <html><body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
    <div style="max-width:600px;margin:auto;padding:20px;">
      <div style="background:#111827;border-radius:12px;padding:25px;color:white;">
        <h2 style="color:#22c55e;">✅ Activate Your Account</h2>
        <p style="color:#9ca3af;">Welcome! Please activate your account to get started.</p>
        <div style="text-align:center;margin:30px 0;">
          <a href="{activation_link}"
             style="background:#22c55e;color:white;padding:12px 24px;
                    text-decoration:none;border-radius:8px;font-weight:bold;">
            Activate Account
          </a>
        </div>
        <p style="color:#9ca3af;font-size:14px;">This link expires in 8 hours.</p>
        <p style="word-break:break-all;color:#60a5fa;font-size:12px;">{activation_link}</p>
      </div>
      <p style="text-align:center;color:#6b7280;font-size:12px;">FraudGuard AI © 2026</p>
    </div>
    </body></html>
    """
    send_email(email, "Activate Your Account", html)


def send_password_reset_email(email: str, reset_link: str):
    html = f"""
    <html><body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
    <div style="max-width:600px;margin:auto;padding:20px;">
      <div style="background:#111827;border-radius:12px;padding:25px;color:white;">
        <h2 style="color:#f59e0b;">🔐 Password Reset Request</h2>
        <p style="color:#9ca3af;">We received a request to reset your password.</p>
        <div style="text-align:center;margin:30px 0;">
          <a href="{reset_link}"
             style="background:#f59e0b;color:black;padding:12px 24px;
                    text-decoration:none;border-radius:8px;font-weight:bold;">
            Reset Password
          </a>
        </div>
        <p style="font-size:12px;color:#9ca3af;">This link expires in 8 hours.</p>
        <p style="word-break:break-all;color:#60a5fa;font-size:12px;">{reset_link}</p>
      </div>
      <p style="text-align:center;color:#6b7280;font-size:12px;">FraudGuard AI © 2026</p>
    </div>
    </body></html>
    """
    send_email(email, "Reset Your Password", html)