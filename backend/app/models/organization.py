from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class Organization(Base):
    """A tenant boundary for customer-owned AutoBizPro data."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    # Subscription plan key; limits for each plan live in app/core/plans.py. Only trusted server code
    # (future billing webhooks, admin tools) may change this, never a user-facing endpoint.
    plan: Mapped[str] = mapped_column(String(32), nullable=False, default="free", server_default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
