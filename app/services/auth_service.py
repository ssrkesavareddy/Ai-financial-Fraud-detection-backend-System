from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
from jose import jwt, JWTError
from datetime import datetime
import re

from app.models.user import User
from app.models.fraud_log import OTPLog
from app.core.config import SECRET_KEY, BASE_URL
from app.core.security import hash_password, verify_password, hash_text, create_token, create_activation_token, \
    create_reset_token
from app.utils.email import send_activation_email, send_password_reset_email
from app.utils.sms import send_sms
from app.utils.sms_templates import registration_otp_sms, registration_success_sms
from app.utils.otp import create_otp_record, verify_otp
from datetime import datetime, timedelta

def validate_phone(phone: str):
    if not re.match(r"^\+\d{10,15}$", phone):
        raise HTTPException(400, "Invalid phone number")


def validate_password(password: str):
    if not re.match(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$", password):
        raise HTTPException(400, "Password must be 8+ characters with letters and numbers.")


def send_registration_otp(phone: str, db: Session, background: BackgroundTasks):
    validate_phone(phone)

    user = db.query(User).filter(User.phone == phone).first()

    if user and user.email:
        raise HTTPException(400, "Phone number is already registered.")

    if not user:
        user = User(phone=phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    otp = create_otp_record(user)
    db.commit()

    background.add_task(send_sms, phone, registration_otp_sms(otp))
    db.add(OTPLog(user_id=user.id, otp_type="register", status="sent"))
    db.commit()


def register_user(phone: str, otp: str, email: str, password: str,
                   dob,
                  db: Session, background: BackgroundTasks):
    validate_password(password)

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(400, "OTP not requested for this phone number.")

    if db.query(User).filter(User.email == email, User.id != user.id).first():
        raise HTTPException(400, "Email address is already registered.")



    ok, msg = verify_otp(user, otp)
    if not ok:
        db.add(OTPLog(user_id=user.id, otp_type="register", status="failed", attempts=user.otp_attempts))
        db.commit()
        raise HTTPException(400, msg)

    user.email = email
    user.password = hash_password(password)

    user.dob = dob
    user.is_verified = False

    db.commit()

    token = create_activation_token(user.email)
    link = f"{BASE_URL}/auth/activate?token={token}"
    background.add_task(send_activation_email, user.email, link)
    background.add_task(send_sms, user.phone, registration_success_sms())


def activate_account(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(400, "Invalid or expired activation token.")

    if payload.get("type") != "activation":
        raise HTTPException(400, "Wrong token type.")

    email = payload.get("sub")
    if not email:
        raise HTTPException(400, "Malformed token.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found.")

    if user.is_verified:
        return "Account is already activated."

    user.is_verified = True
    db.commit()
    return "Account activated successfully."


def login_user(email: str, password: str, db: Session):
    user = db.query(User).filter(User.email == email).first()

    INVALID = HTTPException(401, "Invalid email or password.")

    if not user:
        raise INVALID

    now = datetime.utcnow()

    # 🔁 Reset attempts after 15 minutes
    if user.last_login_attempt_reset:
        if (now - user.last_login_attempt_reset) > timedelta(minutes=15):
            user.login_attempts = 0

    # 🚫 Block if too many attempts
    if user.login_attempts >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again later.")

    # ❌ Wrong password
    if not verify_password(password, user.password):
        user.login_attempts += 1
        user.last_login_attempt_reset = now
        db.commit()
        raise INVALID

    # 🚫 Account checks
    if not user.is_verified:
        raise HTTPException(403, "Please activate your account first.")

    if user.is_blocked:
        raise HTTPException(403, "Account is blocked due to suspected fraud.")

    # ✅ Success
    user.login_attempts = 0
    user.last_login_attempt_reset = now
    db.commit()

    token = create_token({"sub": user.email, "role": user.role})
    return {"access_token": token, "role": user.role}


def request_password_reset_service(email: str, db: Session, background: BackgroundTasks):
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return

    token = create_reset_token(user.email)
    link = f"{BASE_URL}/auth/reset-password?token={token}"
    background.add_task(send_password_reset_email, user.email, link)


def reset_password_service(token: str, new_password: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(400, "Invalid or expired reset token.")

    if payload.get("type") != "reset":
        raise HTTPException(400, "Wrong token type.")

    email = payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found.")

    validate_password(new_password)
    user.password = hash_password(new_password)
    db.commit()