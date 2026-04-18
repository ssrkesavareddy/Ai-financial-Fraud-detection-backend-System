"""
Double-entry ledger.

Every money movement produces exactly two entries:
  sender  → debit  (-amount)
  receiver → credit (+amount)

This guarantees sum(debits) == sum(credits) across all entries
for any transaction_id, making the ledger auditable and reversible.
"""

from sqlalchemy import Column, String, Float, DateTime, CheckConstraint, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Which high-level transaction this entry belongs to
    transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which user's balance this entry affects
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # "debit"  → money leaves this user  (balance decreases)
    # "credit" → money arrives for this user (balance increases)
    entry_type = Column(String, nullable=False)

    amount = Column(Float, nullable=False)

    # Human-readable note (e.g. "bulk debit", "admin credit", "reversal")
    description = Column(String, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("entry_type IN ('debit','credit')", name="ck_ledger_entry_type"),
        CheckConstraint("amount > 0", name="ck_ledger_amount_positive"),
        Index("ix_ledger_transaction", "transaction_id"),
        Index("ix_ledger_user_created", "user_id", "created_at"),
    )