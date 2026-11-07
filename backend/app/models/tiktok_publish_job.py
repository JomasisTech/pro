"""Durable TikTok Content Posting API tracking records."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class TikTokPublishJob(Base):
    __tablename__ = "tiktok_publish_jobs"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    publish_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    caption: Mapped[str] = mapped_column(Text, nullable=False, default="")
    privacy_level: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="upload_pending")
    provider_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
