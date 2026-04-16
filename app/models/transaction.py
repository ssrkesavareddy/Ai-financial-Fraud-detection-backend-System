from app.core.database import Base

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text
from sqlalchemy import func

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    account_balance = Column(Float, nullable=False)
    transaction_duration = Column(Float, nullable=False)
    location = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    login_attempts = Column(Integer, default=0)
    fraud_score = Column(Float, nullable=False)
    ml_probability = Column(Float, nullable=True)
    anomaly_score = Column(Float, nullable=True)
    decision = Column(String, nullable=True)
    is_fraud = Column(Boolean, nullable=False)
    reasons = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    transaction_type = Column(String)
    receiver_id = Column(Integer)
    ip_address = Column(String)
    device_id = Column(String)
    model_version = Column(String, default="v1.0")
