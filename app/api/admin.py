from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models.user import User

from app.core.security import hash_password
from app.core.database import get_db
from app.core.security import require_role
from app.schemas.admin import *
from app.services import admin_service
from app.schemas.admin import AdminCreateUser
router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=DashboardResponse)
def admin_dashboard(db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return admin_service.get_dashboard_stats(db)


@router.get("/users", response_model=list[UserResponse])
def get_all_users(db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return admin_service.get_all_users(db)


@router.patch("/users/{user_id}/balance", response_model=BalanceUpdateResponse)
def update_balance(user_id: int, data: UpdateBalanceRequest,
                  db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return admin_service.update_user_balance(user_id, data.amount, admin, db)


@router.post("/transactions", response_model=AdminTransactionResponse)
def admin_transaction(data: AdminTransactionRequest, db: Session = Depends(get_db),
                     admin=Depends(require_role(["admin"]))):
    return admin_service.create_admin_transaction(
        data.user_id, data.amount, data.transaction_duration,
        data.location, data.channel, admin, db
    )


@router.get("/audit-logs", response_model=AuditLogsResponse)
def get_audit_logs(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=100),
                  admin_id: int | None = None, action: str | None = None,
                  db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return admin_service.get_audit_logs(page, limit, admin_id, action, db)




@router.post("/create-user")
def create_user_by_admin(
    data: AdminCreateUser,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    existing = db.query(User).filter(User.email == data.email).first()

    if existing:
        raise HTTPException(400, "User already exists")

    user = User(
        email=data.email,
        password=hash_password(data.password),
        phone=data.phone,
        dob=data.dob,
        is_verified=True,
        account_balance=0.0
    )

    db.add(user)
    db.commit()

    return {"msg": "User created successfully"}

@router.patch("/users/{user_id}/block")
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    user.is_blocked = True

    db.add(AuditLog(
        admin_id=admin.id,
        action="block_user",
        target_user_id=user.id,
        details=f"Admin {admin.id} blocked user {user.id}"
    ))

    db.commit()

    return {"msg": "User blocked successfully"}


@router.patch("/users/{user_id}/unblock")
def unblock_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(["admin"]))
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(404, "User not found")

    user.is_blocked = False
    db.add(AuditLog(
        admin_id=admin.id,
        action= "unblock_user",
        target_user_id=user.id,
        details=f"Admin {admin.id} blocked user {user.id}"
    ))
    db.commit()

    return {"msg": "User unblocked successfully"}