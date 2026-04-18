from pydantic import BaseModel, EmailStr, Field, constr
from typing import List
from datetime import date
from uuid import UUID

PhoneStr = constr(pattern=r"^\+\d{10,15}$")


class AdminCreateUser(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: PhoneStr
    dob: date


class AdminTransactionRequest(BaseModel):
    user_id: UUID   # ✅ FIXED
    amount: float = Field(gt=0)
    transaction_duration: float = Field(gt=0)
    location: str
    channel: str


class UpdateBalanceRequest(BaseModel):
    amount: float = Field(..., description="Positive to add, negative to deduct. Cannot be 0.")


class UserResponse(BaseModel):
    id: UUID   # ✅ FIXED
    public_id: str | None = None
    name: str
    email: EmailStr | None = None
    phone: str
    account_balance: float
    role: str
    is_verified: bool
    is_active: bool
    is_blocked: bool

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    total_users: int
    total_transactions: int


class BalanceUpdateResponse(BaseModel):
    new_balance: float


class AdminTransactionResponse(BaseModel):
    msg: str


class BulkTransactionItem(BaseModel):
    user_id: UUID   # ✅ FIXED
    amount: float = Field(gt=0)
    transaction_duration: float = Field(gt=0)
    location: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class BulkTransactionRequest(BaseModel):
    transactions: List[BulkTransactionItem] = Field(min_length=1, max_length=500)


class BulkTransactionResult(BaseModel):
    index: int
    user_id: UUID   # ✅ FIXED
    status: str
    detail: str


class BulkTransactionResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BulkTransactionResult]


class AuditLogItem(BaseModel):
    # BUG FIX (9): AuditLog primary key is UUID(as_uuid=True) in the ORM model.
    # Using `id: int` caused a Pydantic ValidationError on every audit-log response.
    id: UUID
    admin_id: UUID
    action: str
    target_user_id: UUID
    details: str
    created_at: str


class AuditLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[AuditLogItem]

# ── Bulk credit ───────────────────────────────────────────────────────────────

class BulkCreditItem(BaseModel):
    user_id: UUID
    amount: float = Field(gt=0)
    transaction_duration: float = Field(gt=0)
    location: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class BulkCreditRequest(BaseModel):
    transactions: List[BulkCreditItem] = Field(min_length=1, max_length=500)


class BulkCreditResult(BaseModel):
    index: int
    user_id: str
    public_id: str | None = None
    status: str
    detail: str


class BulkCreditResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BulkCreditResult]


# ── Bulk debit result (same shape, add public_id) ─────────────────────────────

class BulkDebitResult(BaseModel):
    index: int
    user_id: str
    public_id: str | None = None
    status: str
    detail: str


class BulkDebitResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: List[BulkDebitResult]


# ── Cancel transaction ────────────────────────────────────────────────────────

class CancelTransactionRequest(BaseModel):
    reason: str = Field(min_length=5, description="Admin must provide a cancellation reason")


class CancelTransactionResponse(BaseModel):
    msg: str
    cancelled_transaction: str
    refund_transaction: str
    refunded_amount: float
    new_user_balance: float


# ── Ledger ────────────────────────────────────────────────────────────────────

class LedgerEntryResponse(BaseModel):
    id: str
    transaction_id: str | None = None
    user_id: str | None = None
    entry_type: str
    amount: float
    description: str
    created_at: str


class LedgerResponse(BaseModel):
    transaction_id: str | None = None
    balanced: bool | None = None
    total_debit: float | None = None
    total_credit: float | None = None
    total: int | None = None
    page: int | None = None
    limit: int | None = None
    pages: int | None = None
    entries: List[LedgerEntryResponse] | None = None
    data: List[LedgerEntryResponse] | None = None