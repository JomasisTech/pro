"""Small database-backed dispatcher. Invoke periodically with `python -m app.modules.posting.dispatcher`.

Facebook Page text/link posts and Instagram professional-account single-photo posts are supported.
Instagram media URLs must be public HTTPS URLs so Meta can fetch the image asynchronously.
"""
from datetime import datetime, timedelta, timezone
import logging
import threading
from uuid import uuid4
from pathlib import Path
import httpx
from sqlalchemy import case, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.integrations.social_crypto import decrypt_token
from app.config import get_settings
from app.modules.posting.tiktok_upload import upload_video_file, DEFAULT_CHUNK_SIZE
from app.models import ScheduledPost, SocialAccount, SocialCredential, CalendarEntry, MediaAsset

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v26.0"
INSTAGRAM_GRAPH = "https://graph.instagram.com/v26.0"
MAX_ATTEMPTS = 3
PROCESSING_LEASE = timedelta(minutes=60)
LEASE_HEARTBEAT_INTERVAL_SECONDS = 30
RETRY_BASE_SECONDS = 60
RETRY_MAX_SECONDS = 3600


class AmbiguousPublishResponseError(RuntimeError):
    """The provider accepted a publish request but did not return a usable post ID."""


def _start_lease_heartbeat(job_id, lease_token):
    """Renew a claimed job lease in an independent session while provider I/O is running."""
    stopped = threading.Event()

    def renew():
        while not stopped.wait(LEASE_HEARTBEAT_INTERVAL_SECONDS):
            try:
                with SessionLocal() as heartbeat_db:
                    result = heartbeat_db.execute(update(ScheduledPost).where(
                        ScheduledPost.id == job_id,
                        ScheduledPost.lease_token == lease_token,
                        ScheduledPost.status == "processing",
                    ).values(
                        lease_expires_at=datetime.now(timezone.utc) + PROCESSING_LEASE,
                        processing_started_at=datetime.now(timezone.utc),
                    ))
                    heartbeat_db.commit()
                    if result.rowcount != 1:
                        log.warning("Lost scheduler lease for job %s; heartbeat stopped", job_id)
                        stopped.set()
            except Exception:
                log.exception("Could not renew scheduler lease for job %s", job_id)
                stopped.set()

    thread = threading.Thread(target=renew, name=f"schedule-lease-{job_id}", daemon=True)
    thread.start()
    return stopped, thread


def _publish_outcome_is_ambiguous(exc: Exception) -> bool:
    """Treat every post-request failure except an explicit provider 4xx as uncertain.

    A timeout, 5xx, malformed success response, missing post ID, or local persistence
    failure can happen after the provider accepted the post. Retrying any of those
    outcomes automatically risks creating a duplicate. Explicit 4xx responses are
    treated as definitive provider rejections.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(
        exc,
        (httpx.TransportError, ValueError, KeyError, TypeError, SQLAlchemyError, AmbiguousPublishResponseError),
    )


def dispatch_due(db: Session, *, now: datetime | None = None, limit: int = 20) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    # Requeue jobs abandoned by a crashed worker after their 60-minute lease expires.
    stale_before = now - PROCESSING_LEASE
    stale_lease = (
        ScheduledPost.status == "processing",
        or_(
            ScheduledPost.lease_expires_at <= now,
            (ScheduledPost.lease_expires_at.is_(None))
            & ScheduledPost.processing_started_at.is_not(None)
            & (ScheduledPost.processing_started_at <= stale_before),
        ),
    )
    db.execute(update(ScheduledPost).where(
        *stale_lease, ScheduledPost.attempts >= MAX_ATTEMPTS,
    ).values(status="failed", processing_started_at=None, lease_token=None, lease_expires_at=None, next_attempt_at=None,
             last_error="Worker lease expired after the final allowed attempt"))
    db.execute(update(ScheduledPost).where(
        *stale_lease, ScheduledPost.attempts < MAX_ATTEMPTS,
    ).values(status="queued", processing_started_at=None, lease_token=None, lease_expires_at=None, next_attempt_at=now))
    db.commit()
    due = db.scalars(select(ScheduledPost).where(
        ScheduledPost.status.in_(["queued", "publishing"]), ScheduledPost.scheduled_at <= now,
        or_(ScheduledPost.next_attempt_at.is_(None), ScheduledPost.next_attempt_at <= now),
    ).order_by(ScheduledPost.scheduled_at.asc()).limit(limit)).all()
    counts = {"published": 0, "retrying": 0, "failed": 0}
    for job in due:
        # Atomic compare-and-set prevents two workers from dispatching the same row.
        lease_token = uuid4()
        claimed = db.execute(update(ScheduledPost).where(
            ScheduledPost.id == job.id, ScheduledPost.status.in_(["queued", "publishing"])
        ).values(status="processing", processing_started_at=now,
                 lease_token=lease_token, lease_expires_at=now + PROCESSING_LEASE,
                 attempts=ScheduledPost.attempts + case((ScheduledPost.status == "queued", 1), else_=0)))
        db.commit()
        if claimed.rowcount != 1:
            continue
        job = db.get(ScheduledPost, job.id)
        heartbeat_stop, heartbeat_thread = _start_lease_heartbeat(job.id, lease_token)
        publish_request_started = False
        try:
            account = db.scalar(select(SocialAccount).where(
                SocialAccount.id == job.social_account_id,
                SocialAccount.organization_id == job.organization_id,
                SocialAccount.provider == job.provider,
                SocialAccount.status == "connected",
            ))
            if account is None or job.provider not in {"facebook", "instagram", "tiktok"}:
                raise RuntimeError("The scheduled provider account is unavailable")
            credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
            if credential is None:
                raise RuntimeError("Provider credentials are unavailable; reconnect the account")
            if job.provider == "instagram":
                from app.integrations.instagram_tokens import get_instagram_access_token
                token = get_instagram_access_token(db, account, credential, now=now)
            else:
                token = decrypt_token(credential.access_token_encrypted)
            if job.provider == "tiktok":
                if not job.consent_to_upload or not job.consented_at or not job.consent_version:
                    raise RuntimeError("TikTok upload consent is missing; cancel and recreate this scheduled post with explicit consent")
                if "video.publish" not in (account.granted_scopes or []):
                    raise RuntimeError("TikTok video.publish permission is missing; reconnect the account")
                # Reuse the existing server-side token refresh and provider response handling.
                from app.api.v1.tiktok_publishing import _account_and_token, _post
                account, token = _account_and_token(db, job.organization_id, account.id)
                if job.provider_publish_id:
                    data = _post("/post/publish/status/fetch/", token, {"publish_id": job.provider_publish_id})
                    raw = str(data.get("status") or "PROCESSING_DOWNLOAD")
                    if raw == "PUBLISH_COMPLETE":
                        post_id = str(data.get("publicly_available_post_id") or job.provider_publish_id)
                    elif raw == "FAILED":
                        # The previous session is definitively unusable. Clear it so the next
                        # bounded retry creates a fresh upload session instead of polling it forever.
                        job.provider_publish_id = None
                        db.commit()
                        raise RuntimeError(str(data.get("fail_reason") or "TikTok reported that publishing failed"))
                    elif raw == "PROCESSING_UPLOAD":
                        # A worker may have died mid-transfer. No worker can resume the old
                        # in-memory stream, so abandon this incomplete session and initialize
                        # a fresh one on the next attempt. PROCESSING_DOWNLOAD is polled below.
                        job.provider_publish_id = None
                        job.status = "queued"
                        job.processing_started_at = None
                        job.lease_token = None
                        job.lease_expires_at = None
                        job.next_attempt_at = now + timedelta(seconds=RETRY_BASE_SECONDS)
                        job.last_error = "Previous TikTok upload session was interrupted; preparing a fresh session"
                        db.commit()
                        counts["retrying"] += 1
                        continue
                    else:
                        job.status = "publishing"
                        job.processing_started_at = None
                        job.lease_token = None
                        job.lease_expires_at = None
                        job.next_attempt_at = now + timedelta(seconds=60)
                        job.last_error = None
                        job.provider_publish_id = job.provider_publish_id
                        db.commit()
                        continue
                else:
                    asset = db.scalar(select(MediaAsset).where(
                        MediaAsset.id == job.media_asset_id,
                        MediaAsset.organization_id == job.organization_id,
                    )) if job.media_asset_id else None
                    if asset is None:
                        raise RuntimeError("Scheduled TikTok video asset is unavailable")
                    path = Path(get_settings().media_storage_dir) / asset.storage_key
                    if not path.is_file() or path.stat().st_size != asset.size_bytes:
                        raise RuntimeError("Stored TikTok video is missing or its size no longer matches")
                    if asset.size_bytes < 5 * 1024 * 1024:
                        raise RuntimeError("TikTok requires upload chunks of at least 5 MB; this video is too small for the configured upload method")
                    creator = _post("/post/publish/creator_info/query/", token)
                    privacy_options = creator.get("privacy_level_options") or []
                    settings = get_settings()
                    allowed = privacy_options if settings.tiktok_content_posting_audited else ["SELF_ONLY"]
                    if job.privacy_level not in allowed:
                        raise RuntimeError("The scheduled TikTok privacy setting is no longer allowed by the creator account")
                    max_duration = creator.get("max_video_post_duration_sec")
                    if not max_duration or int(job.video_duration_seconds or 0) > int(max_duration):
                        raise RuntimeError("The scheduled TikTok video exceeds the creator account duration limit")
                    chunk_size = min(DEFAULT_CHUNK_SIZE, asset.size_bytes)
                    total_chunks = (asset.size_bytes + chunk_size - 1) // chunk_size
                    init = _post("/post/publish/video/init/", token, {
                        "post_info": {"title": job.content, "privacy_level": job.privacy_level,
                                      "disable_comment": not job.allow_comment or bool(creator.get("comment_disabled")),
                                      "disable_duet": not job.allow_duet or bool(creator.get("duet_disabled")),
                                      "disable_stitch": not job.allow_stitch or bool(creator.get("stitch_disabled"))},
                        "source_info": {"source": "FILE_UPLOAD", "video_size": asset.size_bytes,
                                        "chunk_size": chunk_size, "total_chunk_count": total_chunks},
                    })
                    publish_id, upload_url = init.get("publish_id"), init.get("upload_url")
                    if not publish_id or not upload_url:
                        raise RuntimeError("TikTok did not return a publish ID and upload URL")
                    job.provider_publish_id = str(publish_id)
                    db.commit()
                    upload_video_file(upload_url, path, asset.content_type, chunk_size=chunk_size)
                    data = _post("/post/publish/status/fetch/", token, {"publish_id": str(publish_id)})
                    raw = str(data.get("status") or "PROCESSING_DOWNLOAD")
                    if raw == "PUBLISH_COMPLETE":
                        post_id = str(data.get("publicly_available_post_id") or publish_id)
                    elif raw == "FAILED":
                        raise RuntimeError(str(data.get("fail_reason") or "TikTok reported that publishing failed"))
                    else:
                        job.status = "publishing"
                        job.processing_started_at = None
                        job.lease_token = None
                        job.lease_expires_at = None
                        job.next_attempt_at = now + timedelta(seconds=60)
                        job.last_error = None
                        db.commit()
                        continue
            else:
                with httpx.Client(timeout=45, follow_redirects=False) as client:
                    if job.provider == "facebook":
                        payload = {"message": job.content, "access_token": token}
                        if job.link_url:
                            payload["link"] = job.link_url
                        publish_request_started = True
                        response = client.post(f"{GRAPH}/{account.provider_account_id}/feed", data=payload)
                        response.raise_for_status()
                        post_id = response.json().get("id")
                    else:
                        if "instagram_business_content_publish" not in (account.granted_scopes or []):
                            raise RuntimeError("Instagram content-publishing permission is missing; reconnect the account")
                        if not job.media_url or not job.media_url.startswith("https://"):
                            raise RuntimeError("Instagram photo post requires a public HTTPS media URL")
                        container = client.post(f"{INSTAGRAM_GRAPH}/{account.provider_account_id}/media", data={
                            "image_url": job.media_url, "caption": job.content, "access_token": token,
                        })
                        container.raise_for_status()
                        creation_id = container.json().get("id")
                        if not creation_id:
                            raise RuntimeError("Instagram did not return a media container identifier")
                        publish_request_started = True
                        published = client.post(f"{INSTAGRAM_GRAPH}/{account.provider_account_id}/media_publish", data={
                            "creation_id": creation_id, "access_token": token,
                        })
                        published.raise_for_status()
                        post_id = published.json().get("id")
            owns_lease = db.scalar(select(ScheduledPost.id).where(
                ScheduledPost.id == job.id,
                ScheduledPost.status == "processing",
                ScheduledPost.lease_token == lease_token,
            ))
            if owns_lease is None:
                log.error("Worker lost lease for scheduled post %s after provider processing", job.id)
                continue
            if not post_id:
                raise AmbiguousPublishResponseError("The provider did not confirm a post identifier")
            db.add(CalendarEntry(
                organization_id=job.organization_id, social_account_id=account.id,
                provider=job.provider, title=job.title, content=job.content,
                external_post_id=str(post_id), status="published", scheduled_at=job.scheduled_at,
            ))
            job.external_post_id = str(post_id)
            job.status = "published"
            job.last_error = None
            job.next_attempt_at = None
            job.processing_started_at = None
            job.lease_token = None
            job.lease_expires_at = None
            db.commit()
            counts["published"] += 1
        except Exception as exc:  # Provider errors are persisted; the worker continues with other jobs.
            db.rollback()
            job = db.get(ScheduledPost, job.id)
            if job is None:
                continue
            if job.lease_token != lease_token:
                log.warning("Skipping stale-worker error update for scheduled post %s", job.id)
                continue
            ambiguous = publish_request_started and _publish_outcome_is_ambiguous(exc)
            if ambiguous:
                # The provider may have accepted the post even though our request timed out
                # or returned a server error. Never blindly retry an uncertain publish.
                job.status = "failed"
                job.last_error = (
                    "Provider outcome is uncertain after a network/server error. Verify the post "
                    "on the social account before creating a replacement."
                )
                job.next_attempt_at = None
            else:
                job.last_error = str(exc)[:500]
                job.status = "queued" if job.attempts < MAX_ATTEMPTS else "failed"
                if job.status == "queued":
                    delay = min(RETRY_BASE_SECONDS * (2 ** max(0, job.attempts - 1)), RETRY_MAX_SECONDS)
                    job.next_attempt_at = now + timedelta(seconds=delay)
                else:
                    job.next_attempt_at = None
            job.processing_started_at = None
            job.lease_token = None
            job.lease_expires_at = None
            db.commit()
            counts["retrying" if job.status == "queued" else "failed"] += 1
            log.warning("Scheduled post %s failed on attempt %s: %s", job.id, job.attempts, exc)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2)
    return counts

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        print(dispatch_due(session))
