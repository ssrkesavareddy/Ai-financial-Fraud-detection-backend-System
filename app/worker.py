"""
Background worker for auto-completing DELAYED transactions.

Usage:
  APScheduler (no extra infra needed):
    python -m app.worker

  Celery (recommended for production):
    celery -A app.worker.celery_app worker --beat -l info
    Requires: REDIS_URL env var (default: redis://localhost:6379/0)
"""

import logging
import os

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# APScheduler variant
# ─────────────────────────────────────────────────────────────
def run_with_apscheduler():
    from apscheduler.schedulers.blocking import BlockingScheduler
    from app.core.database import SessionLocal
    from app.services.fraud_service import run_auto_complete

    scheduler = BlockingScheduler()

    def job():
        db = SessionLocal()
        try:
            result = run_auto_complete(db)
            if result["auto_completed"] > 0:
                logger.info(
                    f"[worker] auto-completed {result['auto_completed']} "
                    f"transactions: {result['completed_ids']}"
                )
        except Exception as e:
            logger.error(f"[worker] error: {e}")
        finally:
            db.close()

    scheduler.add_job(job, "interval", minutes=5, id="auto_complete_delayed", replace_existing=True)
    logger.info("[worker] APScheduler started — checking every 5 minutes")
    scheduler.start()


# ─────────────────────────────────────────────────────────────
# Celery variant
# ─────────────────────────────────────────────────────────────
def make_celery_app():
    try:
        from celery import Celery

        REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        celery_app = Celery("fraud_worker", broker=REDIS_URL, backend=REDIS_URL)

        celery_app.conf.beat_schedule = {
            "auto-complete-delayed": {
                "task": "app.worker.auto_complete_task",
                "schedule": 300.0,  # every 5 minutes
            },
        }
        celery_app.conf.timezone = "UTC"

        @celery_app.task(name="app.worker.auto_complete_task")
        def auto_complete_task():
            from app.core.database import SessionLocal
            from app.services.fraud_service import run_auto_complete
            db = SessionLocal()
            try:
                return run_auto_complete(db)
            finally:
                db.close()

        return celery_app

    except ImportError:
        logger.warning("[worker] Celery not installed — use APScheduler instead.")
        return None


# Exported for `celery -A app.worker.celery_app worker --beat`
celery_app = make_celery_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_with_apscheduler()