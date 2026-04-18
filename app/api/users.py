from fastapi import APIRouter, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import require_role
from app.schemas.admin import UserResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


class UnblockVerifyRequest(BaseModel):
    otp: str


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_me(user=Depends(require_role(["user"]))):
    return user


# ── Transactions — all, debits only, credits only ─────────────────────────────

@router.get("/me/transactions")
def get_my_transactions(
    type: str | None = Query(None, description="Filter by type: debit, credit, admin_credit, admin_debit, bulk_debit, bulk_credit, refund, reversal"),
    db: Session = Depends(get_db),
    user=Depends(require_role(["user"])),
):
    """
    All transactions for the current user.
    Pass ?type=<transaction_type> to filter to a specific type.
    Each row includes a 'direction' field: 'in' (balance grew) or 'out' (balance shrank).
    """
    return user_service.get_user_transactions(user, db, txn_type_filter=type)


@router.get("/me/transactions/debits")
def get_my_debits(
    db: Session = Depends(get_db),
    user=Depends(require_role(["user"])),
):
    """
    Only transactions where money left the account:
    debit, admin_debit, bulk_debit, reversal.
    """
    return user_service.get_user_debits(user, db)


@router.get("/me/transactions/credits")
def get_my_credits(
    db: Session = Depends(get_db),
    user=Depends(require_role(["user"])),
):
    """
    Only transactions where money arrived in the account:
    credit, admin_credit, bulk_credit, refund.
    """
    return user_service.get_user_credits(user, db)


# ── Self-block / unblock ──────────────────────────────────────────────────────

@router.post("/me/block")
def block_self(db: Session = Depends(get_db), user=Depends(require_role(["user"]))):
    """User blocks their own account."""
    return user_service.self_block(user, db)


@router.post("/request-unblock")
def request_unblock(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(require_role(["user"])),
):
    """Step 1 — send an OTP to the user's registered email."""
    return user_service.request_unblock(user, db, background)


@router.post("/verify-unblock")
def verify_unblock(
    data: UnblockVerifyRequest,
    db: Session = Depends(get_db),
    user=Depends(require_role(["user"])),
):
    """Step 2 — verify the OTP to unblock the account."""
    return user_service.verify_unblock(user, data.otp, db)