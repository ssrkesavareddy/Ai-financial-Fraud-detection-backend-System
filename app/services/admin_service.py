from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import AuditLog


def get_dashboard_stats(db: Session):
    return {
        "total_users": db.query(User).count(),
        "total_transactions": db.query(Transaction).count(),
    }


def get_all_users(db: Session):
    return db.query(User).all()


def update_user_balance(user_id: int, amount: float, admin: User, db: Session):
    if amount == 0:
        raise HTTPException(400, "Amount must be non-zero.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found.")

    old_balance = user.account_balance
    new_balance = old_balance + amount

    if new_balance < 0:
        raise HTTPException(400, f"Cannot reduce balance below zero. Maximum deduction is ₹{old_balance:.2f}.")

    user.account_balance = new_balance

    db.add(AuditLog(
        admin_id=admin.id,
        action="update_balance",
        target_user_id=user.id,
        details=f"Balance updated: {amount:+.2f}, old={old_balance:.2f}, new={new_balance:.2f}",
    ))
    db.commit()

    return {"new_balance": user.account_balance}


def create_admin_transaction(user_id: int, amount: float, transaction_duration: float,
                             location: str, channel: str, admin: User, db: Session):
    if amount <= 0:
        raise HTTPException(400, "Amount must be greater than zero.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found.")

    if amount > user.account_balance:
        raise HTTPException(400, "Insufficient user balance.")

    user.account_balance -= amount

    tx = Transaction(
        user_id=user.id,
        amount=amount,
        account_balance=user.account_balance,
        transaction_duration=transaction_duration,
        location=location,
        channel=channel,
        login_attempts=user.login_attempts,
        fraud_score=0.0,
        is_fraud=False,
        reasons="Admin initiated transaction",
        transaction_type="debit",
        ip_address="admin",
        device_id="admin",
        model_version="admin_override",
    )
    db.add(tx)

    db.add(AuditLog(
        admin_id=admin.id,
        action="admin_transaction",
        target_user_id=user.id,
        details=f"Admin (#{admin.id}) debited ₹{amount:.2f} from user #{user.id}. New balance: ₹{user.account_balance:.2f}",
    ))
    db.commit()

    return {"msg": "Transaction added successfully."}


def get_audit_logs(page: int, limit: int, admin_id: int, action: str, db: Session):
    query = db.query(AuditLog)

    if admin_id:
        query = query.filter(AuditLog.admin_id == admin_id)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    pages = max(1, (total + limit - 1) // limit)

    logs = (query
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all())

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": pages,
        "data": [
            {
                "id": log.id,
                "admin_id": log.admin_id,
                "action": log.action,
                "target_user_id": log.target_user_id,
                "details": log.details or "",
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }