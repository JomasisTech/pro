"""Database-backed Brand Intelligence sync worker."""
import logging
import threading
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import or_, select, update

from app.core.database import SessionLocal
from app.models import BrandSyncJob, Membership, SocialAccount
from app.modules.audit.activity import record_activity
from app.api.v1.brand_intelligence import sync_social_account

log = logging.getLogger(__name__)
AUTO_SYNC_INTERVAL = timedelta(hours=6)


def _enqueue_due_accounts(db, now: datetime) -> int:
    due = db.scalars(select(SocialAccount).where(
        SocialAccount.status == "connected",
        or_(SocialAccount.last_synced_at.is_(None), SocialAccount.last_synced_at <= now - AUTO_SYNC_INTERVAL),
    ).limit(100)).all()
    created = 0
    for account in due:
        active = db.scalar(select(BrandSyncJob.id).where(
            BrandSyncJob.social_account_id == account.id,
            BrandSyncJob.status.in_(["queued", "running"]),
        ).limit(1))
        recent_attempt = db.scalar(select(BrandSyncJob.id).where(
            BrandSyncJob.social_account_id == account.id,
            BrandSyncJob.created_at >= now - AUTO_SYNC_INTERVAL,
        ).limit(1))
        if active or recent_attempt:
            continue
        membership = db.scalar(select(Membership).where(
            Membership.organization_id == account.organization_id,
            Membership.role.in_(["owner", "admin"]),
        ).order_by(Membership.created_at.asc()))
        if membership is None:
            continue
        job = BrandSyncJob(organization_id=account.organization_id, social_account_id=account.id,
                           requested_by_user_id=membership.user_id, status="queued", attempts=0, max_attempts=3)
        db.add(job)
        db.flush()
        record_activity(db, membership, "brand_intelligence.social_sync_scheduled", "brand_sync_job", job.id,
                        f"Scheduled automatic {account.provider.title()} Brand Intelligence synchronization")
        created += 1
    if created:
        db.commit()
    return created


def _recover_stale_jobs(db, now: datetime) -> int:
    """Requeue interrupted jobs after a worker crash; exhaust bounded attempts safely."""
    stale_before = now - timedelta(minutes=30)
    stale = db.scalars(select(BrandSyncJob).where(
        BrandSyncJob.status == "running", BrandSyncJob.started_at <= stale_before,
    )).all()
    recovered = 0
    for job in stale:
        if job.attempts < job.max_attempts:
            job.status = "queued"
            job.available_at = now
            job.error_message = "Recovered after an interrupted synchronization worker"
            job.finished_at = None
        else:
            job.status = "failed"
            job.error_message = "Synchronization stopped after repeated worker interruptions"
            job.finished_at = now
        recovered += 1
    if recovered:
        db.commit()
    return recovered


def _claim_one(db, now: datetime):
    candidate = db.scalar(select(BrandSyncJob).where(
        BrandSyncJob.status == "queued", BrandSyncJob.available_at <= now,
    ).order_by(BrandSyncJob.created_at.asc()).limit(1))
    if candidate is None:
        return None
    claimed = db.execute(update(BrandSyncJob).where(
        BrandSyncJob.id == candidate.id, BrandSyncJob.status == "queued",
    ).values(status="running", attempts=BrandSyncJob.attempts + 1, started_at=now,
             error_message=None).execution_options(synchronize_session=False))
    db.commit()
    return candidate.id if claimed.rowcount == 1 else None


def process_one() -> bool:
    with SessionLocal() as db:
        job_id = _claim_one(db, datetime.now(timezone.utc))
        if job_id is None:
            return False
        job = db.get(BrandSyncJob, job_id)
        if job is None:
            return True
        account = db.get(SocialAccount, job.social_account_id)
        membership = db.scalar(select(Membership).where(
            Membership.organization_id == job.organization_id,
            Membership.user_id == job.requested_by_user_id,
            Membership.role.in_(["owner", "admin"]),
        ))
        try:
            if account is None or account.status != "connected":
                raise HTTPException(status_code=409, detail="Social account is no longer connected")
            if membership is None:
                raise HTTPException(status_code=403, detail="The requesting workspace administrator is no longer active")
            result = sync_social_account(account.id, membership, db)
            job = db.get(BrandSyncJob, job_id)
            if job is not None:
                job.status, job.result = "succeeded", result
                job.finished_at = datetime.now(timezone.utc)
                job.error_message = None
                db.commit()
        except HTTPException as exc:
            _finish_failure(db, job_id, str(exc.detail), exc.status_code)
        except Exception:
            log.exception("Brand Intelligence sync job %s failed", job_id)
            _finish_failure(db, job_id, "Synchronization failed unexpectedly", 500)
    return True


def _finish_failure(db, job_id, message: str, status_code: int) -> None:
    job = db.get(BrandSyncJob, job_id)
    if job is None:
        return
    now = datetime.now(timezone.utc)
    if status_code >= 500 and job.attempts < job.max_attempts:
        job.status = "queued"
        job.available_at = now + timedelta(minutes=2 ** max(0, job.attempts - 1))
        job.finished_at = None
    else:
        job.status = "failed"
        job.finished_at = now
    job.error_message = message[:1000]
    db.commit()


def run_worker(stop_event: threading.Event, poll_interval: int = 15) -> None:
    log.info("Brand Intelligence sync worker started")
    next_auto_enqueue = datetime.now(timezone.utc)
    while not stop_event.is_set():
        try:
            now = datetime.now(timezone.utc)
            if now >= next_auto_enqueue:
                with SessionLocal() as db:
                    _recover_stale_jobs(db, now)
                    _enqueue_due_accounts(db, now)
                next_auto_enqueue = now + timedelta(minutes=5)
            if not process_one():
                stop_event.wait(max(5, poll_interval))
        except Exception:
            log.exception("Brand Intelligence worker cycle failed")
            stop_event.wait(max(5, poll_interval))
    log.info("Brand Intelligence sync worker stopped")
