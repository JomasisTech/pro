"""Single-use, expiring invitations to join an organization."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid
from app.core.database import Base

class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    organization: Mapped["Organization"] = relationship()
    invited_by: Mapped["User"] = relationship()
