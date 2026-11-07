from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class Membership(Base):
    """Links a user to an organization with an organization-scoped role."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_organization"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member", server_default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")
