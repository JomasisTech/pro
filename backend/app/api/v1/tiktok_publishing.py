"""TikTok creator settings, Direct Post initialization and publish-status tracking.

Video bytes travel directly from the user's browser to TikTok's short-lived upload URL;
BizPilot Pro never receives or stores the media file or exposes the TikTok access token.
"""
from datetime import datetime, timedelta, timezone
from math import ceil
from uuid import UUID
from urllib.parse import urlparse
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.v1.organizations import require_roles
from app.config import get_settings
from app.core.database import get_db
from app.integrations.social_crypto import decrypt_token, encrypt_token
from app.models import Membership, SocialAccount, SocialCredential, TikTokPublishJob
from app.modules.audit.activity import record_activity

router = APIRouter(prefix="/organizations/{organization_id}/tiktok", tags=["TikTok publishing"])
API = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 1024 * 1024 * 1024

class DirectPostRequest(BaseModel):
    video_size: int = Field(gt=0, le=MAX_VIDEO_SIZE)
    duration_seconds: int = Field(gt=0, le=3600)
    caption: str = Field(default="", max_length=2200)
    privacy_level: str = Field(min_length=1, max_length=40)
    allow_comment: bool = False
    allow_duet: bool = False
    allow_stitch: bool = False
    consent_to_upload: bool


def _account_and_token(db: Session, organization_id: UUID, account_id: UUID) -> tuple[SocialAccount, str]:
    account = db.scalar(select(SocialAccount).where(
        SocialAccount.id == account_id, SocialAccount.organization_id == organization_id,
        SocialAccount.provider == "tiktok", SocialAccount.status == "connected",
    ))
    if account is None:
        raise HTTPException(status_code=404, detail="Connected TikTok account not found")
    if "video.publish" not in (account.granted_scopes or []):
        raise HTTPException(status_code=403, detail="Reconnect TikTok and grant video.publish permission")
    credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
    if credential is None:
        raise HTTPException(status_code=409, detail="TikTok credentials are unavailable; reconnect the account")
    try:
        token = decrypt_token(credential.access_token_encrypted)
        expiry = account.token_expires_at
        if expiry is not None:
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if expiry <= datetime.now(timezone.utc) + timedelta(minutes=5):
                if not credential.refresh_token_encrypted:
                    raise HTTPException(status_code=409, detail="TikTok authorization expired; reconnect the account")
                settings = get_settings()
                refresh_token = decrypt_token(credential.refresh_token_encrypted)
                response = httpx.post("https://open.tiktokapis.com/v2/oauth/token/", data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                }, timeout=20.0, follow_redirects=False)
                response.raise_for_status()
                body = response.json()
                body = body.get("data", body)
                refreshed = body.get("access_token")
                if not isinstance(refreshed, str) or not refreshed:
                    raise ValueError("TikTok did not return a refreshed access token")
                token = refreshed
                credential.access_token_encrypted = encrypt_token(refreshed)
                if body.get("refresh_token"):
                    credential.refresh_token_encrypted = encrypt_token(body["refresh_token"])
                account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, int(body.get("expires_in") or 86400)))
                db.commit()
    except HTTPException:
        raise
    except (RuntimeError, httpx.HTTPError, ValueError, TypeError, KeyError):
        db.rollback()
        raise HTTPException(status_code=409, detail="TikTok authorization could not be refreshed; reconnect the account") from None
    return account, token


def _post(path: str, token: str, payload: dict | None = None) -> dict:
    try:
        response = httpx.post(f"{API}{path}", headers={
            "Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
        }, json=payload or {}, timeout=25.0, follow_redirects=False)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="TikTok could not complete the request; try again later") from None
    error = body.get("error", {})
    if error.get("code") != "ok":
        code = str(error.get("code") or "provider_error")
        if code in {"access_token_invalid", "scope_not_authorized"}:
            raise HTTPException(status_code=409, detail="TikTok authorization expired or lacks publishing permission; reconnect the account")
        if code in {"spam_risk_too_many_posts", "spam_risk_user_banned_from_posting", "reached_active_user_cap"}:
            raise HTTPException(status_code=429, detail="TikTok is not accepting another post for this account right now")
        raise HTTPException(status_code=502, detail="TikTok rejected the request; review the video and account settings")
    return body.get("data", {})

@router.get("/accounts/{account_id}/creator-info")
def creator_info(
    organization_id: UUID, account_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    _, token = _account_and_token(db, membership.organization_id, account_id)
    data = _post("/post/publish/creator_info/query/", token)
    return {
        "creator_username": data.get("creator_username"),
        "creator_nickname": data.get("creator_nickname"),
        "privacy_level_options": data.get("privacy_level_options", []),
        "comment_disabled": bool(data.get("comment_disabled", False)),
        "duet_disabled": bool(data.get("duet_disabled", False)),
        "stitch_disabled": bool(data.get("stitch_disabled", False)),
        "max_video_post_duration_sec": data.get("max_video_post_duration_sec"),
    }

@router.post("/accounts/{account_id}/direct-post", status_code=201)
def initialize_direct_post(
    organization_id: UUID, account_id: UUID, payload: DirectPostRequest,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    if payload.consent_to_upload is not True:
        raise HTTPException(status_code=400, detail="Explicit consent is required before sending a video to TikTok")
    account, token = _account_and_token(db, membership.organization_id, account_id)
    creator = _post("/post/publish/creator_info/query/", token)
    privacy_options = creator.get("privacy_level_options") or []
    from app.config import get_settings
    settings = get_settings()
    allowed_privacy = privacy_options if settings.tiktok_content_posting_audited else ["SELF_ONLY"]
    if payload.privacy_level not in allowed_privacy:
        raise HTTPException(status_code=422, detail="Choose a privacy option currently allowed by this TikTok account")
    max_duration = creator.get("max_video_post_duration_sec")
    if not max_duration:
        raise HTTPException(status_code=409, detail="TikTok did not return the creator's video-duration limit")
    if payload.duration_seconds > int(max_duration):
        raise HTTPException(status_code=422, detail="This video exceeds the duration limit for the connected TikTok account")
    post_info = {
        "title": payload.caption,
        "privacy_level": payload.privacy_level,
        "disable_comment": not payload.allow_comment or bool(creator.get("comment_disabled")),
        "disable_duet": not payload.allow_duet or bool(creator.get("duet_disabled")),
        "disable_stitch": not payload.allow_stitch or bool(creator.get("stitch_disabled")),
    }
    chunk_size = min(CHUNK_SIZE, payload.video_size)
    total_chunks = ceil(payload.video_size / chunk_size)
    data = _post("/post/publish/video/init/", token, {
        "post_info": post_info,
        "source_info": {"source": "FILE_UPLOAD", "video_size": payload.video_size,
                        "chunk_size": chunk_size, "total_chunk_count": total_chunks},
    })
    publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
    parsed_upload_url = urlparse(upload_url) if isinstance(upload_url, str) else None
    if not isinstance(publish_id, str) or parsed_upload_url is None or parsed_upload_url.scheme != "https" or parsed_upload_url.hostname != "open-upload.tiktokapis.com":
        raise HTTPException(status_code=502, detail="TikTok returned an invalid upload session")
    job = TikTokPublishJob(
        organization_id=membership.organization_id, social_account_id=account.id,
        publish_id=publish_id, caption=payload.caption, privacy_level=payload.privacy_level,
        status="upload_pending",
    )
    db.add(job)
    db.flush()
    record_activity(
        db, membership, "tiktok_publish_job.created", "tiktok_publish_job", job.id,
        f'Initialized TikTok video post for "{account.account_name[:60]}"',
    )
    db.commit()
    db.refresh(job)
    return {"job_id": str(job.id), "publish_id": publish_id, "upload_url": upload_url,
            "chunk_size": chunk_size, "total_chunk_count": total_chunks,
            "upload_method": "PUT", "message": "Upload the video bytes to TikTok using the returned upload URL. Publishing is not complete until TikTok confirms it."}

@router.get("/publish-jobs/{job_id}")
def get_publish_status(
    organization_id: UUID, job_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db),
) -> dict:
    job = db.scalar(select(TikTokPublishJob).where(
        TikTokPublishJob.id == job_id, TikTokPublishJob.organization_id == membership.organization_id,
    ))
    if job is None:
        raise HTTPException(status_code=404, detail="TikTok publish job not found")
    _, token = _account_and_token(db, membership.organization_id, job.social_account_id)
    data = _post("/post/publish/status/fetch/", token, {"publish_id": job.publish_id})
    raw_status = str(data.get("status") or "PROCESSING")
    normalized = {
        "PUBLISH_COMPLETE": "published", "FAILED": "failed",
        "PROCESSING_UPLOAD": "uploading", "PROCESSING_DOWNLOAD": "processing",
        "SEND_TO_USER_INBOX": "sent_to_inbox",
    }.get(raw_status, "processing")
    previous_status = job.status
    job.status = normalized
    job.provider_status = {"status": raw_status, "fail_reason": data.get("fail_reason"),
                           "publicly_available_post_id": data.get("publicly_available_post_id")}
    if previous_status != normalized:
        record_activity(
            db, membership, "tiktok_publish_job.status_changed", "tiktok_publish_job", job.id,
            f'TikTok video post status changed from {previous_status} to {normalized}',
        )
    db.commit()
    return {"job_id": str(job.id), "status": normalized, "provider_status": raw_status,
            "failure_reason": data.get("fail_reason"), "published": normalized == "published"}
