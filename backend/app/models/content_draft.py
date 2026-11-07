from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class ContentDraft(Base):
    """A saved piece of content (currently a caption) owned by one organization."""

    __tablename__ = "content_drafts"
    __table_args__ = (Index("ix_content_drafts_org_created", "organization_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False, default="general", server_default="general")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft", server_default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
