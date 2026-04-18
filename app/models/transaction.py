from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer, ForeignKey, CheckConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id = Column(String, unique=True, index=True, nullable=True)

    # Idempotency key — caller supplies a UUID per unique intent.
    # Duplicate submissions with same key return the existing transaction.
    idempotency_key = Column(String, unique=True, nullable=True, index=True)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    amount = Column(Float, nullable=False)
    account_balance = Column(Float, nullable=False)   # balance AFTER transaction (legacy compat)
    balance_before = Column(Float, nullable=True)     # balance BEFORE deduction/addition
    balance_after  = Column(Float, nullable=True)     # balance AFTER  deduction/addition
    transaction_duration = Column(Float, nullable=False)

    location = Column(String, nullable=False)
    channel = Column(String, nullable=False)

    login_attempts = Column(Integer, default=0)

    fraud_score = Column(Float, nullable=False)
    ml_probability = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)

    decision = Column(String, nullable=True)
    is_fraud = Column(Boolean, nullable=False)
    reasons = Column(String, nullable=True)

    # transfer / debit / credit / reversal / bulk_debit / bulk_credit / refund
    transaction_type = Column(String)

    receiver_id = Column(String)
    ip_address = Column(String)
    device_id = Column(String)
    model_version = Column(String, default="v1.0")

    # Status state machine:
    # PENDING → DELAYED → COMPLETED
    #         → COMPLETED (clean allow)
    # DELAYED → REPORTED → COMPLETED / REVERSED
    # COMPLETED → CANCELLED (admin cancel, within window)
    # CANCELLED → refund issued automatically
    status = Column(String, default="PENDING", nullable=False, server_default="PENDING")

    auto_complete_at = Column(DateTime, nullable=True)

    # Cancellation fields
    cancelled_by_admin_id = Column(UUID(as_uuid=True), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancel_reason = Column(Text, nullable=True)

    # Refund tracking
    refund_transaction_id = Column(UUID(as_uuid=True), nullable=True)
    refunded_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','DELAYED','COMPLETED','REPORTED','REVERSED','CANCELLED')",
            name="ck_transaction_status",
        ),
        Index("ix_transactions_status_auto_complete", "status", "auto_complete_at"),
        Index("ix_transactions_user_status", "user_id", "status"),
    )