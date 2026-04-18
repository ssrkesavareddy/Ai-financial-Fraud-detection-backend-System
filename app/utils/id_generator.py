"""
Human-readable ID generators for transactions and users.

Transaction ID format:  TXN-<USER_SHORT>-<YYYYMMDD>-<RANDOM6>
  e.g.  TXN-USR4F2A-20260418-XK9P3Q

User ID format:         USR-<RANDOM8>
  e.g.  USR-4F2AJ8BQ

Rules:
  - uppercase alphanumeric only (no ambiguous chars: 0 O I L)
  - transaction IDs embed user short-code + date → easy to trace
  - user IDs are random (not sequential) → not enumerable
"""

import random
from datetime import date

# Remove visually ambiguous characters
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0,O,I,1,L


def _rand_str(length: int) -> str:
    return "".join(random.choices(_ALPHABET, k=length))


def generate_user_public_id() -> str:
    """USR-<8 random chars>  e.g. USR-4F2AJ8BQ"""
    return f"USR-{_rand_str(8)}"


def generate_transaction_public_id(user_public_id: str) -> str:
    """
    TXN-<user_short>-<YYYYMMDD>-<6 random chars>
    user_short = first 6 chars of the user_public_id (after stripping 'USR-' prefix).
    Date is always today (UTC) — no external arg needed.

    BUG FIX: The previous signature required a `date_str` second argument but every
    call site omitted it, causing a TypeError at runtime.  Date is now generated
    internally so callers only pass the user identifier.

    e.g. TXN-4F2AJ8-20260418-XK9P3Q
    """
    date_str = date.today().strftime("%Y%m%d")
    short = (user_public_id.replace("USR-", "") + "XXXXXX")[:6]
    return f"TXN-{short}-{date_str}-{_rand_str(6)}"