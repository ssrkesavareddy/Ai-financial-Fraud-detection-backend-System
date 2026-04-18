from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from math import ceil
from datetime import datetime

from app.core.security import hash_password
from app.models.user import User
from app.models.transaction import Transaction
from app.models.ledger import LedgerEntry
from app.models.audit_log import AuditLog
from app.utils.id_generator import generate_user_public_id, generate_transaction_public_id
from app.services.fraud_service import transition_status


# ─────────────────────────────────────────────────────────────
# SHARED HELPERS
# ─────────────────────────────────────────────────────────────

def _audit(db, admin_id, action, target_user_id, details=""):
    db.add(AuditLog(admin_id=admin_id, action=action,
                    target_user_id=target_user_id, details=details))


def _ledger(db, transaction_id, user_id, entry_type, amount, description=""):
    db.add(LedgerEntry(transaction_id=transaction_id, user_id=user_id,
                       entry_type=entry_type, amount=amount, description=description))


def _make_tx(user, amount, txn_type, location, channel, duration, pub,
             status="COMPLETED", balance_before=None, balance_after=None):
    """Build a Transaction ORM object. Caller must db.add() + db.flush()."""
    return Transaction(
        public_id            = pub,
        user_id              = user.id,
        amount               = amount,
        account_balance      = user.account_balance,
        balance_before       = balance_before if balance_before is not None else user.account_balance,
        balance_after        = balance_after  if balance_after  is not None else user.account_balance,
        transaction_duration = duration,
        location             = location,
        channel              = channel,
        login_attempts       = user.login_attempts,
        fraud_score          = 0.0,
        ml_probability       = 0.0,
        is_fraud             = False,
        reasons              = f"Admin {txn_type}",
        transaction_type     = txn_type,
        ip_address           = "admin",
        device_id            = "admin",
        model_version        = "admin",
        status               = status,
    )


# ─────────────────────────────────────────────────────────────
# DASHBOARD / USERS
# ─────────────────────────────────────────────────────────────

def get_dashboard_stats(db: Session):
    return {
        "total_users":        db.query(User).count(),
        "total_transactions": db.query(Transaction).count(),
    }


def get_all_users(db: Session):
    return db.query(User).all()


# ─────────────────────────────────────────────────────────────
# ADD / ADJUST BALANCE  →  always creates a Transaction row
# ─────────────────────────────────────────────────────────────

def update_user_balance(user_id: UUID, amount: float, admin: User, db: Session):
    """
    Admin adjusts a user's balance.
      amount > 0  → admin_credit  (money added)
      amount < 0  → admin_debit   (money removed)

    Creates a visible Transaction row so the user sees it in their history
    with the correct type label.
    """
    if amount == 0:
        raise HTTPException(400, "Amount must be non-zero.")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found.")

    abs_amount = abs(amount)
    txn_type   = "admin_credit" if amount > 0 else "admin_debit"

    if amount < 0 and abs_amount > user.account_balance:
        raise HTTPException(400, "Cannot reduce balance below zero.")

    # Capture balance before mutation
    bal_before = user.account_balance

    # Move balance
    user.account_balance = round(user.account_balance + amount, 2)
    bal_after = user.account_balance

    pub = generate_transaction_public_id(user.public_id or str(user.id))
    tx  = _make_tx(user, abs_amount, txn_type, "admin-panel", "admin", 0.0, pub,
                   balance_before=bal_before, balance_after=bal_after)
    db.add(tx)
    db.flush()

    # Ledger
    ledger_type = "credit" if amount > 0 else "debit"
    _ledger(db, tx.id, user.id, ledger_type, abs_amount,
            f"admin balance adjustment {amount:+.2f}")

    _audit(db, admin.id, f"balance_{txn_type}", user.id,
           f"{amount:+.2f} → new balance ₹{user.account_balance:.2f} | tx {pub}")
    db.commit()

    return {
        "new_balance":      user.account_balance,
        "transaction_type": txn_type,
        "public_id":        pub,
    }


# ─────────────────────────────────────────────────────────────
# SINGLE ADMIN DEBIT
# ─────────────────────────────────────────────────────────────

def create_admin_transaction(
    user_id: UUID, amount: float, transaction_duration: float,
    location: str, channel: str, admin: User, db: Session,
):
    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found")
    if amount > user.account_balance:
        raise HTTPException(400, "Insufficient balance")

    user.account_balance -= amount
    pub = generate_transaction_public_id(user.public_id or str(user.id))
    tx  = _make_tx(user, amount, "admin_debit", location, channel, transaction_duration, pub)
    db.add(tx)
    db.flush()

    _ledger(db, tx.id, user.id, "debit", amount, "admin single debit")
    _audit(db, admin.id, "admin_debit", user.id,
           f"₹{amount:.2f} debited | tx {pub}")
    db.commit()
    return {"msg": "Transaction created", "public_id": pub, "transaction_type": "admin_debit"}


# ─────────────────────────────────────────────────────────────
# BULK DEBIT
# ─────────────────────────────────────────────────────────────

def create_bulk_debit(transactions, admin: User, db: Session):
    """Debit FROM multiple users. SAVEPOINT per row. Full ledger + audit."""
    results   = []
    succeeded = 0
    failed    = 0

    for idx, tx_data in enumerate(transactions):
        sp = db.begin_nested()
        try:
            user = db.query(User).filter(User.id == tx_data.user_id).with_for_update().first()
            if not user:         raise ValueError("User not found")
            if user.is_blocked:  raise ValueError("User is blocked")
            if tx_data.amount <= 0: raise ValueError("Invalid amount")
            if tx_data.amount > user.account_balance: raise ValueError("Insufficient balance")

            user.account_balance -= tx_data.amount
            pub = generate_transaction_public_id(user.public_id or str(user.id))
            tx  = _make_tx(user, tx_data.amount, "bulk_debit",
                           tx_data.location, tx_data.channel, tx_data.transaction_duration, pub)
            db.add(tx)
            db.flush()

            _ledger(db, tx.id, user.id, "debit", tx_data.amount, "admin bulk debit")
            _audit(db, admin.id, "bulk_debit", user.id,
                   f"Bulk debit ₹{tx_data.amount:.2f} | tx={pub}")

            sp.commit()
            results.append({"index": idx, "user_id": str(user.id),
                             "public_id": pub, "transaction_type": "bulk_debit",
                             "status": "success", "detail": f"₹{tx_data.amount:.2f} debited"})
            succeeded += 1

        except Exception as e:
            sp.rollback()
            results.append({"index": idx, "user_id": str(getattr(tx_data, "user_id", "")),
                             "public_id": None, "transaction_type": "bulk_debit",
                             "status": "failed", "detail": str(e)})
            failed += 1

    db.commit()
    return {"total": len(transactions), "succeeded": succeeded,
            "failed": failed, "results": results}


# ─────────────────────────────────────────────────────────────
# BULK CREDIT
# ─────────────────────────────────────────────────────────────

def create_bulk_credit(transactions, admin: User, db: Session):
    """Credit INTO multiple users. SAVEPOINT per row. Full ledger + audit."""
    results   = []
    succeeded = 0
    failed    = 0

    for idx, tx_data in enumerate(transactions):
        sp = db.begin_nested()
        try:
            user = db.query(User).filter(User.id == tx_data.user_id).with_for_update().first()
            if not user:             raise ValueError("User not found")
            if not user.is_active:   raise ValueError("User account is deactivated")

            user.account_balance += tx_data.amount
            pub = generate_transaction_public_id(user.public_id or str(user.id))
            tx  = _make_tx(user, tx_data.amount, "bulk_credit",
                           tx_data.location, tx_data.channel, tx_data.transaction_duration, pub)
            db.add(tx)
            db.flush()

            _ledger(db, tx.id, user.id, "credit", tx_data.amount, "admin bulk credit")
            _audit(db, admin.id, "bulk_credit", user.id,
                   f"Bulk credit ₹{tx_data.amount:.2f} | tx={pub}")

            sp.commit()
            results.append({"index": idx, "user_id": str(user.id),
                             "public_id": pub, "transaction_type": "bulk_credit",
                             "status": "success", "detail": f"₹{tx_data.amount:.2f} credited"})
            succeeded += 1

        except Exception as e:
            sp.rollback()
            results.append({"index": idx, "user_id": str(getattr(tx_data, "user_id", "")),
                             "public_id": None, "transaction_type": "bulk_credit",
                             "status": "failed", "detail": str(e)})
            failed += 1

    db.commit()
    return {"total": len(transactions), "succeeded": succeeded,
            "failed": failed, "results": results}


# ─────────────────────────────────────────────────────────────
# CANCEL TRANSACTION + AUTO REFUND
# ─────────────────────────────────────────────────────────────

def cancel_transaction(transaction_id: UUID, reason: str, admin: User, db: Session):
    tx = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .with_for_update()
        .first()
    )
    if not tx:
        raise HTTPException(404, "Transaction not found")
    if tx.status == "CANCELLED":
        raise HTTPException(400, "Already cancelled")
    if tx.status == "REVERSED":
        raise HTTPException(400, "Already reversed — cannot cancel")
    if tx.status != "COMPLETED":
        raise HTTPException(400, f"Only COMPLETED transactions can be cancelled (current: {tx.status})")

    user = db.query(User).filter(User.id == tx.user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "Transaction owner not found")

    now = datetime.utcnow()

    transition_status(tx, "CANCELLED")
    tx.cancelled_by_admin_id = admin.id
    tx.cancelled_at          = now
    tx.cancel_reason         = reason

    # Reversal ledger entry on original tx
    _ledger(db, tx.id, user.id, "credit", tx.amount,
            f"cancellation by admin {admin.id}")

    # Issue refund — credit balance back
    user.account_balance += tx.amount
    refund_pub = generate_transaction_public_id(user.public_id or str(user.id))
    refund_tx  = _make_tx(user, tx.amount, "refund", tx.location or "system",
                          "system", 0.0, refund_pub)
    refund_tx.reasons = f"Refund for cancelled tx {tx.public_id or str(tx.id)}"
    db.add(refund_tx)
    db.flush()

    tx.refund_transaction_id = refund_tx.id
    tx.refunded_at           = now

    _ledger(db, refund_tx.id, user.id, "credit", tx.amount,
            f"refund for cancelled tx {tx.public_id or str(tx.id)}")

    _audit(db, admin.id, "cancel_transaction", user.id,
           f"Cancelled tx {tx.public_id} (₹{tx.amount:.2f}). "
           f"Reason: {reason}. Refund tx: {refund_pub}")
    db.commit()

    return {
        "msg":                  "Transaction cancelled and refund issued",
        "cancelled_transaction": tx.public_id or str(tx.id),
        "refund_transaction":    refund_pub,
        "transaction_type":      "refund",
        "refunded_amount":       tx.amount,
        "new_user_balance":      user.account_balance,
    }


# ─────────────────────────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────────────────────────

def get_audit_logs(page, limit, admin_id, action, db: Session):
    q = db.query(AuditLog)
    if admin_id is not None:  q = q.filter(AuditLog.admin_id == admin_id)
    if action is not None:    q = q.filter(AuditLog.action == action)
    total = q.count()
    logs  = q.order_by(AuditLog.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    return {
        "total": total, "page": page, "limit": limit,
        "pages": max(1, ceil(total / limit)),
        "data": [
            {"id": str(l.id), "admin_id": str(l.admin_id),
             "target_user_id": str(l.target_user_id), "action": l.action,
             "details": l.details or "", "created_at": l.created_at.isoformat()}
            for l in logs
        ],
    }


# ─────────────────────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────────────────────

def block_user(user_id: UUID, admin: User, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.is_blocked = True
    _audit(db, admin.id, "block_user", user.id, "blocked")
    db.commit()
    return {"msg": "User blocked"}


def unblock_user(user_id: UUID, admin: User, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    user.is_blocked = False
    _audit(db, admin.id, "unblock_user", user.id, "unblocked")
    db.commit()
    return {"msg": "User unblocked"}


def create_user_by_admin(data, db: Session):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "User already exists")
    user = User(
        name=data.name, public_id=generate_user_public_id(),
        email=data.email, password=hash_password(data.password),
        phone=data.phone, dob=data.dob, is_verified=True, account_balance=0.0,
    )
    db.add(user)
    db.commit()
    return {"msg": "User created successfully"}


def get_reported_transactions(page, limit, db: Session):
    q     = db.query(Transaction).filter(Transaction.status == "REPORTED")
    total = q.count()
    txns  = q.order_by(Transaction.created_at.desc()).offset((page-1)*limit).limit(limit).all()
    return {
        "total": total, "page": page, "limit": limit,
        "pages": max(1, ceil(total / limit)),
        "data": [
            {"transaction_id": str(t.id), "public_id": t.public_id or "",
             "user_id": str(t.user_id), "amount": t.amount,
             "transaction_type": t.transaction_type,
             "location": t.location, "fraud_score": t.fraud_score,
             "reasons": t.reasons.split("|") if t.reasons else [],
             "status": t.status, "created_at": t.created_at.isoformat()}
            for t in txns
        ],
    }


def activate_user(user_id: UUID, admin: User, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    if user.is_active: raise HTTPException(400, "Already active")
    user.is_active = True
    _audit(db, admin.id, "activate_user", user.id, f"Activated {user.email}")
    db.commit()
    from app.utils.email import send_account_activated_email
    try: send_account_activated_email(user.email, user.name)
    except Exception: pass
    return {"msg": "Account activated."}


def deactivate_user(user_id: UUID, admin: User, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user: raise HTTPException(404, "User not found")
    if user.role == "admin": raise HTTPException(403, "Cannot deactivate another admin")
    if not user.is_active: raise HTTPException(400, "Already deactivated")
    user.is_active = False
    _audit(db, admin.id, "deactivate_user", user.id, f"Deactivated {user.email}")
    db.commit()
    from app.utils.email import send_account_deactivated_email
    try: send_account_deactivated_email(user.email, user.name)
    except Exception: pass
    return {"msg": "Account deactivated."}


# ─────────────────────────────────────────────────────────────
# LEDGER QUERIES
# ─────────────────────────────────────────────────────────────

def get_ledger_for_transaction(transaction_id: UUID, db: Session):
    entries = (
        db.query(LedgerEntry)
        .filter(LedgerEntry.transaction_id == transaction_id)
        .order_by(LedgerEntry.created_at)
        .all()
    )
    if not entries:
        raise HTTPException(404, "No ledger entries for this transaction")
    total_debit  = sum(e.amount for e in entries if e.entry_type == "debit")
    total_credit = sum(e.amount for e in entries if e.entry_type == "credit")
    return {
        "transaction_id": str(transaction_id),
        "balanced":       abs(total_debit - total_credit) < 0.001,
        "total_debit":    total_debit,
        "total_credit":   total_credit,
        "entries": [
            {"id": str(e.id), "user_id": str(e.user_id), "entry_type": e.entry_type,
             "amount": e.amount, "description": e.description or "",
             "created_at": e.created_at.isoformat()}
            for e in entries
        ],
    }


def get_user_ledger(user_id: UUID, page: int, limit: int, db: Session):
    q     = db.query(LedgerEntry).filter(LedgerEntry.user_id == user_id).order_by(LedgerEntry.created_at.desc())
    total = q.count()
    entries = q.offset((page-1)*limit).limit(limit).all()
    return {
        "total": total, "page": page, "limit": limit,
        "pages": max(1, ceil(total / limit)),
        "data": [
            {"id": str(e.id), "transaction_id": str(e.transaction_id),
             "entry_type": e.entry_type, "amount": e.amount,
             "description": e.description or "", "created_at": e.created_at.isoformat()}
            for e in entries
        ],
    }



# ── Ledger integrity validation ───────────────────────────────────────────────

def validate_ledger_integrity(db: Session) -> dict:
    """
    Check that every transfer transaction has balanced double-entry ledger rows:
      SUM(debit entries) == SUM(credit entries) per transaction_id

    Pure debit or credit transactions are excluded — they are single-leg by design.
    Only transactions with a receiver_id (transfers) must balance.
    """
    from sqlalchemy import text

    sql = text("""
        SELECT
            t.id::text                                                        AS transaction_id,
            t.public_id,
            COALESCE(SUM(CASE WHEN l.entry_type = 'debit'  THEN l.amount ELSE 0 END), 0) AS total_debit,
            COALESCE(SUM(CASE WHEN l.entry_type = 'credit' THEN l.amount ELSE 0 END), 0) AS total_credit
        FROM transactions t
        LEFT JOIN ledger_entries l ON l.transaction_id = t.id
        WHERE t.receiver_id IS NOT NULL
          AND t.status IN ('COMPLETED', 'DELAYED', 'REPORTED')
        GROUP BY t.id, t.public_id
        HAVING
            ABS(
                COALESCE(SUM(CASE WHEN l.entry_type = 'debit'  THEN l.amount ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN l.entry_type = 'credit' THEN l.amount ELSE 0 END), 0)
            ) > 0.01
        ORDER BY t.id
    """)

    imbalanced_rows = db.execute(sql).fetchall()

    # Also count total transfer transactions checked
    count_sql = text("""
        SELECT COUNT(*) FROM transactions
        WHERE receiver_id IS NOT NULL
          AND status IN ('COMPLETED', 'DELAYED', 'REPORTED')
    """)
    total = db.execute(count_sql).scalar() or 0

    imbalanced = [
        {
            "transaction_id": row.transaction_id,
            "public_id":      row.public_id,
            "total_debit":    round(row.total_debit, 2),
            "total_credit":   round(row.total_credit, 2),
            "delta":          round(abs(row.total_debit - row.total_credit), 2),
        }
        for row in imbalanced_rows
    ]

    return {
        "status":                   "OK" if not imbalanced else "IMBALANCED",
        "total_transfers_checked":  total,
        "imbalanced_count":         len(imbalanced),
        "imbalanced":               imbalanced,
    }
