from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.schemas.analytics import *
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])

MAX_LIMIT = 100


@router.get("/fraud-rate", response_model=FraudRateResponse)
def fraud_rate(start_date: str | None = None, end_date: str | None = None,
              db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return analytics_service.get_fraud_rate(start_date, end_date, db)


@router.get("/fraud-logs", response_model=FraudLogsResponse)
def fraud_logs(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=MAX_LIMIT),
              user_id: int | None = None, fraud_only: bool = False,
              start_date: str | None = None, end_date: str | None = None,
              db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return analytics_service.get_fraud_logs(page, limit, user_id, fraud_only, start_date, end_date, db)


@router.get("/otp-logs", response_model=OtpLogsResponse)
def otp_logs(page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=MAX_LIMIT),
            user_id: int | None = None, status: str | None = None,
            start_date: str | None = None, end_date: str | None = None,
            db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return analytics_service.get_otp_logs(page, limit, user_id, status, start_date, end_date, db)


@router.get("/fraud-trend")
def fraud_trend(start_date: str | None = None, end_date: str | None = None,
               page: int = Query(1, ge=1), limit: int = Query(30, ge=1, le=MAX_LIMIT),
               db: Session = Depends(get_db), admin=Depends(require_role(["admin"]))):
    return analytics_service.get_fraud_trend(start_date, end_date, page, limit, db)