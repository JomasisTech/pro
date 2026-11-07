"""YouTube Data API resumable uploads and processing status."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.organizations import require_roles
from app.config import get_settings
from app.core.database import get_db
from app.integrations.social_crypto import decrypt_token, encrypt_token
from app.models import Membership, SocialAccount, SocialCredential, YouTubePublishJob
from app.modules.audit.activity import record_activity

router = APIRouter(prefix="/organizations/{organization_id}/youtube", tags=["YouTube publishing"])
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_API_URL = "https://www.googleapis.com/youtube/v3/videos"
MAX_VIDEO_SIZE = 256 * 1024 * 1024 * 1024

class YouTubeUploadRequest(BaseModel):
    video_size: int = Field(gt=0, le=MAX_VIDEO_SIZE)
    mime_type: str = Field(pattern=r"^video/(mp4|quicktime|webm|mpeg|3gpp)$")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    privacy_status: str = Field(default="private", pattern=r"^(private|unlisted|public)$")
    made_for_kids: bool
    consent_to_upload: bool


def _account_token(db: Session, org_id: UUID, account_id: UUID) -> tuple[SocialAccount, str]:
    account = db.scalar(select(SocialAccount).where(
        SocialAccount.id == account_id, SocialAccount.organization_id == org_id,
        SocialAccount.provider == "youtube", SocialAccount.status == "connected"))
    if account is None:
        raise HTTPException(status_code=404, detail="Connected YouTube account not found")
    scopes = account.granted_scopes or []
    if not any("youtube.upload" in s for s in scopes):
        raise HTTPException(status_code=403, detail="Reconnect YouTube and grant video upload permission")
    credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
    if credential is None:
        raise HTTPException(status_code=409, detail="YouTube credentials are unavailable; reconnect the account")
    try:
        token = decrypt_token(credential.access_token_encrypted)
        expiry = account.token_expires_at
        if expiry is not None:
            if expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc) + timedelta(minutes=5):
                if not credential.refresh_token_encrypted:
                    raise HTTPException(status_code=409, detail="YouTube authorization expired; reconnect the account")
                settings = get_settings()
                response = httpx.post(GOOGLE_TOKEN_URL, data={
                    "client_id": settings.google_client_id, "client_secret": settings.google_client_secret,
                    "refresh_token": decrypt_token(credential.refresh_token_encrypted), "grant_type": "refresh_token",
                }, timeout=20, follow_redirects=False)
                response.raise_for_status(); body = response.json()
                token = body["access_token"]
                credential.access_token_encrypted = encrypt_token(token)
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(body.get("expires_in", 3600)))
                db.commit()
    except HTTPException: raise
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError):
        db.rollback()
        raise HTTPException(status_code=409, detail="YouTube authorization could not be refreshed; reconnect the account") from None
    return account, token

@router.post("/accounts/{account_id}/upload", status_code=201)
def initialize_youtube_upload(
    organization_id: UUID, account_id: UUID, payload: YouTubeUploadRequest,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    if not payload.consent_to_upload:
        raise HTTPException(status_code=400, detail="Explicit consent is required before sending a video to YouTube")
    account, token = _account_token(db, membership.organization_id, account_id)
    metadata = {"snippet": {"title": payload.title, "description": payload.description,
                             "tags": payload.tags, "categoryId": "22"},
                "status": {"privacyStatus": payload.privacy_status,
                           "selfDeclaredMadeForKids": payload.made_for_kids}}
    try:
        response = httpx.post(YOUTUBE_UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                     "X-Upload-Content-Length": str(payload.video_size), "X-Upload-Content-Type": payload.mime_type},
            json=metadata, timeout=30, follow_redirects=False)
        response.raise_for_status()
        session_url = response.headers.get("Location")
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        raise HTTPException(status_code=429 if code == 429 else 502, detail="YouTube could not initialize the upload. Check channel permissions and try again.") from None
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="YouTube upload session could not be created; try again.") from None
    if not session_url or not session_url.startswith("https://www.googleapis.com/upload/youtube/"):
        raise HTTPException(status_code=502, detail="YouTube returned an invalid resumable upload session")
    job = YouTubePublishJob(organization_id=membership.organization_id, social_account_id=account.id,
        upload_session_encrypted=encrypt_token(session_url), title=payload.title,
        description=payload.description, privacy_status=payload.privacy_status, status="upload_pending")
    db.add(job)
    db.flush()
    record_activity(
        db, membership, "youtube_publish_job.created", "youtube_publish_job", job.id,
        f'Initialized YouTube video upload "{payload.title[:60]}"',
    )
    db.commit()
    db.refresh(job)
    return {"job_id": str(job.id), "upload_url": session_url, "video_size": payload.video_size,
            "chunk_size": 8 * 1024 * 1024, "status": "upload_pending",
            "message": "Upload directly to the secure YouTube resumable session. YouTube must confirm processing before the video is marked complete."}

@router.get("/publish-jobs/{job_id}")
def youtube_publish_status(
    organization_id: UUID, job_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    job = db.scalar(select(YouTubePublishJob).where(YouTubePublishJob.id == job_id,
        YouTubePublishJob.organization_id == membership.organization_id))
    if job is None: raise HTTPException(status_code=404, detail="YouTube publish job not found")
    _, token = _account_token(db, membership.organization_id, job.social_account_id)
    if not job.video_id:
        return {"job_id": str(job.id), "status": job.status, "video_id": None,
                "message": "Upload is not complete yet. Finish or resume the upload from the original browser session."}
    try:
        response = httpx.get(YOUTUBE_API_URL, params={"part": "status,processingDetails,snippet", "id": job.video_id},
            headers={"Authorization": f"Bearer {token}"}, timeout=20, follow_redirects=False)
        response.raise_for_status(); items = response.json().get("items", [])
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not retrieve YouTube processing status; retry shortly") from None
    if not items:
        raise HTTPException(status_code=404, detail="YouTube video status is not available for this account")
    item = items[0]; status = item.get("status", {}); processing = item.get("processingDetails", {})
    previous_status = job.status
    upload_status = status.get("uploadStatus", "uploaded")
    processing_status = processing.get("processingStatus")
    if upload_status in {"failed", "rejected"} or processing_status == "failed":
        job.status = "failed"; job.failure_reason = status.get("failureReason") or status.get("rejectionReason") or processing.get("processingFailureReason")
    elif processing_status == "succeeded" or upload_status == "processed": job.status = "published"
    elif processing_status == "processing": job.status = "processing"
    else: job.status = "uploaded"
    if previous_status != job.status:
        record_activity(
            db, membership, "youtube_publish_job.status_changed", "youtube_publish_job", job.id,
            f'YouTube video upload status changed from {previous_status} to {job.status}',
        )
    db.commit()
    return {"job_id": str(job.id), "status": job.status, "video_id": job.video_id,
            "privacy_status": status.get("privacyStatus"), "upload_status": upload_status,
            "processing_status": processing_status, "failure_reason": job.failure_reason,
            "video_url": f"https://www.youtube.com/watch?v={job.video_id}" if job.status == "published" else None}

@router.post("/publish-jobs/{job_id}/complete")
def complete_youtube_upload(
    organization_id: UUID, job_id: UUID, payload: dict,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    video_id = payload.get("video_id")
    if not isinstance(video_id, str) or not (6 <= len(video_id) <= 32) or not video_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="A valid YouTube video ID is required")
    job = db.scalar(select(YouTubePublishJob).where(YouTubePublishJob.id == job_id,
        YouTubePublishJob.organization_id == membership.organization_id))
    if job is None: raise HTTPException(status_code=404, detail="YouTube publish job not found")
    _, token = _account_token(db, membership.organization_id, job.social_account_id)
    try:
        response = httpx.get(YOUTUBE_API_URL, params={"part": "id", "id": video_id},
            headers={"Authorization": f"Bearer {token}"}, timeout=20, follow_redirects=False)
        response.raise_for_status(); items = response.json().get("items", [])
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not verify the uploaded YouTube video") from None
    if not items or items[0].get("id") != video_id:
        raise HTTPException(status_code=422, detail="YouTube did not confirm this uploaded video")
    previous_status = job.status
    job.video_id = video_id
    job.status = "uploaded"
    if previous_status != job.status:
        record_activity(
            db, membership, "youtube_publish_job.status_changed", "youtube_publish_job", job.id,
            f'YouTube video upload status changed from {previous_status} to uploaded',
        )
    db.commit()
    return {"job_id": str(job.id), "video_id": video_id, "status": "uploaded",
            "message": "YouTube accepted the upload. Processing status will be checked separately."}
