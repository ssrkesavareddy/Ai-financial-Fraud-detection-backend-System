from fastapi import APIRouter, Depends, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.schemas.transaction import TransactionRequest, TransactionResponse
from app.services import fraud_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("/", response_model=TransactionResponse)
def create_transaction(data: TransactionRequest, request: Request,
                       background: BackgroundTasks, db: Session = Depends(get_db),
                       current_user=Depends(require_role(["user"]))):
    result = fraud_service.process_transaction(
        current_user, data.amount, data.transaction_type,
        data.receiver_id, data.ip_address, data.device_id,
        data.location, data.channel, data.transaction_duration,
        db, background
    )

    return result