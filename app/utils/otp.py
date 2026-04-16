import random
from datetime import datetime, timedelta
from fastapi import HTTPException
from app.core.security import hash_text, verify_text


def generate_otp():
    return str(random.randint(100000, 999999))


def create_otp_record(user):
    if user.last_otp_request:
        elapsed = (datetime.utcnow() - user.last_otp_request).total_seconds()
        if elapsed < 30:
            raise HTTPException(status_code=429, detail="Wait before requesting another OTP")

    otp = generate_otp()

    user.otp_hash = hash_text(otp)
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=5)
    user.otp_attempts = 0
    user.last_otp_request = datetime.utcnow()

    return otp


def verify_otp(user, otp: str):
    if not user.otp_hash:
        return False, "No OTP generated"

    if datetime.utcnow() > user.otp_expiry:
        return False, "OTP expired"

    if user.otp_attempts >= 5:
        return False, "Too many attempts"

    if not verify_text(otp, user.otp_hash):
        user.otp_attempts += 1
        return False, "Invalid OTP"

    user.otp_hash = None
    user.otp_expiry = None
    user.otp_attempts = 0

    return True, "OTP verified"