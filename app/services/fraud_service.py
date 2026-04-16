from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
import pandas as pd
from datetime import datetime

from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog
from app.utils.email import send_fraud_email
from app.utils.sms import send_sms
from app.utils.sms_templates import fraud_sms
from app.utils.helpers import calculate_age
from app.ml.model_loader import get_pipeline


def get_risk_level(score):
    if score > 0.7:
        return "high"
    elif score > 0.4:
        return "medium"
    return "low"


def get_fraud_reasons(row, prob):
    reasons = []

    if prob > 0.5:
        reasons.append("High ML fraud probability")

    if row["Amount_to_Balance_Ratio"] > 0.7:
        reasons.append("Large transaction vs balance")

    if row["LoginAttempts"] > 3:
        reasons.append("Multiple login attempts")

    if row["is_night"] == 1:
        reasons.append("Night-time transaction")

    return reasons


def process_transaction(user: User, amount: float, transaction_type: str,
                        receiver_id: int, ip_address: str, device_id: str,
                        location: str, channel: str, transaction_duration: float,
                        db: Session, background: BackgroundTasks):
    if not user.is_verified:
        raise HTTPException(403, "Account not verified")

    if user.is_blocked:
        raise HTTPException(403, "Account blocked")

    if amount > user.account_balance:
        raise HTTPException(400, "Insufficient balance")

    balance = user.account_balance
    age = calculate_age(user.dob) if user.dob else 0
    ratio = amount / (balance + 1)

    hour = datetime.utcnow().hour
    is_night = 1 if hour < 6 or hour > 22 else 0

    X = pd.DataFrame([{
        "TransactionAmount": amount,
        "AccountBalance": balance,
        "TransactionDuration": transaction_duration,
        "LoginAttempts": user.login_attempts,
        "CustomerAge": age,
        "Amount_to_Balance_Ratio": ratio,
        "amount_deviation": ratio,
        "login_risk": 1 if user.login_attempts > 3 else 0,
        "is_night": is_night,
        "TransactionType": transaction_type,
        "Location": location,
        "Channel": channel
    }])

    pipeline = get_pipeline()
    prob = float(pipeline.predict_proba(X)[0][1]) if pipeline else 0.1

    final_score = prob
    anomaly_score = 0.0

    if final_score > 0.7:
        decision = "block"
    elif final_score > 0.4:
        decision = "review"
    else:
        decision = "allow"

    is_fraud = decision != "allow"
    reasons = get_fraud_reasons(X.iloc[0], prob)

    if decision == "block":
        user.is_blocked = True
        background.add_task(send_fraud_email, user.email, amount, location, final_score, reasons)
        background.add_task(send_sms, user.phone, fraud_sms(amount, location))
    elif decision == "allow":
        user.account_balance -= amount

    tx = Transaction(
        user_id=user.id,
        amount=amount,
        account_balance=user.account_balance,
        transaction_duration=transaction_duration,
        location=location,
        channel=channel,
        login_attempts=user.login_attempts,
        fraud_score=final_score,
        ml_probability=prob,
        anomaly_score=anomaly_score,
        decision=decision,
        is_fraud=is_fraud,
        reasons="|".join(reasons),
        transaction_type=transaction_type,
        receiver_id=receiver_id,
        ip_address=ip_address,
        device_id=device_id,
        model_version="v2_pipeline"
    )

    db.add(tx)

    db.add(FraudLog(
        user_id=user.id,
        event_type="fraud_detected" if is_fraud else "transaction_ok",
        amount=amount,
        location=location,
        fraud_score=final_score,
        reasons="|".join(reasons),
        action_taken=decision
    ))

    db.commit()
    db.refresh(tx)

    return {
        "transaction_id": tx.id,
        "fraud_probability": final_score,
        "ml_probability": prob,
        "anomaly_score": anomaly_score,
        "decision": decision,
        "risk_level": get_risk_level(final_score),
        "model_version": "v2_pipeline",
        "is_fraud": is_fraud,
        "reasons": reasons
    }