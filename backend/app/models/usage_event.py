from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UsageEvent(Base):
    """One billable/limited action by an organization (e.g. one AI caption). Counted per month against its plan."""

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_org_metric_created", "organization_id", "metric", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now()
    )
