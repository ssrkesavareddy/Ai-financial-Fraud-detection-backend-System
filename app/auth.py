from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from app.schemas import (
    RegisterRequest, LoginRequest, SendOtpRequest, RegisterWithOtpRequest,
    PasswordResetRequest, ResetPasswordRequest, TokenResponse
)
import time
from app.schemas import MessageResponse, TokenResponse
from app.database import get_db
from app.models import User, OTPLog
from app.config import BASE_URL
import re
from app.security import (
    hash_password,
    verify_password,
    create_token,
    hash_text,
    create_activation_token,
    create_reset_token
)
from app.utils.email import send_activation_email, send_password_reset_email
from app.utils.sms import send_sms
from app.utils.sms_templates import registration_otp_sms, registration_success_sms
from app.utils.otp import create_otp_record, verify_otp
from app.config import SECURITY_QUESTIONS, SECRET_KEY
from jose import jwt

router = APIRouter()

# -------- IN‑MEMORY OTP RATE LIMITER --------
otp_request_log = {}

def check_otp_rate_limit(ip: str):
    now = time.time()
    if ip not in otp_request_log:
        otp_request_log[ip] = []
    # Keep only requests from the last 60 seconds
    otp_request_log[ip] = [t for t in otp_request_log[ip] if now - t < 60]
    if len(otp_request_log[ip]) >= 5:
        raise HTTPException(429, "Too many OTP requests. Please wait a minute.")
    otp_request_log[ip].append(now)


# -------- VALIDATION --------
def validate_phone(phone: str):
    if not phone.startswith("+") or len(phone) < 10:
        raise HTTPException(400, "Invalid phone number")


def validate_password(password: str):
    if not re.match(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$", password):
        raise HTTPException(400, "Password must be 8+ chars with letters and numbers")


# ---------------- SEND OTP ----------------
@router.post("/send-register-otp", response_model=MessageResponse)
def send_register_otp(
    data: SendOtpRequest,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    client_ip = request.client.host
    check_otp_rate_limit(client_ip)

    validate_phone(data.phone)

    user = db.query(User).filter(User.phone == data.phone).first()

    if user and user.email:
        raise HTTPException(400, "Phone already registered")

    if not user:
        user = User(phone=data.phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    otp = create_otp_record(user)
    db.commit()

    background.add_task(send_sms, data.phone, registration_otp_sms(otp))

    db.add(OTPLog(user_id=user.id, otp_type="register", status="sent"))
    db.commit()

    return {"msg": "OTP sent"}


# ---------------- REGISTER ----------------
@router.post("/register", response_model=MessageResponse)
def register(
    data: RegisterWithOtpRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    validate_password(data.password)

    user = db.query(User).filter(User.phone == data.phone).first()

    if not user:
        raise HTTPException(400, "OTP not requested")

    ok, msg = verify_otp(user, data.otp)

    if not ok:
        db.add(OTPLog(user_id=user.id, otp_type="register", status="failed", attempts=user.otp_attempts))
        db.commit()
        raise HTTPException(400, msg)

    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already exists")

    if data.security_question not in SECURITY_QUESTIONS:
        raise HTTPException(400, "Invalid security question")

    user.email = data.email
    user.password = hash_password(data.password)
    user.security_question = data.security_question
    user.security_answer = hash_text(data.security_answer)
    user.dob = data.dob
    user.is_verified = False

    db.commit()

    token = create_activation_token(user.email)
    link = f"{BASE_URL}/auth/activate?token={token}"

    background.add_task(send_activation_email, user.email, link)
    background.add_task(send_sms, user.phone, registration_success_sms())

    return {"msg": "Registered. Check email to activate"}


# ---------------- ACTIVATE ----------------
@router.get("/activate", response_model=MessageResponse)
def activate(token: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

        if payload.get("type") != "activation":
            raise HTTPException(400, "Invalid token")

        email = payload.get("sub")

    except Exception:
        raise HTTPException(400, "Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()

    if not user:
        raise HTTPException(404, "User not found")

    user.is_verified = True
    db.commit()

    return {"msg": "Account activated"}


# ---------------- LOGIN ----------------
@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(401, "Invalid credentials")

    if user.login_attempts >= 5:
        raise HTTPException(429, "Too many attempts")

    if not verify_password(data.password, user.password):
        user.login_attempts += 1
        db.commit()
        raise HTTPException(401, "Invalid credentials")

    if not user.is_verified:
        raise HTTPException(403, "Activate account first")

    if user.is_blocked:
        raise HTTPException(403, "Account blocked")

    user.login_attempts = 0
    db.commit()

    token = create_token({
        "sub": user.email,
        "role": user.role
    })

    return {
        "access_token": token,
        "role": user.role
    }


# ---------------- REQUEST PASSWORD RESET ----------------
@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(
    data: PasswordResetRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == data.email).first()

    if not user:
        raise HTTPException(404, "User not found")

    token = create_reset_token(user.email)
    link = f"{BASE_URL}/auth/reset-password?token={token}"

    background.add_task(send_password_reset_email, user.email, link)

    return {"msg": "Reset link sent"}


# ---------------- RESET PASSWORD (CONFIRM) ----------------
@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "reset":
            raise HTTPException(400, "Invalid token type")
        email = payload.get("sub")
    except Exception:
        raise HTTPException(400, "Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")

    validate_password(data.new_password)
    user.password = hash_password(data.new_password)
    db.commit()

    return {"msg": "Password updated successfully"}