"""Independent YouTube processing-status poller.

Run with ``python -m app.modules.posting.youtube_worker`` from the backend directory.
This worker deliberately polls only uploads whose browser upload has already been
verified and whose YouTube video ID is durable in the database.
"""
from __future__ import annotations

import logging
from collections import Counter

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.youtube_publishing import YOUTUBE_API_URL, _account_token
from app.core.database import SessionLocal
from app.models import SocialAccount, YouTubePublishJob

log = logging.getLogger(__name__)


def _derive_status(item: dict) -> tuple[str, str | None]:
    status = item.get("status") or {}
    processing = item.get("processingDetails") or {}
    upload_status = status.get("uploadStatus", "uploaded")
    processing_status = processing.get("processingStatus")
    if upload_status in {"failed", "rejected"} or processing_status == "failed":
        reason = (status.get("failureReason") or status.get("rejectionReason")
                  or processing.get("processingFailureReason") or "YouTube processing failed")
        return "failed", str(reason)[:100]
    if processing_status == "succeeded" or upload_status == "processed":
        return "published", None
    if processing_status == "processing":
        return "processing", None
    return "uploaded", None


def poll_youtube_processing(db: Session, *, limit: int = 50) -> dict[str, int]:
    """Poll durable uploaded/processing jobs without requiring an open browser."""
    counts: Counter[str] = Counter()
    jobs = db.scalars(
        select(YouTubePublishJob)
        .where(YouTubePublishJob.video_id.is_not(None),
               YouTubePublishJob.status.in_(["uploaded", "processing"]))
        .order_by(YouTubePublishJob.updated_at.asc())
        .limit(limit)
    ).all()
    for job in jobs:
        try:
            account = db.scalar(select(SocialAccount).where(
                SocialAccount.id == job.social_account_id,
                SocialAccount.organization_id == job.organization_id,
                SocialAccount.provider == "youtube",
                SocialAccount.status == "connected",
            ))
            if account is None:
                job.status = "failed"
                job.failure_reason = "YouTube account is disconnected"
                counts["failed"] += 1
                db.commit()
                continue
            _, token = _account_token(db, job.organization_id, account.id)
            response = httpx.get(
                YOUTUBE_API_URL,
                params={"part": "status,processingDetails", "id": job.video_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
                follow_redirects=False,
            )
            response.raise_for_status()
            items = response.json().get("items", [])
            if not items or items[0].get("id") != job.video_id:
                # A missing result can be transient; do not turn it into a false failure.
                counts["unavailable"] += 1
                continue
            next_status, reason = _derive_status(items[0])
            job.status = next_status
            job.failure_reason = reason
            db.commit()
            counts[next_status] += 1
        except (httpx.HTTPError, HTTPException, ValueError, KeyError, TypeError, RuntimeError) as exc:
            db.rollback()
            counts["errors"] += 1
            log.warning("Could not poll YouTube job %s: %s", job.id, exc)
    return {key: counts[key] for key in ("published", "processing", "uploaded", "failed", "unavailable", "errors")}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        print(poll_youtube_processing(session))
