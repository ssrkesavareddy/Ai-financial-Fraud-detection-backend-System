from dotenv import load_dotenv
import os

load_dotenv()

# ── Auth ──────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY")
BASE_URL   = os.getenv("BASE_URL")

if not SECRET_KEY:
    raise RuntimeError("FATAL: SECRET_KEY environment variable is not set.")
if not BASE_URL:
    raise RuntimeError("FATAL: BASE_URL environment variable is not set.")

# ── Fraud / worker ────────────────────────────────────────────────────────────
# Hours a suspicious transaction is held before auto-completing.
FRAUD_DELAY_HOURS = float(os.getenv("FRAUD_DELAY_HOURS", "5"))

# Maximum rows the worker processes per run (prevents OOM on large tables).
WORKER_BATCH_SIZE = int(os.getenv("WORKER_BATCH_SIZE", "100"))

# ── OTP ───────────────────────────────────────────────────────────────────────
# All OTP behaviour is driven from here — change one env var, whole system adapts.
OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "5"))
OTP_MAX_ATTEMPTS   = int(os.getenv("OTP_MAX_ATTEMPTS",   "5"))
OTP_COOLDOWN_SECS  = int(os.getenv("OTP_COOLDOWN_SECS",  "60"))