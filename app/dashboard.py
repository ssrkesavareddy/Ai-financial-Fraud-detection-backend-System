from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from app.database import get_db
from app.models import Transaction, FraudLog, OTPLog
from app.dependencies import require_role
from app.schemas import (
    FraudRateResponse, FraudLogsResponse, FraudLogItem,
    OtpLogsResponse, OTPLogItem, FraudTrendResponse
)

router = APIRouter()

@router.get("/fraud-rate", response_model=FraudRateResponse)
def fraud_rate(
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_role(["admin"]))
):
    query = db.query(Transaction)
    if start_date:
        query = query.filter(Transaction.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(Transaction.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    fraud = query.filter(Transaction.is_fraud == True).count()
    return {
        "total": total,
        "fraud": fraud,
        "rate": round((fraud / total) * 100, 2) if total else 0
    }

@router.get("/fraud-logs", response_model=FraudLogsResponse)
def fraud_logs(
    page: int = 1,
    limit: int = 10,
    user_id: int | None = None,
    fraud_only: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_role(["admin"]))
):
    query = db.query(FraudLog)
    if user_id:
        query = query.filter(FraudLog.user_id == user_id)
    if fraud_only:
        query = query.filter(FraudLog.action_taken == "blocked")
    if start_date:
        query = query.filter(FraudLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(FraudLog.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    pages = (total + limit - 1) // limit

    logs = query.order_by(FraudLog.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    data = [
        FraudLogItem(
            user_id=log.user_id,
            amount=log.amount,
            location=log.location,
            fraud_score=log.fraud_score,
            action_taken=log.action_taken,
            reasons=log.reasons,
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

@router.get("/otp-logs", response_model=OtpLogsResponse)
def otp_logs(
    page: int = 1,
    limit: int = 10,
    user_id: int | None = None,
    status: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
    admin=Depends(require_role(["admin"]))
):
    query = db.query(OTPLog)
    if user_id:
        query = query.filter(OTPLog.user_id == user_id)
    if status:
        query = query.filter(OTPLog.status == status)
    if start_date:
        query = query.filter(OTPLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(OTPLog.created_at <= datetime.fromisoformat(end_date))

    total = query.count()
    pages = (total + limit - 1) // limit

    logs = query.order_by(OTPLog.created_at.desc()) \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    data = [
        OTPLogItem(
            user_id=log.user_id,
            otp_type=log.otp_type,
            status=log.status,
            attempts=log.attempts,
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

@router.get("/fraud-trend", response_model=dict)   # custom response shape
def fraud_trend(
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    limit: int = 30,
    db: Session = Depends(get_db),
    admin=Depends(require_role(["admin"]))
):
    query = db.query(
        func.date(FraudLog.created_at).label("date"),
        func.count(FraudLog.id).label("fraud_count")
    ).filter(FraudLog.action_taken == "blocked")

    if start_date:
        query = query.filter(FraudLog.created_at >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(FraudLog.created_at <= datetime.fromisoformat(end_date))

    # Count total unique dates before pagination
    total_dates = query.group_by("date").count()

    results = query.group_by("date") \
        .order_by("date") \
        .offset((page - 1) * limit) \
        .limit(limit) \
        .all()

    data = [{"date": str(r.date), "fraud_count": r.fraud_count} for r in results]
    pages = (total_dates + limit - 1) // limit if total_dates else 1

    return {
        "total": total_dates,
        "page": page,
        "limit": limit,
        "pages": pages,
        "data": data
    }