from pydantic import BaseModel
from typing import Optional, List


class FraudRateResponse(BaseModel):
    total: int
    fraud: int
    rate: float


class FraudLogItem(BaseModel):
    user_id: int
    amount: float
    location: str
    fraud_score: float
    action_taken: str
    reasons: Optional[str] = ""
    created_at: str


class OTPLogItem(BaseModel):
    user_id: int
    otp_type: str
    status: str
    attempts: int
    created_at: str


class FraudLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[FraudLogItem]


class OtpLogsResponse(BaseModel):
    total: int
    page: int
    limit: int
    pages: int
    data: List[OTPLogItem]


class FraudTrendResponse(BaseModel):
    date: str
    fraud_count: int