from uuid import UUID

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import require_role
from app.schemas.transaction import TransactionRequest, TransactionResponse
from app.services import fraud_service, report_service

router = APIRouter(prefix="/transactions", tags=["Transactions"])

require_user = require_role(["user"])


class FraudReportVerify(BaseModel):
    otp: str


@router.post("/", response_model=TransactionResponse)
def create_transaction(
    data: TransactionRequest,
    background: BackgroundTasks,          # still needed — fraud alert email is bg
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    return fraud_service.process_transaction(current_user, data, db, background)


@router.post("/{transaction_id}/report")
def report_transaction(
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
    # No BackgroundTasks — OTP delivery is synchronous inside the service.
    # The endpoint returns only after email success/failure is known.
):
    return report_service.request_fraud_report(transaction_id, current_user, db)


@router.post("/{transaction_id}/verify-report")
def verify_report(
    transaction_id: UUID,
    data: FraudReportVerify,
    db: Session = Depends(get_db),
    current_user=Depends(require_user),
):
    return report_service.verify_fraud_report(transaction_id, data.otp, current_user, db)