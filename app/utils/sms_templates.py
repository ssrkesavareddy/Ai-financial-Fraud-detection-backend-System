def registration_otp_sms(otp):
    return f"🔐 Your registration OTP is {otp}. Valid for 5 minutes."


def recovery_otp_sms(otp):
    return f"🔐 Your recovery OTP is {otp}. Valid for 5 minutes."


def registration_success_sms():
    return "✅ Your account has been created successfully."


def fraud_sms(amount, location):
    return f"🚨 Fraud Alert: Suspicious transaction of ₹{amount} detected from {location}."