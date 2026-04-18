from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import datetime
from math import ceil
from uuid import UUID

from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog, OTPLog


def parse_datetime(value: str, field: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            400,
            f"Invalid date format for '{field}'. Use ISO 8601 (YYYY-MM-DDTHH:MM:SS)"
        )


# ─────────────────────────────────────────────
# FRAUD RATE
# ─────────────────────────────────────────────
def get_fraud_rate(start_date: str, end_date: str, db: Session):
    start = parse_datetime(start_date, "start_date")
    end = parse_datetime(end_date, "end_date")

    query = db.query(Transaction)

    if start:
        query = query.filter(Transaction.created_at >= start)
    if end:
        query = query.filter(Transaction.created_at <= end)

    total = query.count()
    fraud = query.filter(Transaction.is_fraud == True).count()

    return {
        "total": total,
        "fraud": fraud,
        "rate": round((fraud / total) * 100, 2) if total else 0.0,
    }


# ─────────────────────────────────────────────
# FRAUD LOGS
# ─────────────────────────────────────────────
def get_fraud_logs(
    page: int,
    limit: int,
    user_id: UUID | None,
    fraud_only: bool,
    start_date: str,
    end_date: str,
    db: Session
):
    start = parse_datetime(start_date, "start_date")
    end = parse_datetime(end_date, "end_date")

    query = db.query(FraudLog)

    if user_id is not None:
        query = query.filter(FraudLog.user_id == user_id)

    if fraud_only:
        query = query.filter(FraudLog.action_taken == "blocked")

    if start:
        query = query.filter(FraudLog.created_at >= start)

    if end:
        query = query.filter(FraudLog.created_at <= end)

    total = query.count()

    logs = (
        query
        .order_by(FraudLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": ceil(total / limit) if total else 1,
        "data": [
            {
                "user_id": str(log.user_id),
                "amount": log.amount,
                "location": log.location,
                "fraud_score": log.fraud_score,
                "action_taken": log.action_taken,
                "reasons": log.reasons or "",
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


# ─────────────────────────────────────────────
# OTP LOGS
# ─────────────────────────────────────────────
def get_otp_logs(
    page: int,
    limit: int,
    user_id: UUID | None,
    status: str | None,
    start_date: str,
    end_date: str,
    db: Session
):
    start = parse_datetime(start_date, "start_date")
    end = parse_datetime(end_date, "end_date")

    query = db.query(OTPLog)

    if user_id is not None:
        query = query.filter(OTPLog.user_id == user_id)

    if status:
        query = query.filter(OTPLog.status == status)

    if start:
        query = query.filter(OTPLog.created_at >= start)

    if end:
        query = query.filter(OTPLog.created_at <= end)

    total = query.count()

    logs = (
        query
        .order_by(OTPLog.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": ceil(total / limit) if total else 1,
        "data": [
            {
                "user_id": str(log.user_id),
                "otp_type": log.otp_type,
                "status": log.status,
                "attempts": log.attempts,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    }


# ─────────────────────────────────────────────
# FRAUD TREND
# ─────────────────────────────────────────────
def get_fraud_trend(start_date: str, end_date: str, page: int, limit: int, db: Session):
    start = parse_datetime(start_date, "start_date")
    end = parse_datetime(end_date, "end_date")

    base = (
        db.query(
            func.date(FraudLog.created_at).label("date"),
            func.count(FraudLog.id).label("fraud_count"),
        )
        .filter(FraudLog.action_taken == "blocked")
    )

    if start:
        base = base.filter(FraudLog.created_at >= start)
    if end:
        base = base.filter(FraudLog.created_at <= end)

    grouped = base.group_by(func.date(FraudLog.created_at))

    total_dates = db.query(func.count()).select_from(grouped.subquery()).scalar() or 0

    results = (
        grouped
        .order_by(func.date(FraudLog.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    pages = ceil(total_dates / limit) if total_dates else 1

    return {
        "total": total_dates,
        "page": page,
        "limit": limit,
        "pages": pages,
        "data": [{"date": str(r.date), "fraud_count": r.fraud_count} for r in results],
    }