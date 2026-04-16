from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.schemas.admin import UserResponse
from app.schemas.transaction import TransactionDetailResponse
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(user=Depends(require_role(["user"]))):
    return user


@router.get("/me/transactions", response_model=list[TransactionDetailResponse])
def get_my_transactions(db: Session = Depends(get_db), user=Depends(require_role(["user"]))):
    return user_service.get_user_transactions(user, db)