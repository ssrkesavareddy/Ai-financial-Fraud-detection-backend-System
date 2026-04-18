from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, timedelta
import random
import logging
from uuid import UUID

from app.models.transaction import Transaction
from app.models.transaction_report import TransactionReport
from app.models.user import User
from app.models.fraud_log import OTPLog
from app.services.fraud_service import transition_status
from app.utils.email import send_email_with_retry
from app.core.security import hash_text, verify_text
from app.core.config import OTP_EXPIRY_MINUTES, OTP_MAX_ATTEMPTS, OTP_COOLDOWN_SECS

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# STEP 1 — REQUEST / RESEND OTP (FIXED)
# ─────────────────────────────────────────────
def request_fraud_report(transaction_id: UUID, user: User, db: Session) -> dict:

    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .with_for_update()
        .first()
    )

    if not tx:
        raise HTTPException(404, "Transaction not found")

    if tx.status != "DELAYED":
        raise HTTPException(400, "Only DELAYED transactions can be reported")

    now = datetime.utcnow()

    report = (
        db.query(TransactionReport)
        .filter(TransactionReport.transaction_id == transaction_id)
        .with_for_update()
        .first()
    )

    # ── EXISTING REPORT (RESEND) ─────────────────
    if report:

        if report.status == "verified":
            raise HTTPException(400, "Already verified")

        # cooldown
        if report.last_otp_sent_at:
            elapsed = (now - report.last_otp_sent_at).total_seconds()
            if elapsed < OTP_COOLDOWN_SECS:
                raise HTTPException(
                    429,
                    f"Wait {int(OTP_COOLDOWN_SECS - elapsed)} seconds"
                )

        otp = str(random.randint(100000, 999999))

        # update BEFORE send
        report.otp_hash = hash_text(otp)
        report.otp_expiry = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
        report.otp_used = False
        report.last_otp_sent_at = now

        # 🔴 FIX: send BEFORE commit (critical)
        _send_otp_email_or_raise(user, otp)

        db.add(OTPLog(user_id=user.id, otp_type="report", status="resent"))
        db.commit()

        return {"msg": "OTP resent successfully"}

    # ── FIRST REQUEST ─────────────────
    otp = str(random.randint(100000, 999999))

    new_report = TransactionReport(
        transaction_id=transaction_id,
        user_id=user.id,
        otp_hash=hash_text(otp),
        otp_expiry=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        otp_attempts=0,
        last_otp_sent_at=now,
        status="pending",
    )

    db.add(new_report)

    # 🔴 FIX: send BEFORE commit
    _send_otp_email_or_raise(user, otp)

    db.add(OTPLog(user_id=user.id, otp_type="report", status="sent"))
    db.commit()

    return {"msg": "OTP sent successfully"}


# ─────────────────────────────────────────────
# EMAIL SEND (SAFE)
# ─────────────────────────────────────────────
def _send_otp_email_or_raise(user: User, otp: str):

    html = f"""
    <html><body>
    <h2>Fraud Report OTP</h2>
    <p>Hello {user.name}</p>
    <h1>{otp}</h1>
    <p>Valid for {OTP_EXPIRY_MINUTES} minutes</p>
    </body></html>
    """

    success = send_email_with_retry(user.email, "Fraud Report OTP", html)

    if not success:
        logger.error(f"OTP email failed for user {user.id}")
        raise HTTPException(500, "Failed to send OTP. Try again.")


# ─────────────────────────────────────────────
# STEP 2 — VERIFY OTP
# ─────────────────────────────────────────────
def verify_fraud_report(transaction_id: UUID, otp: str, user: User, db: Session):

    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
        .with_for_update()
        .first()
    )

    if not tx:
        raise HTTPException(404, "Transaction not found")

    if tx.status == "REPORTED":
        return {"msg": "Already reported"}

    if tx.status != "DELAYED":
        raise HTTPException(400, "Invalid state")

    report = (
        db.query(TransactionReport)
        .filter(TransactionReport.transaction_id == transaction_id)
        .with_for_update()
        .first()
    )

    if not report:
        raise HTTPException(404, "No report found")

    # brute-force guard
    if report.otp_attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts")

    if datetime.utcnow() > report.otp_expiry:
        raise HTTPException(400, "OTP expired")

    if report.otp_used:
        raise HTTPException(400, "OTP already used")

    # increment FIRST
    report.otp_attempts += 1
    db.commit()

    if not verify_text(otp, report.otp_hash):
        db.add(OTPLog(user_id=user.id, otp_type="report", status="failed"))
        db.commit()
        raise HTTPException(400, "Invalid OTP")

    # success
    report.otp_used = True
    report.otp_hash = None
    report.otp_attempts = 0
    report.status = "verified"

    transition_status(tx, "REPORTED")
    tx.auto_complete_at = None

    db.add(OTPLog(user_id=user.id, otp_type="report", status="verified"))
    db.commit()

    return {"msg": "Report submitted", "public_id": tx.public_id}