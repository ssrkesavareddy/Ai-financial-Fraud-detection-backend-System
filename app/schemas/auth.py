from pydantic import BaseModel, EmailStr, constr
from datetime import date

# 🔒 reusable types
PhoneStr = constr(pattern=r"^\+\d{10,15}$")
PasswordStr = constr(min_length=6, max_length=128)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: PasswordStr
    phone: PhoneStr

    dob: date


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordStr


class SendOtpRequest(BaseModel):
    phone: PhoneStr


class RegisterWithOtpRequest(BaseModel):
    otp: str
    email: EmailStr
    password: PasswordStr
    phone: PhoneStr

    dob: date


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: PasswordStr


class TokenResponse(BaseModel):
    access_token: str
    role: str


class MessageResponse(BaseModel):
    msg: str