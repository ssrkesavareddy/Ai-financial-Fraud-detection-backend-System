from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Transaction, AuditLog
from app.dependencies import require_role
from app.schemas import (
    AdminTransactionRequest, UpdateBalanceRequest, UserResponse,
    DashboardResponse, BalanceUpdateResponse, AdminTransactionResponse,
    AuditLogsResponse, AuditLogItem
)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/dashboard", response_model=DashboardResponse)
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    return {
        "total_users": db.query(User).count(),
        "total_transactions": db.query(Transaction).count()
    }

@router.get("/users", response_model=list[UserResponse])
def get_all_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    return db.query(User).all()

@router.patch("/users/{user_id}/balance", response_model=BalanceUpdateResponse)
def update_balance(
    user_id: int,
    data: UpdateBalanceRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    old_balance = user.account_balance
    user.account_balance += data.amount

    # Improved audit detail
    detail = f"Balance updated: {data.amount:+.2f}, old={old_balance:.2f}, new={user.account_balance:.2f}"
    db.add(AuditLog(
        admin_id=admin.id,
        action="update_balance",
        target_user_id=user.id,
        details=detail
    ))
    db.commit()
    return {"new_balance": user.account_balance}

@router.post("/transactions", response_model=AdminTransactionResponse)
def admin_transaction(
    data: AdminTransactionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if data.amount > user.account_balance:
        raise HTTPException(400, "Insufficient balance")

    user.account_balance -= data.amount
    tx = Transaction(
        user_id=user.id,
        amount=data.amount,
        account_balance=user.account_balance,
        transaction_duration=data.transaction_duration,
        customer_age=user.customer_age,
        location=data.location,
        channel=data.channel,
        login_attempts=user.login_attempts,
        fraud_score=0,
        is_fraud=False,
        reasons="Admin transaction",
        transaction_type="debit",
        ip_address="admin",
        device_id="admin",
        model_version="admin"
    )
    db.add(AuditLog(
        admin_id=admin.id,
        action="admin_transaction",
        target_user_id=user.id,
        details=f"Admin initiated debit of {data.amount} from user {user.id}"
    ))
    db.add(tx)
    db.commit()
    return {"msg": "Transaction added"}

# NEW: GET /admin/audit-logs
@router.get("/audit-logs", response_model=AuditLogsResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    admin_id: int | None = None,
    action: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    query = db.query(AuditLog)
    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    pages = (total + limit - 1) // limit

    logs = query.order_by(AuditLog.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    data = [
        AuditLogItem(
            id=log.id,
            admin_id=log.admin_id,
            action=log.action,
            target_user_id=log.target_user_id,
            details=log.details,
            created_at=log.created_at.isoformat()
        )
        for log in logs
    ]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "data": data
    }