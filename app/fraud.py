from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
import numpy as np
import os
import joblib
import requests
from datetime import datetime

from app.database import get_db
from app.dependencies import require_role
from app.models import Transaction, User, FraudLog
from app.schemas import TransactionRequest, TransactionResponse

from app.utils.email import send_fraud_email
from app.utils.sms import send_sms
from app.utils.sms_templates import fraud_sms

router = APIRouter()

# -------------------------
# MODEL CONFIG
# -------------------------
MODEL_PATH = "ml/fraud_model.pkl"
SCALER_PATH = "ml/scaler.pkl"

MODEL_URL = os.getenv("MODEL_URL")
SCALER_URL = os.getenv("SCALER_URL")

model = None
scaler = None
MODEL_VERSION = "v1.0"


def download_file(url, path):
    if url and not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        response = requests.get(url)
        with open(path, "wb") as f:
            f.write(response.content)


# -------------------------
# LOAD MODEL SAFELY
# -------------------------
try:
    download_file(MODEL_URL, MODEL_PATH)
    download_file(SCALER_URL, SCALER_PATH)

    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

except Exception as e:
    print("Model loading failed:", e)
    model = None
    scaler = None


# -------------------------
# RISK LEVEL
# -------------------------
def get_risk_level(prob: float) -> str:
    if prob > 0.8:
        return "high"
    elif prob > 0.5:
        return "medium"
    return "low"


# -------------------------
# UPDATE KNOWN DEVICES/IPs
# -------------------------
def update_known_ips_devices(user: User, ip: str, device: str):
    if ip not in (user.known_ips or []):
        ips = (user.known_ips or [])[:4]
        ips.insert(0, ip)
        user.known_ips = ips

    if device not in (user.known_devices or []):
        devs = (user.known_devices or [])[:4]
        devs.insert(0, device)
        user.known_devices = devs


# -------------------------
# FRAUD REASONS
# -------------------------
def get_fraud_reasons(amount, balance, attempts, ip, device, user):
    reasons = []

    if amount > balance * 0.8:
        reasons.append("High transaction vs balance")

    if attempts >= 3:
        reasons.append("Multiple transaction attempts")

    if user.known_ips and ip not in user.known_ips:
        reasons.append("New IP address")

    if user.known_devices and device not in user.known_devices:
        reasons.append("Unknown device")

    return reasons


# -------------------------
# MAIN API
# -------------------------
@router.post("/", response_model=TransactionResponse)
def transaction(
    data: TransactionRequest,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["user"]))
):
    user = current_user

    # VALIDATIONS
    if not user.is_verified:
        raise HTTPException(403, "Account not verified")

    if user.is_blocked:
        raise HTTPException(403, "Account blocked")

    if data.amount > user.account_balance:
        raise HTTPException(400, "Insufficient balance")

    # FEATURE ENGINEERING
    is_new_ip = 0 if data.ip_address in (user.known_ips or []) else 1
    is_new_device = 0 if data.device_id in (user.known_devices or []) else 1

    X = np.array([[
        data.amount,
        user.account_balance,
        user.login_attempts,
        is_new_ip,
        is_new_device
    ]])

    # SAFE PREDICTION
    if model is None or scaler is None:
        prob = 0.1
    else:
        X_scaled = scaler.transform(X)
        prob = model.predict_proba(X_scaled)[0][1]

    is_fraud = prob > 0.8

    # REASONS
    reasons = get_fraud_reasons(
        data.amount,
        user.account_balance,
        user.login_attempts,   # ✅ FIXED
        data.ip_address,
        data.device_id,
        user
    )

    event_type = "fraud_detected" if is_fraud else "transaction_ok"

    # FRAUD HANDLING
    if is_fraud:
        user.is_blocked = True

        background.add_task(
            send_fraud_email,
            user.email,
            data.amount,
            data.location,
            prob,
            reasons
        )

        background.add_task(
            send_sms,
            user.phone,
            fraud_sms(data.amount, data.location)
        )
    else:
        user.account_balance -= data.amount
        update_known_ips_devices(user, data.ip_address, data.device_id)

    # SAVE TRANSACTION
    tx = Transaction(
        user_id=user.id,
        amount=data.amount,
        account_balance=user.account_balance,
        transaction_duration=data.transaction_duration,
        customer_age=user.customer_age,
        location=data.location,
        channel=data.channel,
        login_attempts=user.login_attempts,
        fraud_score=float(prob),
        is_fraud=is_fraud,
        reasons="|".join(reasons),
        transaction_type=data.transaction_type,
        receiver_id=data.receiver_id,
        ip_address=data.ip_address,
        device_id=data.device_id,
        model_version=MODEL_VERSION
    )

    db.add(tx)

    # LOG
    db.add(FraudLog(
        user_id=user.id,
        event_type=event_type,
        amount=data.amount,
        location=data.location,
        fraud_score=float(prob),
        reasons="|".join(reasons),
        action_taken="blocked" if is_fraud else "allowed"
    ))

    db.commit()
    db.refresh(tx)

    return TransactionResponse(
        transaction_id=tx.id,
        fraud_probability=float(prob),
        risk_level=get_risk_level(prob),
        model_version=MODEL_VERSION,
        is_fraud=is_fraud,
        reasons=reasons
    )