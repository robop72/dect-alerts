import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..config import settings
from ..database import SessionLocal
from ..models import Alert

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(check_escalations, "interval", seconds=10, id="escalation_check", replace_existing=True)
    scheduler.start()
    logger.info("Escalation scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Escalation scheduler stopped")


def check_escalations():
    db = SessionLocal()
    try:
        pending = db.query(Alert).filter(Alert.status.in_(["pending", "calling"])).all()
        now = datetime.now(timezone.utc)
        for alert in pending:
            received = alert.timestamp_received
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            elapsed = (now - received).total_seconds()
            if elapsed >= settings.ESCALATION_TIMEOUT_SECONDS:
                alert.status = "escalated"
                alert.full_log = (alert.full_log or "") + (
                    f"\n[{datetime.utcnow().isoformat()}] ESCALATED — no response after {elapsed:.0f}s"
                    " — Level 2 escalation triggered"
                )
                logger.warning(f"Alert {alert.id} escalated after {elapsed:.0f}s")
        db.commit()
    except Exception as e:
        logger.error(f"Escalation check error: {e}")
        db.rollback()
    finally:
        db.close()
