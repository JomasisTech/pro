from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class ActivityLog(Base):
    """Append-only record of who did what inside an organization. Never edited or deleted by the app."""

    __tablename__ = "activity_logs"
    __table_args__ = (Index("ix_activity_logs_org_created", "organization_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    # The user can be deleted later; actor_name keeps the name as it was at the time.
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[str] = mapped_column(String(160), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "draft.deleted"
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # No foreign key on purpose: the log must outlive the thing that was deleted.
    entity_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    summary: Mapped[str] = mapped_column(String(400), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
