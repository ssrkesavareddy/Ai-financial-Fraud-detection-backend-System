from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, nullable=False, unique=True, index=True)
    phone = Column(String, nullable=False, unique=True)

    password = Column(String, nullable=False)



    account_balance = Column(Float, default=0.0, nullable=False)

    dob = Column(Date, nullable=True)

    role = Column(String, default="user", nullable=False)

    login_attempts = Column(Integer, default=0, nullable=False)
    last_login_attempt_reset = Column(DateTime, nullable=True)

    is_verified = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)

    otp_hash = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0, nullable=False)
    last_otp_request = Column(DateTime, nullable=True)

    known_ips = Column(ARRAY(String), default=[])
    known_devices = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
        UniqueConstraint("phone", name="uq_user_phone"),
    )