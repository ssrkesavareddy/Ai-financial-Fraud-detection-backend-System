from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, Date, JSON
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String, index=True)
    password = Column(String)
    security_question = Column(String)
    security_answer = Column(String)
    account_balance = Column(Float, default=50000)
    dob = Column(Date)
    customer_age = Column(Integer)
    role = Column(String, default="user")
    login_attempts = Column(Integer, default=0)
    last_login_attempt_reset = Column(DateTime, default=datetime.utcnow)
    is_verified = Column(Boolean, default=False)
    is_blocked = Column(Boolean, default=False)

    # OTP fields
    otp_hash = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0)
    last_otp_request = Column(DateTime, nullable=True)

    # New: store last used IPs and devices (for fraud detection)
    known_ips = Column(JSON, default=list)       # e.g. ["1.2.3.4", "5.6.7.8"]
    known_devices = Column(JSON, default=list)   # e.g. ["device123", "device456"]

class OTPLog(Base):
    __tablename__ = "otp_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    otp_type = Column(String)
    status = Column(String)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    event_type = Column(String)
    amount = Column(Float)
    location = Column(String)
    fraud_score = Column(Float)
    reasons = Column(Text)
    action_taken = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    amount = Column(Float)
    account_balance = Column(Float)
    transaction_duration = Column(Float)
    customer_age = Column(Integer)
    location = Column(String)
    channel = Column(String)
    login_attempts = Column(Integer)
    fraud_score = Column(Float)
    is_fraud = Column(Boolean)
    reasons = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # NEW COLUMNS
    transaction_type = Column(String)      # debit / credit
    receiver_id = Column(Integer, nullable=True)
    ip_address = Column(String)
    device_id = Column(String)
    model_version = Column(String, default="v1.0")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(Integer)
    action = Column(String)
    target_user_id = Column(Integer)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)