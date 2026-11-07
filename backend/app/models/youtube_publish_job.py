"""Durable YouTube resumable-upload and processing records."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, String, LargeBinary, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class YouTubePublishJob(Base):
    __tablename__ = "youtube_publish_jobs"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    video_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    upload_session_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    privacy_status: Mapped[str] = mapped_column(String(16), nullable=False, default="private")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="upload_pending")
    failure_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
