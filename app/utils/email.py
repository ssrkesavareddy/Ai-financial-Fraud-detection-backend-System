import requests
import os
import logging
import time

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

def _get_config():
    api_key = os.getenv("BREVO_API_KEY")
    email_from = os.getenv("EMAIL_FROM")

    if not api_key or not email_from:
        raise RuntimeError("Missing BREVO_API_KEY or EMAIL_FROM")

    return api_key, email_from


# ─────────────────────────────────────────────
# BASE SEND (NON-CRITICAL)
# ─────────────────────────────────────────────

def send_email(to_email: str, subject: str, html_content: str) -> bool:
    try:
        api_key, email_from = _get_config()
    except RuntimeError as e:
        logger.error(f"[EMAIL] Config error: {e}")
        return False

    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json"
    }

    payload = {
        "sender": {"email": email_from},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)

        if res.status_code in (200, 201):
            logger.info(f"[EMAIL] Sent '{subject}' to {to_email}")
            return True
        else:
            logger.error(f"[EMAIL] Failed ({res.status_code}) → {res.text}")
            return False

    except Exception as e:
        logger.error(f"[EMAIL] Exception: {e}")
        return False


# ─────────────────────────────────────────────
# RETRY SEND (CRITICAL)
# ─────────────────────────────────────────────

_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 10]


def send_email_with_retry(to_email: str, subject: str, html_content: str) -> bool:
    for attempt in range(1, _MAX_RETRIES + 1):
        success = send_email(to_email, subject, html_content)

        if success:
            return True

        if attempt < _MAX_RETRIES:
            logger.warning(f"[EMAIL] Retry {attempt} failed, retrying...")
            time.sleep(_RETRY_DELAYS[attempt - 1])

    logger.error(f"[EMAIL] All retries failed for {to_email}")
    return False


# ─────────────────────────────────────────────
# OTP EMAILS (CRITICAL)
# ─────────────────────────────────────────────

def send_registration_otp_email(email: str, name: str, otp: str) -> bool:
    html = f"""
    <html><body>
    <h2>🔐 Registration OTP</h2>
    <p>Hello {name},</p>
    <h1>{otp}</h1>
    <p>Valid for 5 minutes. Do not share.</p>
    </body></html>
    """

    return send_email_with_retry(email, "FraudGuard OTP", html)


def send_unblock_otp_email(email: str, name: str, otp: str) -> bool:
    html = f"""
    <html><body>
    <h2>🔓 Unblock OTP</h2>
    <p>Hello {name},</p>
    <h1>{otp}</h1>
    <p>Valid for 5 minutes. Do not share.</p>
    </body></html>
    """

    return send_email_with_retry(email, "Account Unblock OTP", html)


# ─────────────────────────────────────────────
# NON-CRITICAL EMAILS
# ─────────────────────────────────────────────

def send_registration_success_email(email: str, name: str):
    html = f"""
    <html><body>
    <h2>✅ Account Created</h2>
    <p>Welcome {name}, your account is ready.</p>
    </body></html>
    """
    send_email(email, "Account Created", html)


def send_activation_email(email: str, activation_link: str):
    html = f"""
    <html><body>
    <h2>Activate Account</h2>
    <a href="{activation_link}">Activate</a>
    </body></html>
    """
    send_email(email, "Activate Account", html)


def send_password_reset_email(email: str, reset_link: str):
    html = f"""
    <html><body>
    <h2>Password Reset</h2>
    <a href="{reset_link}">Reset Password</a>
    </body></html>
    """
    send_email(email, "Reset Password", html)


def send_fraud_email(email: str, amount: float, location: str, prob: float, reasons: list[str]):
    reason_html = "".join(f"<li>{r}</li>" for r in reasons)

    html = f"""
    <html><body>
    <h2>🚨 Fraud Alert</h2>
    <p>Amount: ₹{amount}</p>
    <p>Location: {location}</p>
    <p>Risk: {prob}</p>
    <ul>{reason_html}</ul>
    </body></html>
    """

    send_email(email, "Fraud Alert", html)

# ── Admin activate / deactivate notification emails ─────────────────────────

def send_account_activated_email(email: str, name: str):
    """Sent when an admin activates a user's account."""
    html = f"""
    <html><body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
    <div style="max-width:600px;margin:auto;padding:20px;">
      <div style="background:#111827;border-radius:12px;padding:25px;color:white;">
        <h2 style="color:#22c55e;">✅ Account Activated</h2>
        <p style="color:#9ca3af;">Hello {name},</p>
        <p style="color:#9ca3af;">
          Your FraudGuard account has been <strong style="color:#22c55e;">activated</strong>
          by an administrator. You can now log in and use all features.
        </p>
      </div>
      <p style="text-align:center;color:#6b7280;font-size:12px;">FraudGuard AI © 2026</p>
    </div>
    </body></html>
    """
    send_email(email, "✅ Your Account Has Been Activated — FraudGuard", html)


def send_account_deactivated_email(email: str, name: str):
    """Sent when an admin deactivates a user's account."""
    html = f"""
    <html><body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
    <div style="max-width:600px;margin:auto;padding:20px;">
      <div style="background:#111827;border-radius:12px;padding:25px;color:white;">
        <h2 style="color:#ef4444;">⛔ Account Deactivated</h2>
        <p style="color:#9ca3af;">Hello {name},</p>
        <p style="color:#9ca3af;">
          Your FraudGuard account has been <strong style="color:#ef4444;">deactivated</strong>
          by an administrator. You will not be able to log in until reactivated.
        </p>
        <p style="color:#9ca3af;">
          If you believe this is a mistake, please contact our support team.
        </p>
      </div>
      <p style="text-align:center;color:#6b7280;font-size:12px;">FraudGuard AI © 2026</p>
    </div>
    </body></html>
    """
    send_email(email, "⛔ Your Account Has Been Deactivated — FraudGuard", html)