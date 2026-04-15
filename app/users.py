from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Transaction, User
from app.dependencies import get_user, require_role
from app.schemas import UserResponse, TransactionDetailResponse

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
def get_me(user: User = Depends(require_role(["user"]))):
    return user

@router.get("/me/transactions", response_model=list[TransactionDetailResponse])
def get_my_transactions(
    db: Session = Depends(get_db),
        user: User = Depends(require_role(["user"]))
):
    transactions = db.query(Transaction).filter(Transaction.user_id == user.id).all()
    return [
        TransactionDetailResponse(
            transaction_id=t.id,
            amount=t.amount,
            account_balance=t.account_balance,
            transaction_duration=t.transaction_duration,
            customer_age=t.customer_age,
            location=t.location,
            channel=t.channel,
            login_attempts=t.login_attempts,
            fraud_score=t.fraud_score,
            is_fraud=t.is_fraud,
            reasons=t.reasons.split("|") if t.reasons else [],
            created_at=t.created_at.isoformat()
        ) for t in transactions
    ]