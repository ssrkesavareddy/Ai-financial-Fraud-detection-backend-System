from sqlalchemy import Column, String, Float, DateTime, Text, Boolean, Integer, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.core.database import Base
import uuid


class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK — user must exist
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    event_type    = Column(String, nullable=False)
    amount        = Column(Float,  nullable=False)
    location      = Column(String, nullable=False)

    fraud_score   = Column(Float,  nullable=False)
    reasons       = Column(Text,   nullable=True)
    action_taken  = Column(String, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)

    __table_args__ = (
        Index("ix_fraud_logs_user_created", "user_id", "created_at"),
    )


class OTPLog(Base):
    __tablename__ = "otp_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK — user must exist
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    otp_type   = Column(String,  nullable=False)
    status     = Column(String,  nullable=False)
    attempts   = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)