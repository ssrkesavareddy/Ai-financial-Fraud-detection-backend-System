from sqlalchemy.orm import Session
from fastapi import HTTPException
from jose import jwt, JWTError
from datetime import datetime, timedelta
import re

from app.models.user import User
from app.models.fraud_log import OTPLog
from app.core.config import SECRET_KEY, BASE_URL
from app.core.security import (
    hash_password, verify_password,
    create_token, create_reset_token,
)
from app.utils.email import (
    send_registration_otp_email,
    send_registration_success_email,
    send_password_reset_email,
)
from app.utils.otp import create_otp_record, verify_otp
from app.utils.id_generator import generate_user_public_id


# ─────────────────────────────────────────────
# VALIDATORS
# ─────────────────────────────────────────────

def validate_phone(phone: str):
    if not re.match(r"^\+\d{10,15}$", phone):
        raise HTTPException(400, "Invalid phone number")


def validate_password(password: str):
    if not re.match(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$", password):
        raise HTTPException(400, "Password must be 8+ characters with letters and numbers.")


# ─────────────────────────────────────────────
# STEP 1 — SEND REGISTRATION OTP
# ─────────────────────────────────────────────

def send_registration_otp(name: str, phone: str, email: str, db: Session):
    validate_phone(phone)

    existing_by_phone = db.query(User).filter(User.phone == phone).first()
    existing_by_email = db.query(User).filter(User.email == email).first()

    if existing_by_email:
        raise HTTPException(400, "Email already registered")

    if not existing_by_phone:
        user = User(
            name=name,
            phone=phone,
            public_id=generate_user_public_id(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user = existing_by_phone

    if user.last_otp_request:
        if datetime.utcnow() - user.last_otp_request < timedelta(seconds=60):
            raise HTTPException(429, "Wait before requesting OTP again")

    otp = create_otp_record(user)
    user.last_otp_request = datetime.utcnow()

    success = send_registration_otp_email(email, name, otp)
    if not success:
        raise HTTPException(500, "Failed to send OTP")

    db.add(OTPLog(user_id=user.id, otp_type="register", status="sent"))
    db.commit()

    return {"msg": "OTP sent to your email. Enter it to complete registration."}


# ─────────────────────────────────────────────
# STEP 2 — COMPLETE REGISTRATION
# No activation link is needed. The OTP itself IS the email verification.
# Account is set to is_verified=True immediately on correct OTP.
# ─────────────────────────────────────────────

def register_user(
    name: str, phone: str, otp: str,
    email: str, password: str, dob,
    db: Session,
):
    validate_password(password)

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(400, "OTP not requested for this phone number")

    if db.query(User).filter(User.email == email, User.id != user.id).first():
        raise HTTPException(400, "Email already registered")

    ok, msg = verify_otp(user, otp)
    if not ok:
        db.add(OTPLog(user_id=user.id, otp_type="register", status="failed", attempts=user.otp_attempts))
        db.commit()
        raise HTTPException(400, msg)

    user.name       = name
    user.email      = email
    user.password   = hash_password(password)
    user.dob        = dob
    # OTP verified = email confirmed. Mark as verified immediately.
    # No activation link email is sent — the OTP was the proof of email ownership.
    user.is_verified = True
    user.is_active   = True

    db.add(OTPLog(user_id=user.id, otp_type="register", status="verified"))
    db.commit()

    send_registration_success_email(user.email, user.name)

    return {"msg": "Registration successful. Your account is now active — you can log in."}


# ─────────────────────────────────────────────
# LOGIN
# Checks (in order):
#   1. User exists
#   2. Rate-limit on failed attempts
#   3. Password correct
#   4. is_verified  — OTP was completed during registration
#   5. is_active    — admin has not deactivated the account
# Blocked (self-blocked) users CAN still login; they just can't transact.
# ─────────────────────────────────────────────

def login_user(email: str, password: str, db: Session):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(401, "Invalid email or password")

    now = datetime.utcnow()

    if user.last_login_attempt_reset:
        if (now - user.last_login_attempt_reset) > timedelta(minutes=15):
            user.login_attempts = 0

    if user.login_attempts >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again later.")

    if not verify_password(password, user.password):
        user.login_attempts += 1
        user.last_login_attempt_reset = now
        db.commit()
        raise HTTPException(401, "Invalid email or password")

    if not user.is_verified:
        raise HTTPException(403, "Account not yet verified. Complete OTP registration.")

    # Admin-deactivated accounts cannot login at all.
    if not user.is_active:
        raise HTTPException(
            403,
            "Your account has been deactivated by an administrator. "
            "Please contact support."
        )

    # Self-blocked users CAN login (they manage their block via /users/me/block).

    user.login_attempts = 0
    user.last_login_attempt_reset = now
    db.commit()

    token = create_token({"sub": user.email, "role": user.role.lower()})
    return {"access_token": token, "role": user.role}


# ─────────────────────────────────────────────
# PASSWORD RESET
# ─────────────────────────────────────────────

def request_password_reset_service(email: str, db: Session):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return  # silent — never leak whether email exists

    token = create_reset_token(user.email)
    link  = f"{BASE_URL}/auth/reset-password?token={token}"

    send_password_reset_email(user.email, link)

    db.add(OTPLog(user_id=user.id, otp_type="reset", status="sent"))
    db.commit()


def reset_password_service(token: str, new_password: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(400, "Invalid or expired token")

    if payload.get("type") != "reset":
        raise HTTPException(400, "Invalid token type")

    email = payload.get("sub")
    user  = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")

    validate_password(new_password)
    user.password = hash_password(new_password)
    db.commit()

    return {"msg": "Password reset successful"}