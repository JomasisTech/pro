"""In-process scheduled-post worker for single-instance deployments.

The worker uses independent SQLAlchemy sessions and the dispatcher's atomic row claims.
For horizontal scaling, move media to shared object storage before enabling multiple instances.
"""
import logging
import threading
from app.config import get_settings
from app.core.database import SessionLocal
from app.modules.posting.dispatcher import dispatch_due

log = logging.getLogger(__name__)


def run_worker(stop_event: threading.Event) -> None:
    settings = get_settings()
    interval = max(5, settings.scheduler_poll_interval_seconds)
    log.info("Scheduled-post worker started; polling every %s seconds", interval)
    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                result = dispatch_due(db)
            if any(result.values()):
                log.info("Scheduled-post dispatch result: %s", result)
        except Exception:
            log.exception("Scheduled-post worker cycle failed")
        stop_event.wait(interval)
    log.info("Scheduled-post worker stopped")
