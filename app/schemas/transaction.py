from pydantic import BaseModel, Field
from typing import Optional, List


class TransactionRequest(BaseModel):
    amount: float = Field(gt=0)
    transaction_type: str
    receiver_id: Optional[int] = None
    ip_address: str
    device_id: str
    location: str
    channel: str
    transaction_duration: float = Field(gt=0)


class TransactionResponse(BaseModel):
    transaction_id: int
    fraud_probability: float
    ml_probability: float
    anomaly_score: float
    decision: str
    risk_level: str
    model_version: str
    is_fraud: bool
    reasons: List[str]


class TransactionDetailResponse(BaseModel):
    transaction_id: int
    amount: float
    account_balance: float
    transaction_duration: float
    location: str
    channel: str
    login_attempts: int
    fraud_score: float
    is_fraud: bool
    reasons: List[str]
    created_at: str
    transaction_type: str
    receiver_id: Optional[int] = None
    ip_address: str
    device_id: str
    model_version: str
