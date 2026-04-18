from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
from datetime import datetime, timedelta
import random
import logging

from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import OTPLog
from app.utils.helpers import calculate_age
from app.utils.email import send_unblock_otp_email
from app.core.security import hash_text, verify_text
from app.schemas.transaction import CREDIT_TYPES, DEBIT_TYPES, get_direction

logger = logging.getLogger(__name__)

UNBLOCK_COOLDOWN_SECONDS = 60


# ── Transactions ──────────────────────────────────────────────────────────────

# Internal types that must never be exposed to end-users via the API.
# Admins see real types via the admin panel; user-facing history shows only
# the financial direction, not the internal mechanism.
_INTERNAL_TYPE_MAP: dict[str, str] = {
    "admin_credit": "credit",
    "admin_debit":  "debit",
    "bulk_credit":  "credit",
    "bulk_debit":   "debit",
    "reversal":     "credit",   # reversal arrives as money-in for the user
}


def _public_type(tx_type: str) -> str:
    """Map internal transaction types to their user-visible equivalents."""
    return _INTERNAL_TYPE_MAP.get(tx_type, tx_type)


def _serialize_tx(t: Transaction) -> dict:
    raw_type = t.transaction_type or "debit"
    txn_type = _public_type(raw_type)           # sanitised for user-facing output
    return {
        "public_id":             t.public_id or "",
        "transaction_type":      txn_type,
        "direction":             get_direction(raw_type),   # "in" or "out"
        "amount":                t.amount,
        "account_balance":       t.account_balance,
        "balance_before":        t.balance_before,
        "balance_after":         t.balance_after,
        "transaction_duration":  t.transaction_duration,
        "location":              t.location,
        "channel":               t.channel,
        "login_attempts":        t.login_attempts or 0,
        "fraud_score":           t.fraud_score,
        "is_fraud":              t.is_fraud,
        "reasons":               t.reasons.split("|") if t.reasons else [],
        "created_at":            t.created_at.isoformat(),
        "receiver_id":           t.receiver_id,
        "ip_address":            t.ip_address or "",
        "device_id":             t.device_id or "",
        "model_version":         t.model_version or "v1.0",
        "status":                t.status or "PENDING",
        "cancelled_at":          t.cancelled_at.isoformat() if t.cancelled_at else None,
        "cancel_reason":         t.cancel_reason,
        "refunded_at":           t.refunded_at.isoformat() if t.refunded_at else None,
        "refund_transaction_id": str(t.refund_transaction_id) if t.refund_transaction_id else None,
    }


def get_user_transactions(user: User, db: Session, txn_type_filter: str | None = None):
    """All transactions for the user, optionally filtered by type."""
    q = db.query(Transaction).filter(Transaction.user_id == user.id)
    if txn_type_filter:
        q = q.filter(Transaction.transaction_type == txn_type_filter)
    txns = q.order_by(Transaction.created_at.desc()).all()
    return [_serialize_tx(t) for t in txns]


def get_user_debits(user: User, db: Session):
    """All transactions where money left the user's account."""
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.transaction_type.in_(DEBIT_TYPES),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return [_serialize_tx(t) for t in txns]


def get_user_credits(user: User, db: Session):
    """All transactions where money arrived into the user's account."""
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user.id,
            Transaction.transaction_type.in_(CREDIT_TYPES),
        )
        .order_by(Transaction.created_at.desc())
        .all()
    )
    return [_serialize_tx(t) for t in txns]


# ── Self-block ────────────────────────────────────────────────────────────────

def self_block(user: User, db: Session):
    if user.is_blocked:
        raise HTTPException(400, "Account already blocked")
    user.is_blocked = True

    # BUG FIX (5): AuditLog.admin_id is a UUID FK pointing at users.id.
    # Passing integer 0 crashes PostgreSQL with a type-mismatch error.
    # Self-block and self-unblock are user actions, not admin actions, so
    # we record them in OTPLog (which has no admin_id constraint) instead.
    db.add(OTPLog(user_id=user.id, otp_type="self_block", status="blocked"))
    db.commit()
    return {"msg": "Account blocked successfully"}


# ── Unblock — Step 1: send OTP to registered email ───────────────────────────

def request_unblock(user: User, db: Session, background: BackgroundTasks):
    if not user.is_blocked:
        raise HTTPException(400, "Account is not blocked")

    if user.last_unblock_otp_request:
        elapsed = (datetime.utcnow() - user.last_unblock_otp_request).total_seconds()
        if elapsed < UNBLOCK_COOLDOWN_SECONDS:
            wait = int(UNBLOCK_COOLDOWN_SECONDS - elapsed)
            raise HTTPException(429, f"Wait {wait}s before requesting again")

    otp = str(random.randint(100000, 999999))

    user.unblock_otp_hash         = hash_text(otp)
    user.unblock_otp_expiry       = datetime.utcnow() + timedelta(minutes=5)
    user.unblock_otp_used         = False
    user.unblock_otp_attempts     = 0
    user.last_unblock_otp_request = datetime.utcnow()

    db.add(OTPLog(user_id=user.id, otp_type="unblock", status="sent"))
    db.commit()

    background.add_task(send_unblock_otp_email, user.email, user.name, otp)

    return {"msg": "Unblock OTP sent to your registered email address."}


# ── Unblock — Step 2: verify OTP ─────────────────────────────────────────────

def verify_unblock(user: User, otp: str, db: Session):
    if not user.is_blocked:
        raise HTTPException(400, "Account is not blocked")

    if not user.unblock_otp_hash:
        raise HTTPException(400, "No unblock OTP requested. Call /request-unblock first.")

    if datetime.utcnow() > user.unblock_otp_expiry:
        raise HTTPException(400, "OTP expired. Request a new one.")

    if user.unblock_otp_attempts >= 5:
        raise HTTPException(429, "Too many attempts. Request a new OTP.")

    if user.unblock_otp_used:
        raise HTTPException(400, "OTP already used. Request a new one.")

    if not verify_text(otp, user.unblock_otp_hash):
        user.unblock_otp_attempts += 1
        db.add(OTPLog(user_id=user.id, otp_type="unblock", status="failed"))
        db.commit()
        raise HTTPException(400, "Invalid OTP")

    # Success
    user.unblock_otp_used     = True
    user.unblock_otp_hash     = None
    user.unblock_otp_expiry   = None
    user.unblock_otp_attempts = 0
    user.is_blocked           = False

    # BUG FIX (5): Same fix — use OTPLog instead of AuditLog for user self-actions.
    db.add(OTPLog(user_id=user.id, otp_type="unblock", status="verified"))
    db.commit()
    return {"msg": "Account unblocked successfully"}