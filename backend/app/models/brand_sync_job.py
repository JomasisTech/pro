from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BrandSyncJob(Base):
    """Durable, retryable request to synchronize one connected social account."""

    __tablename__ = "brand_sync_jobs"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
