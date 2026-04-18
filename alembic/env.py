from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context

from app.core.database import Base, DATABASE_URL

# 🔴 EXPLICIT IMPORTS (NO WILDCARD)
from app.models.user import User
from app.models.transaction import Transaction
from app.models.ledger import LedgerEntry
from app.models.fraud_log import FraudLog, OTPLog
from app.models.transaction_report import TransactionReport
from app.models.audit_log import AuditLog

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()