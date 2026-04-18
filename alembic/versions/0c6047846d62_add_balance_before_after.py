"""add balance_before_after

Revision ID: 0c6047846d62
Revises: ae3fadba002a
Create Date: 2026-04-18

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = '0c6047846d62'
down_revision: Union[str, Sequence[str], None] = 'ae3fadba002a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ✅ ADD COLUMNS (use NUMERIC, not FLOAT)
    op.add_column(
        "transactions",
        sa.Column("balance_before", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=True),
    )

    # ✅ BACKFILL ONLY WHAT IS SAFE
    op.execute("""
        UPDATE transactions
        SET balance_after = account_balance
        WHERE balance_after IS NULL;
    """)

    # ✅ MAKE balance_after REQUIRED
    op.alter_column(
        "transactions",
        "balance_after",
        nullable=False
    )

    # ✅ USEFUL INDEX
    op.create_index(
        "ix_tx_user_created",
        "transactions",
        ["user_id", "created_at"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tx_user_created", table_name="transactions")
    op.drop_column("transactions", "balance_after")
    op.drop_column("transactions", "balance_before")