from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session
import time

from app.core.database import get_db
from app.schemas.auth import *
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

otp_request_log: dict[str, list[float]] = {}


def check_otp_rate_limit(ip: str):
    now = time.time()
    otp_request_log.setdefault(ip, [])
    otp_request_log[ip] = [t for t in otp_request_log[ip] if now - t < 60]
    if len(otp_request_log[ip]) >= 5:
        from fastapi import HTTPException
        raise HTTPException(429, "Too many OTP requests. Please wait a minute.")
    otp_request_log[ip].append(now)


@router.post("/send-register-otp", response_model=MessageResponse)
def send_register_otp(data: SendOtpRequest, background: BackgroundTasks,
                      request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host
    check_otp_rate_limit(client_ip)
    auth_service.send_registration_otp(data.phone, db, background)
    return {"msg": "OTP sent"}


@router.post("/register", response_model=MessageResponse)
def register(data: RegisterWithOtpRequest, background: BackgroundTasks,
             db: Session = Depends(get_db)):
    auth_service.register_user(
        data.phone, data.otp, data.email, data.password,
         data.dob,
        db, background
    )
    return {"msg": "Registered successfully. Check your email to activate your account."}


@router.get("/activate", response_model=MessageResponse)
def activate(token: str, db: Session = Depends(get_db)):
    msg = auth_service.activate_account(token, db)
    return {"msg": msg}


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return auth_service.login_user(data.email, data.password, db)


@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(data: PasswordResetRequest, background: BackgroundTasks,
                          db: Session = Depends(get_db)):
    auth_service.request_password_reset_service(data.email, db, background)
    return {"msg": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    auth_service.reset_password_service(data.token, data.new_password, db)
    return {"msg": "Password updated successfully."}