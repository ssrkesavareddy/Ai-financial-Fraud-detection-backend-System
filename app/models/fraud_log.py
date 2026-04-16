from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Index
from datetime import datetime
from app.core.database import Base


class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    fraud_score = Column(Float, nullable=False)
    reasons = Column(Text, nullable=True)
    action_taken = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    __table_args__ = (
        Index("ix_fraud_logs_user_created", "user_id", "created_at"),
    )


class OTPLog(Base):
    __tablename__ = "otp_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    otp_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer, nullable=False, index=True)
    action = Column(String, nullable=False)
    target_user_id = Column(Integer, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
