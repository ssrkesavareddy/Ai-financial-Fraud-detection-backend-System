from pydantic import BaseModel, EmailStr, Field,  constr
from typing import List
from datetime import date



PhoneStr = constr(pattern=r"^\+\d{10,15}$")

class AdminCreateUser(BaseModel):
    email: EmailStr
    password: str
    phone: PhoneStr
    dob: date


class AdminTransactionRequest(BaseModel):
    user_id: int
    amount: float = Field(gt=0)
    transaction_duration: float = Field(gt=0)
    location: str
    channel: str


class UpdateBalanceRequest(BaseModel):
    amount: float = Field(..., description="Positive to add, negative to deduct. Cannot be 0.")


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