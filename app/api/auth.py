from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import time

from app.core.database import get_db
from app.schemas.auth import (
    SendOtpRequest,
    RegisterWithOtpRequest,
    PasswordResetRequest,
    ResetPasswordRequest,
    TokenResponse,
    MessageResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

# ─────────────────────────────────────────────
# SIMPLE IN-MEMORY RATE LIMITER
# ─────────────────────────────────────────────
_otp_request_log: dict[str, list[float]] = {}


def _check_otp_rate_limit(ip: str):
    now = time.time()
    _otp_request_log.setdefault(ip, [])
    _otp_request_log[ip] = [t for t in _otp_request_log[ip] if now - t < 60]
    if len(_otp_request_log[ip]) >= 5:
        raise HTTPException(429, "Too many OTP requests. Wait 1 minute.")
    _otp_request_log[ip].append(now)


# ─────────────────────────────────────────────
# SEND OTP (STEP 1)
# OTP is sent to the user's email address.
# Verifying this OTP during registration IS the email verification —
# no separate activation link is required.
# ─────────────────────────────────────────────
@router.post("/send-register-otp", response_model=MessageResponse)
def send_register_otp(
    request: Request,
    data: SendOtpRequest,
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else "unknown"
    _check_otp_rate_limit(ip)
    return auth_service.send_registration_otp(data.name, data.phone, data.email, db)


# ─────────────────────────────────────────────
# REGISTER + VERIFY OTP (STEP 2)
# On correct OTP → account is immediately verified and active.
# No activation link email is sent.
# ─────────────────────────────────────────────
@router.post("/register", response_model=MessageResponse)
def register(
    data: RegisterWithOtpRequest,
    db: Session = Depends(get_db),
):
    """
    Verifies the OTP and completes registration in one step.
    A correct OTP proves email ownership — is_verified is set to True immediately.
    """
    return auth_service.register_user(
        data.name, data.phone, data.otp,
        data.email, data.password, data.dob,
        db,
    )


# NOTE: /auth/activate has been removed.
# The OTP sent to the user's email during registration serves as email verification.
# Clicking a separate link is no longer required.


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    return auth_service.login_user(form_data.username, form_data.password, db)


# ─────────────────────────────────────────────
# PASSWORD RESET
# ─────────────────────────────────────────────
@router.post("/request-password-reset", response_model=MessageResponse)
def request_password_reset(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    auth_service.request_password_reset_service(data.email, db)
    return {"msg": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    return auth_service.reset_password_service(data.token, data.new_password, db)