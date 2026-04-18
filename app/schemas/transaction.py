from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class TransactionType(str, Enum):
    # User-initiated
    debit  = "debit"    # user sends money out (balance decreases)
    credit = "credit"   # user receives money in (balance increases)

    # Admin-initiated (appear in user's history with clear labels)
    admin_debit       = "admin_debit"       # admin debits user
    admin_credit      = "admin_credit"      # admin credits user (e.g. add balance)
    bulk_debit        = "bulk_debit"        # admin bulk debit
    bulk_credit       = "bulk_credit"       # admin bulk credit

    # System-generated
    refund   = "refund"   # issued after cancel or reverse
    reversal = "reversal"


class TransactionRequest(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: TransactionType = Field(
        ...,
        description="'debit' = money out, 'credit' = money in"
    )
    receiver_id: Optional[UUID] = Field(
        None,
        description="Required for debit transfers — the recipient user UUID"
    )
    ip_address: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    transaction_duration: float = Field(gt=0)
    idempotency_key: Optional[str] = None


class TransactionResponse(BaseModel):
    public_id: str
    transaction_type: str
    fraud_probability: float
    decision: str
    risk_level: Optional[str]
    is_fraud: bool
    reasons: List[str]
    status: str
    idempotent: bool = False

    model_config = {"from_attributes": True}


class TransactionDetailResponse(BaseModel):
    public_id: str
    transaction_type: str        # debit / credit / admin_credit / admin_debit / bulk_* / refund
    direction: str               # "in" (balance increased) or "out" (balance decreased)
    amount: float
    account_balance: float
    transaction_duration: float
    location: str
    channel: str
    login_attempts: int
    fraud_score: float
    is_fraud: bool
    reasons: List[str]
    created_at: datetime
    receiver_id: Optional[str] = None
    ip_address: str
    device_id: str
    model_version: str
    status: str

    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    refunded_at: Optional[datetime] = None
    refund_transaction_id: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Types that increase user balance (money IN) ────────────────────────────────
CREDIT_TYPES = {"credit", "admin_credit", "bulk_credit", "refund"}

# ── Types that decrease user balance (money OUT) ──────────────────────────────
DEBIT_TYPES  = {"debit", "admin_debit", "bulk_debit", "reversal"}


def get_direction(transaction_type: str) -> str:
    """Return 'in' or 'out' for any transaction type."""
    return "in" if transaction_type in CREDIT_TYPES else "out"