from sqlalchemy.orm import Session
from app.models.user import User
from app.models.transaction import Transaction
from app.utils.helpers import calculate_age


def get_user_transactions(user: User, db: Session):
    transactions = (db.query(Transaction)
                    .filter(Transaction.user_id == user.id)
                    .order_by(Transaction.created_at.desc())
                    .all())

    return [
        {
            "transaction_id": t.id,
            "amount": t.amount,
            "account_balance": t.account_balance,
            "transaction_duration": t.transaction_duration,
            "customer_age": calculate_age(user.dob) if user.dob else 0,
            "location": t.location,
            "channel": t.channel,
            "login_attempts": t.login_attempts or 0,
            "fraud_score": t.fraud_score,
            "is_fraud": t.is_fraud,
            "reasons": t.reasons.split("|") if t.reasons else [],
            "created_at": t.created_at.isoformat(),
            "transaction_type": t.transaction_type or "debit",
            "receiver_id": t.receiver_id,
            "ip_address": t.ip_address or "",
            "device_id": t.device_id or "",
            "model_version": t.model_version or "v1.0",
        }
        for t in transactions
    ]