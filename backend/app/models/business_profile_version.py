from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BusinessProfileVersion(Base):
    """Immutable snapshot of a profile change or user confirmation."""

    __tablename__ = "business_profile_versions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now())
