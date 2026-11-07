from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class SocialAccount(Base):
    """Organization-owned social account metadata; OAuth credentials are stored separately."""

    __tablename__ = "social_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "provider", "provider_account_id", name="uq_social_account_provider_identity"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(200), nullable=False)
    account_name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="connected", server_default="connected")
    granted_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
