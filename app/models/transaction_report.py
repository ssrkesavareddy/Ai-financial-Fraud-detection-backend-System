from sqlalchemy import Column, String, Boolean, DateTime, Integer, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from datetime import datetime
import uuid


class TransactionReport(Base):
    __tablename__ = "transaction_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FKs — prevent orphan reports
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    otp_hash     = Column(String,   nullable=True)
    otp_expiry   = Column(DateTime, nullable=True)
    otp_used     = Column(Boolean,  default=False, nullable=False)

    # Brute-force guard — checked before every verify attempt
    otp_attempts = Column(Integer, default=0, nullable=False)

    last_otp_sent_at = Column(DateTime, nullable=True)

    status = Column(String, default="pending", nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_report_transaction_id"),
    )