"""Organization-scoped scheduling API. Facebook Page text/link is the first dispatch adapter."""
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.api.v1.organizations import get_membership, require_roles
from app.core.database import get_db
from app.core.plans import Metric
from app.models import Membership, ScheduledPost, SocialAccount, MediaAsset, ContentDraft
from app.modules.audit.activity import record_activity
from app.modules.billing.quota import require_quota, record_usage

router = APIRouter(prefix="/organizations/{organization_id}/scheduled-posts", tags=["scheduling"])

class ScheduleCreate(BaseModel):
    draft_id: UUID
    social_account_id: UUID
    provider: str = Field(pattern="^(facebook|instagram|tiktok)$")
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=63206)
    link_url: HttpUrl | None = None
    media_url: HttpUrl | None = None
    media_asset_id: UUID | None = None
    video_duration_seconds: int | None = Field(default=None, gt=0, le=3600)
    privacy_level: str | None = Field(default=None, max_length=40)
    allow_comment: bool = False
    allow_duet: bool = False
    allow_stitch: bool = False
    consent_to_upload: bool = False
    scheduled_at: datetime

class ScheduleReschedule(BaseModel):
    scheduled_at: datetime


class ScheduledPostResponse(BaseModel):
    """Public view of a scheduled post. Worker internals (lease token/expiry, processing start and
    the provider's publish session id) are deliberately not exposed to workspace members."""
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    draft_id: UUID | None
    social_account_id: UUID
    provider: str
    title: str
    content: str
    link_url: str | None
    media_url: str | None
    media_asset_id: UUID | None
    video_duration_seconds: int | None
    privacy_level: str | None
    allow_comment: bool
    allow_duet: bool
    allow_stitch: bool
    consent_to_upload: bool
    consented_at: datetime | None
    consent_version: str | None
    scheduled_at: datetime
    status: str
    attempts: int
    next_attempt_at: datetime | None
    external_post_id: str | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime

def _owned(db: Session, membership: Membership, schedule_id: UUID) -> ScheduledPost:
    item = db.scalar(select(ScheduledPost).where(
        ScheduledPost.id == schedule_id,
        ScheduledPost.organization_id == membership.organization_id,
    ))
    if item is None:
        raise HTTPException(404, "Scheduled post not found")
    return item

@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduledPostResponse)
def create_schedule(payload: ScheduleCreate,
    membership: Membership = Depends(require_roles("owner", "admin")),
    quota_membership: Membership = Depends(require_quota(Metric.SCHEDULED_POSTS)),
    db: Session = Depends(get_db)):
    # Creating a scheduled post is an explicit approval-and-publish action. Only workspace
    # owners/admins may perform it; ordinary members must submit drafts for approval first.
    draft = db.scalar(select(ContentDraft).where(
        ContentDraft.id == payload.draft_id,
        ContentDraft.organization_id == membership.organization_id,
    ))
    if draft is None:
        raise HTTPException(404, "Approved content draft not found in this workspace")
    if draft.status != "approved":
        raise HTTPException(409, "Only an approved content draft can be scheduled")
    if payload.content.strip() != draft.content:
        raise HTTPException(409, "Scheduled content must exactly match the approved draft. Update and re-approve the draft first.")
    if payload.scheduled_at.tzinfo is None:
        raise HTTPException(422, "scheduled_at must include a timezone")
    if payload.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "scheduled_at must be in the future")
    if payload.provider == "instagram":
        if payload.link_url is not None:
            raise HTTPException(422, "Instagram scheduled photo posts do not support link_url")
        if payload.media_url is None or payload.media_url.scheme != "https":
            raise HTTPException(422, "Instagram photo scheduling requires a publicly accessible HTTPS media_url")
    elif payload.provider == "tiktok":
        if len(payload.content) > 2200:
            raise HTTPException(422, "TikTok captions cannot exceed 2,200 characters")
        if payload.media_url is not None or payload.link_url is not None:
            raise HTTPException(422, "TikTok scheduled videos must use an uploaded media_asset_id")
        if payload.media_asset_id is None or payload.video_duration_seconds is None or not payload.privacy_level:
            raise HTTPException(422, "TikTok scheduling requires media_asset_id, video_duration_seconds, and privacy_level")
        if payload.consent_to_upload is not True:
            raise HTTPException(400, "Explicit consent is required before BizPilot Pro sends this video to TikTok")
    elif payload.media_url is not None or payload.media_asset_id is not None:
        raise HTTPException(422, "media is not supported for Facebook scheduled posts")
    account = db.scalar(select(SocialAccount).where(
        SocialAccount.id == payload.social_account_id,
        SocialAccount.organization_id == membership.organization_id,
        SocialAccount.provider == payload.provider,
        SocialAccount.status == "connected",
    ))
    if account is None:
        raise HTTPException(404, f"Connected {payload.provider} account not found")
    if payload.provider == "instagram" and "instagram_business_content_publish" not in (account.granted_scopes or []):
        raise HTTPException(409, "Reconnect Instagram and grant content-publishing permission before scheduling")
    media_asset = None
    if payload.provider == "tiktok":
        if "video.publish" not in (account.granted_scopes or []):
            raise HTTPException(409, "Reconnect TikTok and grant video.publish permission before scheduling")
        media_asset = db.scalar(select(MediaAsset).where(
            MediaAsset.id == payload.media_asset_id,
            MediaAsset.organization_id == membership.organization_id,
        ))
        if media_asset is None:
            raise HTTPException(404, "Organization-owned video asset not found")
        if media_asset.content_type not in {"video/mp4", "video/quicktime", "video/webm"}:
            raise HTTPException(422, "TikTok requires an MP4, QuickTime, or WebM video")
    item = ScheduledPost(
        organization_id=membership.organization_id, draft_id=draft.id, social_account_id=account.id,
        provider=payload.provider, title=payload.title, content=draft.content,
        link_url=str(payload.link_url) if payload.link_url else None,
        media_url=str(payload.media_url) if payload.media_url else None,
        media_asset_id=media_asset.id if media_asset else None,
        video_duration_seconds=payload.video_duration_seconds,
        privacy_level=payload.privacy_level,
        allow_comment=payload.allow_comment, allow_duet=payload.allow_duet, allow_stitch=payload.allow_stitch,
        consent_to_upload=payload.provider == "tiktok" and payload.consent_to_upload,
        consented_at=datetime.now(timezone.utc) if payload.provider == "tiktok" else None,
        consent_version="tiktok-scheduled-upload-v1" if payload.provider == "tiktok" else None,
        scheduled_at=payload.scheduled_at,
    )
    db.add(item)
    db.flush()
    record_activity(db, membership, "scheduled_post.created", "scheduled_post", item.id,
                    f'Scheduled {payload.provider.title()} post "{payload.title[:60]}"')
    db.commit()
    record_usage(db, membership.organization_id, Metric.SCHEDULED_POSTS)
    db.refresh(item)
    return item

@router.get("", response_model=list[ScheduledPostResponse])
def list_schedules(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)):
    return list(db.scalars(select(ScheduledPost).where(
        ScheduledPost.organization_id == membership.organization_id
    ).order_by(ScheduledPost.scheduled_at.asc()).limit(200)).all())

@router.patch("/{schedule_id}/reschedule", response_model=ScheduledPostResponse)
def reschedule(schedule_id: UUID, payload: ScheduleReschedule,
    membership: Membership = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)):
    item = _owned(db, membership, schedule_id)
    if item.status != "queued":
        raise HTTPException(409, "Only queued posts can be rescheduled")
    if payload.scheduled_at.tzinfo is None or payload.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(422, "scheduled_at must be a future timezone-aware datetime")
    # Compare-and-set on status: a worker may have claimed the post since it was loaded above.
    changed = db.execute(update(ScheduledPost).where(
        ScheduledPost.id == item.id, ScheduledPost.organization_id == membership.organization_id,
        ScheduledPost.status == "queued",
    ).values(scheduled_at=payload.scheduled_at))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Only queued posts can be rescheduled")
    record_activity(db, membership, "scheduled_post.rescheduled", "scheduled_post", item.id,
                    f'Rescheduled {item.provider.title()} post "{item.title[:60]}"')
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_schedule(schedule_id: UUID, membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db)):
    item = _owned(db, membership, schedule_id)
    if item.status != "queued":
        raise HTTPException(409, "Only queued posts can be cancelled")
    # Compare-and-set on status so a post a worker has just claimed is never overwritten as cancelled.
    changed = db.execute(update(ScheduledPost).where(
        ScheduledPost.id == item.id, ScheduledPost.organization_id == membership.organization_id,
        ScheduledPost.status == "queued",
    ).values(status="cancelled"))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Only queued posts can be cancelled")
    record_activity(db, membership, "scheduled_post.cancelled", "scheduled_post", item.id,
                    f'Cancelled {item.provider.title()} post "{item.title[:60]}"')
    db.commit()
    return None
