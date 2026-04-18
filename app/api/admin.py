from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.user import User
from app.core.database import get_db
from app.core.security import require_role
from app.schemas.admin import *
from app.services import admin_service
from app.services.fraud_service import admin_approve, admin_reverse

router = APIRouter(prefix="/admin", tags=["Admin"])
require_admin = require_role(["admin"])


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardResponse)
def admin_dashboard(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.get_dashboard_stats(db)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserResponse])
def get_all_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.get_all_users(db)


@router.patch("/users/{user_id}/balance", response_model=BalanceUpdateResponse)
def update_balance(user_id: UUID, data: UpdateBalanceRequest,
                   db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.update_user_balance(user_id, data.amount, admin, db)


@router.patch("/users/{user_id}/block")
def block_user(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.block_user(user_id, admin, db)


@router.patch("/users/{user_id}/unblock")
def unblock_user(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.unblock_user(user_id, admin, db)


@router.patch("/users/{user_id}/activate")
def activate_user(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.activate_user(user_id, admin, db)


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(user_id: UUID, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return admin_service.deactivate_user(user_id, admin, db)


@router.post("/create-user")
def create_user_by_admin(data: AdminCreateUser, db: Session = Depends(get_db),
                          admin: User = Depends(require_admin)):
    return admin_service.create_user_by_admin(data, db)


# ── Single admin transaction (debit) ─────────────────────────────────────────

@router.post("/transactions", response_model=AdminTransactionResponse)
def admin_transaction(data: AdminTransactionRequest, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    return admin_service.create_admin_transaction(
        data.user_id, data.amount, data.transaction_duration,
        data.location, data.channel, admin, db,
    )


# ── Bulk debit ────────────────────────────────────────────────────────────────

@router.post("/bulk-transactions", response_model=BulkDebitResponse)
def admin_bulk_debit(data: BulkTransactionRequest, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    """
    Debit amount FROM each user's balance.
    Per-row SAVEPOINT — failures don't roll back earlier rows.
    Ledger entry + audit log written per row.
    """
    return admin_service.create_bulk_debit(data.transactions, admin, db)


# ── Bulk credit ───────────────────────────────────────────────────────────────

@router.post("/bulk-credit", response_model=BulkCreditResponse)
def admin_bulk_credit(data: BulkCreditRequest, db: Session = Depends(get_db),
                      admin: User = Depends(require_admin)):
    """
    Credit amount INTO each user's balance.
    Use for salary disbursals, cashback, incentives, corrections, etc.
    Ledger entry + audit log written per row.
    """
    return admin_service.create_bulk_credit(data.transactions, admin, db)


# ── Cancel transaction + auto-refund ─────────────────────────────────────────

@router.post("/transactions/{transaction_id}/cancel", response_model=CancelTransactionResponse)
def cancel_transaction(
    transaction_id: UUID,
    data: CancelTransactionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin cancels a COMPLETED transaction.
    - Status → CANCELLED
    - Refund issued immediately (user balance restored)
    - Refund transaction created for traceability
    - Ledger entries + audit log written
    Only COMPLETED transactions can be cancelled.
    """
    return admin_service.cancel_transaction(transaction_id, data.reason, admin, db)


# ── Reported transactions (fraud review queue) ────────────────────────────────

@router.get("/reported-transactions")
def get_reported_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return admin_service.get_reported_transactions(page, limit, db)


@router.post("/transactions/{transaction_id}/approve")
def approve_reported(transaction_id: UUID, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    """Approve a REPORTED transaction → COMPLETED (fraud claim rejected, no refund)."""
    return admin_approve(transaction_id, admin, db)


@router.post("/transactions/{transaction_id}/reverse")
def reverse_reported(transaction_id: UUID, db: Session = Depends(get_db),
                     admin: User = Depends(require_admin)):
    """Reverse a REPORTED transaction → REVERSED + refund to user."""
    return admin_reverse(transaction_id, admin, db)


# ── Ledger visibility ─────────────────────────────────────────────────────────

@router.get("/transactions/{transaction_id}/ledger")
def get_transaction_ledger(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Return all double-entry ledger records for a transaction.
    Shows whether debit == credit (balanced field).
    """
    return admin_service.get_ledger_for_transaction(transaction_id, db)


@router.get("/users/{user_id}/ledger")
def get_user_ledger(
    user_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Full financial ledger history for a user — every debit and credit."""
    return admin_service.get_user_ledger(user_id, page, limit, db)


# ── Audit logs ────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogsResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    admin_id: UUID | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return admin_service.get_audit_logs(page, limit, admin_id, action, db)


# ── Worker trigger ────────────────────────────────────────────────────────────

@router.post("/worker/run-auto-complete", tags=["Admin", "Worker"])
def trigger_auto_complete(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Manually trigger the auto-complete worker. Testing/debugging only."""
    from app.services.fraud_service import run_auto_complete
    return run_auto_complete(db)


# ── Ledger validation ─────────────────────────────────────────────────────────

@router.get("/ledger/validate", tags=["Admin", "Ledger"])
def validate_ledger(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Run a double-entry consistency check across the entire ledger.

    For every transfer transaction (receiver_id IS NOT NULL), the sum of
    debit entries must equal the sum of credit entries.

    Returns:
      - total_transactions_checked
      - imbalanced: list of {transaction_id, total_debit, total_credit, delta}
      - status: "OK" | "IMBALANCED"
    """
    from app.services.admin_service import validate_ledger_integrity
    return validate_ledger_integrity(db)