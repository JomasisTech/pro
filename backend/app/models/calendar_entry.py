from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class CalendarEntry(Base):
    """Provider-backed scheduled or published content surfaced in the unified calendar."""
    __tablename__ = "calendar_entries"
    __table_args__ = (Index("ix_calendar_entries_org_scheduled", "organization_id", "scheduled_at"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    external_post_id: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="scheduled", server_default="scheduled")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
