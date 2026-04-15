from pydantic import BaseModel, EmailStr, Field
from datetime import date, datetime
from typing import Optional, List

# -------------------------
# AUTH
# -------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    phone: str
    security_question: str
    security_answer: str
    dob: date

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class SendOtpRequest(BaseModel):
    phone: str

class RegisterWithOtpRequest(BaseModel):
    otp: str
    email: EmailStr
    password: str
    phone: str
    security_question: str
    security_answer: str
    dob: date

class PasswordResetRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class TokenResponse(BaseModel):
    access_token: str
    role: str

class MessageResponse(BaseModel):
    msg: str

# -------------------------
# TRANSACTION – FIXED
# -------------------------
class TransactionRequest(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: str  # "debit" or "credit"
    receiver_id: Optional[int] = None
    ip_address: str
    device_id: str
    location: str
    channel: str
    transaction_duration: float = Field(gt=0)

class TransactionResponse(BaseModel):
    transaction_id: int
    fraud_probability: float
    risk_level: str          # low / medium / high
    model_version: str
    is_fraud: bool
    reasons: List[str]

class TransactionDetailResponse(BaseModel):
    transaction_id: int
    amount: float
    account_balance: float
    transaction_duration: float
    customer_age: int
    location: str
    channel: str
    login_attempts: int
    fraud_score: float
    is_fraud: bool
    reasons: List[str]
    created_at: str
    transaction_type: str
    receiver_id: Optional[int]
    ip_address: str
    device_id: str
    model_version: str

# -------------------------
# ADMIN
# -------------------------
class AdminTransactionRequest(BaseModel):
    user_id: int
    amount: float
    transaction_duration: float
    location: str
    channel: str

class UpdateBalanceRequest(BaseModel):
    amount: float

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    phone: str
    account_balance: float
    role: str
    is_verified: bool
    is_blocked: bool

class DashboardResponse(BaseModel):
    total_users: int
    total_transactions: int

class BalanceUpdateResponse(BaseModel):
    new_balance: float

class AdminTransactionResponse(BaseModel):
    msg: str

# -------------------------
# ANALYTICS
# -------------------------
class FraudRateResponse(BaseModel):
    total: int
    fraud: int
    rate: float

class FraudLogItem(BaseModel):
    user_id: int
    amount: float
    location: str
    fraud_score: float
    action_taken: str
    reasons: str
    created_at: str

class OTPLogItem(BaseModel):
    user_id: int
    otp_type: str
    status: str
    attempts: int
    created_at: str

class FraudLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[FraudLogItem]

class OtpLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[OTPLogItem]

class FraudTrendResponse(BaseModel):
    date: str
    fraud_count: int

# -------------------------
# AUDIT LOGS (new)
# -------------------------
class AuditLogItem(BaseModel):
    id: int
    admin_id: int
    action: str
    target_user_id: int
    details: str
    created_at: str

class AuditLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[AuditLogItem]