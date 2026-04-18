from sqlalchemy import Column, String, Boolean, Float, Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from app.core.database import Base
import uuid
from sqlalchemy.orm import validates


class User(Base):
    __tablename__ = "users"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id = Column(String, unique=True, index=True, nullable=True)

    # ── Identity ──────────────────────────────────────────────────────────────
    name  = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, nullable=False)

    password = Column(String, nullable=True)

    account_balance = Column(Float, default=0.0, nullable=False)
    dob             = Column(Date,  nullable=True)

    role = Column(String, default="user", nullable=False)

    @validates("role")
    def validate_role(self, key, value):
        return value.lower()

    login_attempts           = Column(Integer,  default=0,    nullable=False)
    last_login_attempt_reset = Column(DateTime, nullable=True)

    # is_verified: user completed OTP verification during registration.
    # Set to True immediately on successful OTP — NO email activation link needed.
    is_verified = Column(Boolean, default=False, nullable=False)

    # is_active: admin-controlled flag.
    # Deactivated users (is_active=False) cannot login regardless of is_verified.
    # Admins use PATCH /admin/users/{id}/activate|deactivate to toggle this.
    is_active = Column(Boolean, default=True, nullable=False)

    # is_blocked: user self-blocked their account. Can still login but not transact.
    is_blocked = Column(Boolean, default=False, nullable=False)

    # ── Unblock OTP ───────────────────────────────────────────────────────────
    unblock_otp_hash         = Column(String,   nullable=True)
    unblock_otp_expiry       = Column(DateTime, nullable=True)
    unblock_otp_used         = Column(Boolean,  default=False, nullable=False)
    unblock_otp_attempts     = Column(Integer,  default=0,     nullable=False)
    last_unblock_otp_request = Column(DateTime, nullable=True)

    # ── Registration / General OTP ────────────────────────────────────────────
    otp_hash         = Column(String,   nullable=True)
    otp_expiry       = Column(DateTime, nullable=True)
    otp_attempts     = Column(Integer,  default=0, nullable=False)
    last_otp_request = Column(DateTime, nullable=True)

    known_ips     = Column(ARRAY(String), default=[])
    known_devices = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
        UniqueConstraint("phone", name="uq_user_phone"),
    )