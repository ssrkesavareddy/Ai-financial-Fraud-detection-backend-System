import requests
import os

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM")
if not BREVO_API_KEY or not EMAIL_FROM:
    raise Exception("Email config missing")

def send_email(to_email: str, subject: str, html_content: str):
    url = "https://api.brevo.com/v3/smtp/email"

    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "sender": {"email": EMAIL_FROM},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }

    res = requests.post(url, headers=headers, json=data)

    # 🔥 FAIL SAFE (IMPORTANT)
    if res.status_code not in [200, 201]:
        raise Exception(f"Email failed: {res.text}")


# -------------------------
# FRAUD EMAIL
# -------------------------
def send_fraud_email(email, amount, location, prob, reasons):
    reason_html = "".join([f"<li>{r}</li>" for r in reasons])

    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
        <div style="max-width:600px;margin:auto;padding:20px;">

            <div style="background:#111827;border-radius:12px;padding:25px;color:white;">

                <h2 style="color:#ef4444;margin-bottom:10px;">
                    🚨 Fraud Alert
                </h2>

                <p style="color:#9ca3af;">
                    Suspicious activity detected on your account.
                </p>

                <div style="margin:20px 0;padding:15px;background:#1f2937;border-radius:8px;">
                    <p><b>Amount:</b> ₹{amount}</p>
                    <p><b>Location:</b> {location}</p>
                    <p><b>Risk Score:</b> {prob:.2f}</p>
                </div>

                <h3 style="margin-top:20px;">Reasons:</h3>
                <ul style="color:#d1d5db;">
                    {reason_html}
                </ul>

                <div style="margin-top:20px;padding:15px;background:#7f1d1d;border-radius:8px;">
                    <b>Account Status:</b> BLOCKED
                </div>

                <p style="margin-top:20px;color:#9ca3af;">
                    Please recover your account using OTP + security verification.
                </p>

            </div>

            <p style="text-align:center;color:#6b7280;margin-top:10px;font-size:12px;">
                Fraud Detection System © 2026
            </p>

        </div>
    </body>
    </html>
    """

    send_email(email, "🚨 Fraud Alert - Immediate Action Required", html)


def send_activation_email(email, activation_link):
    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
        <div style="max-width:600px;margin:auto;padding:20px;">

            <div style="background:#111827;border-radius:12px;padding:25px;color:white;">

                <h2 style="color:#22c55e;margin-bottom:10px;">
                    ✅ Activate Your Account
                </h2>

                <p style="color:#9ca3af;">
                    Welcome! Your account has been created successfully.
                </p>

                <p style="color:#9ca3af;">
                    Please activate your account to start using our services.
                </p>

                <div style="text-align:center;margin:30px 0;">
                    <a href="{activation_link}" 
                       style="
                       background:#22c55e;
                       color:white;
                       padding:12px 24px;
                       text-decoration:none;
                       border-radius:8px;
                       font-weight:bold;
                       display:inline-block;">
                       Activate Account
                    </a>
                </div>

                <p style="color:#9ca3af;font-size:14px;">
                    This link will expire in a few hours for security reasons.
                </p>

                <p style="color:#9ca3af;font-size:12px;margin-top:20px;">
                    If the button doesn't work, copy and paste this link:
                </p>

                <p style="word-break:break-all;color:#60a5fa;font-size:12px;">
                    {activation_link}
                </p>

            </div>

            <p style="text-align:center;color:#6b7280;margin-top:10px;font-size:12px;">
                Fraud Detection System © 2026
            </p>

        </div>
    </body>
    </html>
    """

    send_email(email, "Activate Your Account", html)


def send_password_reset_email(email, reset_link):
    html = f"""
    <html>
    <body style="margin:0;padding:0;background:#0f172a;font-family:Arial;">
        <div style="max-width:600px;margin:auto;padding:20px;">

            <div style="background:#111827;border-radius:12px;padding:25px;color:white;">

                <h2 style="color:#f59e0b;">🔐 Password Reset Request</h2>

                <p style="color:#9ca3af;">
                    We received a request to reset your password.
                </p>

                <div style="text-align:center;margin:30px 0;">
                    <a href="{reset_link}" 
                       style="
                       background:#f59e0b;
                       color:black;
                       padding:12px 24px;
                       text-decoration:none;
                       border-radius:8px;
                       font-weight:bold;">
                       Reset Password
                    </a>
                </div>

                <p style="font-size:12px;color:#9ca3af;">
                    This link expires in 8 hours.
                </p>

                <p style="word-break:break-all;color:#60a5fa;font-size:12px;">
                    {reset_link}
                </p>

            </div>

            <p style="text-align:center;color:#6b7280;font-size:12px;">
                Fraud Detection System © 2026
            </p>

        </div>
    </body>
    </html>
    """

    send_email(email, "Reset Your Password", html)