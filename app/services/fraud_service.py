"""
fraud_service.py — user transaction creation, fraud logic, admin decisions, worker.

Transaction type rules:
  debit  → balance decreases, fraud-checked, goes through DELAYED if suspicious
  credit → balance increases, no fraud check (user receives funds)

report_service.py owns the OTP/reporting lifecycle.
"""

from sqlalchemy.orm import Session
from fastapi import HTTPException, BackgroundTasks
from datetime import datetime, timedelta
import logging
from uuid import UUID

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.transaction import Transaction
from app.models.fraud_log import FraudLog
from app.models.ledger import LedgerEntry
from app.schemas.transaction import TransactionRequest, get_direction
from app.utils.email import send_fraud_email
from app.utils.id_generator import generate_transaction_public_id
from app.core.config import FRAUD_DELAY_HOURS, WORKER_BATCH_SIZE

logger = logging.getLogger(__name__)

# ── State machine ─────────────────────────────────────────────────────────────
ALLOWED_TRANSITIONS = {
    "PENDING":   {"DELAYED", "COMPLETED"},
    "DELAYED":   {"COMPLETED", "REPORTED"},
    "REPORTED":  {"COMPLETED", "REVERSED"},
    "COMPLETED": {"CANCELLED"},
    "CANCELLED": set(),
    "REVERSED":  set(),
}


def transition_status(tx: Transaction, new_status: str) -> None:
    if new_status not in ALLOWED_TRANSITIONS.get(tx.status, set()):
        raise HTTPException(400, f"Invalid transition {tx.status} → {new_status}")
    tx.status = new_status


# ── Helpers ───────────────────────────────────────────────────────────────────
def _audit(db: Session, admin_id, action: str, target_user_id, details: str = "") -> None:
    db.add(AuditLog(
        admin_id=admin_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
    ))


def _ledger(db: Session, transaction_id, user_id,
            entry_type: str, amount: float, description: str = "") -> None:
    db.add(LedgerEntry(
        transaction_id=transaction_id,
        user_id=user_id,
        entry_type=entry_type,
        amount=amount,
        description=description,
    ))


# ── Create transaction (user-initiated) ───────────────────────────────────────
def process_transaction(
    user: User,
    data: TransactionRequest,
    db: Session,
    bg: BackgroundTasks,
) -> dict:
    if user.is_blocked:
        raise HTTPException(403, "User blocked")

    # ── Idempotency ───────────────────────────────────────────────────────────
    if data.idempotency_key:
        existing = (
            db.query(Transaction)
            .filter(Transaction.idempotency_key == data.idempotency_key)
            .first()
        )
        if existing:
            return {
                "public_id":         existing.public_id,
                "transaction_type":  existing.transaction_type,
                "fraud_probability": existing.fraud_score,
                "decision":          existing.decision or "allow",
                "risk_level":        "high" if existing.fraud_score >= 0.8 else "low",
                "is_fraud":          existing.is_fraud,
                "reasons":           existing.reasons.split("|") if existing.reasons else [],
                "status":            existing.status,
                "idempotent":        True,
            }

    txn_type = data.transaction_type.value

    # ══════════════════════════════════════════════════════════════════════════
    # CREDIT — user receives money in (e.g. top-up, P2P receive)
    # No fraud check. Balance increases.
    # ══════════════════════════════════════════════════════════════════════════
    if txn_type == "credit":
        balance_before = user.account_balance
        user.account_balance += data.amount
        balance_after = user.account_balance
        public_id = generate_transaction_public_id(user.public_id or str(user.id))

        tx = Transaction(
            public_id            = public_id,
            idempotency_key      = data.idempotency_key or None,
            user_id              = user.id,
            amount               = data.amount,
            account_balance      = user.account_balance,
            balance_before       = balance_before,
            balance_after        = balance_after,
            transaction_duration = data.transaction_duration,
            location             = data.location,
            channel              = data.channel,
            login_attempts       = user.login_attempts,
            ip_address           = data.ip_address,
            device_id            = data.device_id,
            transaction_type     = "credit",
            receiver_id          = str(data.receiver_id) if data.receiver_id else None,
            fraud_score          = 0.0,
            ml_probability       = 0.0,
            decision             = "allow",
            is_fraud             = False,
            reasons              = "",
            status               = "COMPLETED",
            model_version        = "n/a",
        )
        db.add(tx)
        db.flush()
        _ledger(db, tx.id, user.id, "credit", data.amount,
                f"user credit {public_id}")
        db.commit()
        db.refresh(tx)

        return {
            "public_id":         tx.public_id,
            "transaction_type":  "credit",
            "fraud_probability": 0.0,
            "decision":          "allow",
            "risk_level":        "low",
            "is_fraud":          False,
            "reasons":           [],
            "status":            "COMPLETED",
            "idempotent":        False,
        }

    # ══════════════════════════════════════════════════════════════════════════
    # DEBIT — user sends money out. Fraud-checked.
    # ══════════════════════════════════════════════════════════════════════════
    if txn_type == "debit":
        if data.amount > user.account_balance:
            raise HTTPException(400, "Insufficient balance")

        reasons_list: list[str] = []

        # ── Multi-factor fraud rules ──────────────────────────────────────────
        # Rule 1: Large amount relative to balance (>40% is suspicious)
        if data.amount > user.account_balance * 0.4:
            reasons_list.append("High amount ratio (>40% of balance)")

        # Rule 2: Unknown / suspicious location
        if data.location.strip().lower() in ("unknown", "", "none"):
            reasons_list.append("Unknown location")

        # Rule 3: Unknown / suspicious device
        if "unknown" in data.device_id.strip().lower():
            reasons_list.append("Unknown device ID")

        # Rule 4: Multiple failed logins before this transaction
        if user.login_attempts >= 3:
            reasons_list.append(f"High login attempts ({user.login_attempts})")

        # Rule 5: Suspicious IP ranges (non-RFC1918 and non-common corp)
        if data.ip_address.startswith(("77.", "91.", "45.", "185.")):
            reasons_list.append("Suspicious IP range")

        # Rule 6: Very short transaction duration (bot-like speed)
        if data.transaction_duration < 1:
            reasons_list.append("Abnormally fast transaction (<1s)")

        is_fraud    = len(reasons_list) > 0
        fraud_score = min(0.2 * len(reasons_list), 1.0) if is_fraud else 0.1
        status           = "COMPLETED"
        auto_complete_at = None

        # Capture balance BEFORE deduction for audit trail
        balance_before = user.account_balance

        # Deduct immediately — prevents double-spend during delay window
        user.account_balance -= data.amount
        balance_after = user.account_balance

        if is_fraud:
            status           = "DELAYED"
            auto_complete_at = datetime.utcnow() + timedelta(hours=FRAUD_DELAY_HOURS)
            bg.add_task(send_fraud_email, user.email, data.amount,
                        data.location, fraud_score, reasons_list)

        public_id = generate_transaction_public_id(user.public_id or str(user.id))

        tx = Transaction(
            public_id            = public_id,
            idempotency_key      = data.idempotency_key or None,
            user_id              = user.id,
            amount               = data.amount,
            account_balance      = user.account_balance,
            balance_before       = balance_before,
            balance_after        = balance_after,
            transaction_duration = data.transaction_duration,
            location             = data.location,
            channel              = data.channel,
            login_attempts       = user.login_attempts,
            ip_address           = data.ip_address,
            device_id            = data.device_id,
            transaction_type     = "debit",
            receiver_id          = str(data.receiver_id) if data.receiver_id else None,
            fraud_score          = fraud_score,
            ml_probability       = fraud_score,
            decision             = "block" if is_fraud else "allow",
            is_fraud             = is_fraud,
            reasons              = "|".join(reasons_list),
            status               = status,
            auto_complete_at     = auto_complete_at,
            model_version        = "rule_v1",
        )
        db.add(tx)
        db.add(FraudLog(
            user_id      = user.id,
            event_type   = "fraud" if is_fraud else "normal",
            amount       = data.amount,
            location     = data.location,
            fraud_score  = fraud_score,
            reasons      = "|".join(reasons_list),
            action_taken = status,
        ))
        db.flush()

        if status == "COMPLETED":
            _ledger(db, tx.id, user.id, "debit", data.amount,
                    f"user debit {public_id}")
            if data.receiver_id:
                # Verify receiver exists before writing ledger entry
                receiver = (
                    db.query(User)
                    .filter(User.id == data.receiver_id)
                    .with_for_update()
                    .first()
                )
                if not receiver:
                    raise HTTPException(404, f"Receiver {data.receiver_id} not found — transfer aborted")
                receiver.account_balance += data.amount
                _ledger(db, tx.id, data.receiver_id, "credit", data.amount,
                        f"received from debit {public_id}")

        db.commit()
        db.refresh(tx)

        return {
            "public_id":         tx.public_id,
            "transaction_type":  "debit",
            "fraud_probability": fraud_score,
            "decision":          "block" if is_fraud else "allow",
            "risk_level":        "high" if fraud_score >= 0.8 else "low",
            "is_fraud":          is_fraud,
            "reasons":           reasons_list,
            "status":            status,
            "idempotent":        False,
        }

    raise HTTPException(400,
        "transaction_type must be 'debit' or 'credit'. "
        "Admin types (admin_debit, admin_credit, bulk_*) are triggered via /admin endpoints.")


# ── Admin approve ─────────────────────────────────────────────────────────────
def admin_approve(transaction_id: UUID, admin: User, db: Session) -> dict:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not tx:
        raise HTTPException(404, "Transaction not found")
    if tx.status != "REPORTED":
        raise HTTPException(400, "Only REPORTED transactions can be approved")

    transition_status(tx, "COMPLETED")
    _ledger(db, tx.id, tx.user_id, "debit", tx.amount,
            f"admin approved reported tx {tx.public_id} — fraud claim rejected")
    _audit(db, admin.id, "approve", tx.user_id,
           f"Approved fraud report tx {tx.public_id} — no refund")
    db.commit()
    return {"msg": "Approved", "public_id": tx.public_id}


# ── Admin reverse ─────────────────────────────────────────────────────────────
def admin_reverse(transaction_id: UUID, admin: User, db: Session) -> dict:
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not tx:
        raise HTTPException(404, "Transaction not found")
    if tx.status == "REVERSED":
        return {"msg": "Already reversed"}
    if tx.status != "REPORTED":
        raise HTTPException(400, "Only REPORTED transactions can be reversed")

    user = (
        db.query(User)
        .filter(User.id == tx.user_id)
        .with_for_update()
        .first()
    )

    user.account_balance += tx.amount
    transition_status(tx, "REVERSED")
    _ledger(db, tx.id, user.id, "credit", tx.amount,
            f"admin reversed reported tx {tx.public_id} — refund issued")

    # Standalone refund transaction for full traceability
    refund_pub = generate_transaction_public_id(user.public_id or str(user.id))
    refund_tx = Transaction(
        public_id            = refund_pub,
        user_id              = user.id,
        amount               = tx.amount,
        account_balance      = user.account_balance,
        transaction_duration = 0.0,
        location             = tx.location or "system",
        channel              = "system",
        login_attempts       = 0,
        fraud_score          = 0.0,
        is_fraud             = False,
        reasons              = f"Refund for reversed tx {tx.public_id or str(tx.id)}",
        transaction_type     = "refund",
        ip_address           = "admin",
        device_id            = "admin",
        model_version        = "admin",
        status               = "COMPLETED",
    )
    db.add(refund_tx)
    db.flush()

    tx.refund_transaction_id = refund_tx.id
    tx.refunded_at           = datetime.utcnow()
    _ledger(db, refund_tx.id, user.id, "credit", tx.amount,
            f"refund for reversed tx {tx.public_id or str(tx.id)}")

    _audit(db, admin.id, "reverse", user.id,
           f"Reversed tx {tx.public_id} — refund ₹{tx.amount:.2f} → {refund_pub}")
    db.commit()
    return {
        "msg": "Reversed and refunded",
        "public_id": tx.public_id,
        "refund_transaction": refund_pub,
        "refunded_amount": tx.amount,
    }


# ── Worker ────────────────────────────────────────────────────────────────────
def run_auto_complete(db: Session) -> dict:
    now = datetime.utcnow()
    candidates = (
        db.query(Transaction)
        .filter(
            Transaction.status == "DELAYED",
            Transaction.auto_complete_at <= now,
        )
        .limit(WORKER_BATCH_SIZE)
        .all()
    )

    completed_ids: list[str] = []
    reversed_ids:  list[str] = []
    failed_ids:    list[str] = []

    for candidate in candidates:
        savepoint = db.begin_nested()
        try:
            tx = (
                db.query(Transaction)
                .filter(Transaction.id == candidate.id)
                .with_for_update(skip_locked=True)
                .first()
            )
            if not tx:
                savepoint.rollback()
                continue
            if tx.status != "DELAYED":
                savepoint.rollback()
                continue

            user = (
                db.query(User)
                .filter(User.id == tx.user_id)
                .with_for_update()
                .first()
            )

            transition_status(tx, "COMPLETED")
            _ledger(db, tx.id, tx.user_id, "debit", tx.amount,
                    f"auto-completed delayed tx {tx.public_id or str(tx.id)}")
            if tx.receiver_id:
                try:
                    receiver_uuid = UUID(tx.receiver_id)
                    receiver = (
                        db.query(User)
                        .filter(User.id == receiver_uuid)
                        .with_for_update()
                        .first()
                    )
                    if receiver:
                        receiver.account_balance += tx.amount
                        _ledger(db, tx.id, receiver_uuid, "credit", tx.amount,
                                f"auto-completed credit from tx {tx.public_id or str(tx.id)}")
                    else:
                        logger.warning(f"[worker] Receiver {tx.receiver_id} not found for tx {tx.public_id}")
                except (ValueError, AttributeError) as e:
                    logger.warning(f"[worker] Bad receiver_id on tx {tx.public_id}: {e}")

            completed_ids.append(tx.public_id or str(tx.id))
            db.flush()
            savepoint.commit()

        except Exception as exc:
            tid = getattr(candidate, "public_id", None) or str(candidate.id)
            logger.error(f"[worker] Failed {tid}: {exc}", exc_info=True)
            failed_ids.append(tid)
            savepoint.rollback()

    db.commit()
    return {
        "auto_completed": len(completed_ids),
        "auto_reversed":  len(reversed_ids),
        "failed":         len(failed_ids),
        "completed_ids":  completed_ids,
        "reversed_ids":   reversed_ids,
        "failed_ids":     failed_ids,
    }
