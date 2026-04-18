from pydantic import BaseModel, EmailStr, constr
from datetime import date

PhoneStr = constr(pattern=r"^\+\d{10,15}$")
PasswordStr = constr(min_length=6, max_length=128)


class SendOtpRequest(BaseModel):
    name: str
    phone: PhoneStr
    email: EmailStr


class RegisterWithOtpRequest(BaseModel):
    name: str
    phone: PhoneStr
    email: EmailStr
    otp: str
    password: PasswordStr
    dob: date


class LoginRequest(BaseModel):
    email: EmailStr
    password: PasswordStr


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