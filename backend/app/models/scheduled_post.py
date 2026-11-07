"""Durable provider-neutral schedule records for the posting dispatcher."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class ScheduledPost(Base):
    __tablename__ = "scheduled_posts"
    __table_args__ = (Index("ix_scheduled_posts_due", "status", "scheduled_at"),
                      Index("ix_scheduled_posts_retry", "status", "next_attempt_at"),
                      Index("ix_scheduled_posts_org", "organization_id", "created_at"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    draft_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("content_drafts.id", ondelete="RESTRICT"), nullable=True, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    media_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    media_asset_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("media_assets.id", ondelete="RESTRICT"), nullable=True, index=True)
    video_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    privacy_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    allow_comment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    allow_duet: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    allow_stitch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consent_to_upload: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_publish_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Unique owner token prevents a stale worker from renewing a lease claimed by another worker.
    lease_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    external_post_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
