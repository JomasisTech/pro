from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import BrandSyncJob, Membership, Organization, SocialAccount, User


def test_worker_processes_queued_job_and_persists_result(session_factory, monkeypatch):
    from app.modules.brand_intelligence import worker

    with session_factory() as db:
        user = User(email="worker-owner@example.com", full_name="Worker Owner", password_hash="hash")
        db.add(user)
        db.flush()
        org = Organization(name="Worker Org", slug=f"worker-{uuid4().hex[:8]}")
        db.add(org)
        db.flush()
        membership = Membership(user_id=user.id, organization_id=org.id, role="owner")
        account = SocialAccount(organization_id=org.id, provider="instagram", provider_account_id="ig-worker", account_name="@worker")
        db.add_all([membership, account])
        db.flush()
        job = BrandSyncJob(organization_id=org.id, social_account_id=account.id,
                           requested_by_user_id=user.id, status="queued", attempts=0, max_attempts=3,
                           available_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        db.add(job)
        db.commit()
        job_id = job.id

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    monkeypatch.setattr(worker, "sync_social_account", lambda account_id, membership, db: {
        "provider": "instagram", "retrieved": 2, "inserted": 2, "updated": 0,
    })
    assert worker.process_one() is True
    with session_factory() as db:
        job = db.get(BrandSyncJob, job_id)
        assert job.status == "succeeded"
        assert job.attempts == 1
        assert job.result["retrieved"] == 2
        assert job.finished_at is not None


def test_worker_retries_transient_failure_with_backoff(session_factory, monkeypatch):
    from app.modules.brand_intelligence import worker

    with session_factory() as db:
        user = User(email="retry-owner@example.com", full_name="Retry Owner", password_hash="hash")
        db.add(user)
        db.flush()
        org = Organization(name="Retry Org", slug=f"retry-{uuid4().hex[:8]}")
        db.add(org)
        db.flush()
        membership = Membership(user_id=user.id, organization_id=org.id, role="owner")
        account = SocialAccount(organization_id=org.id, provider="instagram", provider_account_id="ig-retry", account_name="@retry")
        db.add_all([membership, account])
        db.flush()
        job = BrandSyncJob(organization_id=org.id, social_account_id=account.id,
                           requested_by_user_id=user.id, status="queued", attempts=0, max_attempts=3,
                           available_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        db.add(job)
        db.commit()
        job_id = job.id

    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    from fastapi import HTTPException
    monkeypatch.setattr(worker, "sync_social_account", lambda *args: (_ for _ in ()).throw(HTTPException(status_code=502, detail="provider unavailable")))
    assert worker.process_one() is True
    with session_factory() as db:
        job = db.get(BrandSyncJob, job_id)
        assert job.status == "queued"
        assert job.attempts == 1
        assert job.error_message == "provider unavailable"
        assert job.available_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)


def test_worker_recovers_stale_running_job_after_restart(session_factory):
    from app.modules.brand_intelligence.worker import _recover_stale_jobs

    with session_factory() as db:
        user = User(email="stale-owner@example.com", full_name="Stale Owner", password_hash="hash")
        db.add(user)
        db.flush()
        org = Organization(name="Stale Org", slug=f"stale-{uuid4().hex[:8]}")
        db.add(org)
        db.flush()
        account = SocialAccount(organization_id=org.id, provider="youtube", provider_account_id="yt-stale", account_name="Channel")
        db.add(account)
        db.flush()
        job = BrandSyncJob(organization_id=org.id, social_account_id=account.id,
                           requested_by_user_id=user.id, status="running", attempts=1, max_attempts=3,
                           started_at=datetime.now(timezone.utc) - timedelta(minutes=45))
        db.add(job)
        db.commit()
        job_id = job.id
        assert _recover_stale_jobs(db, datetime.now(timezone.utc)) == 1
        recovered = db.get(BrandSyncJob, job_id)
        assert recovered.status == "queued"
        assert recovered.error_message.startswith("Recovered after")
