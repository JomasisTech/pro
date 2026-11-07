from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class SocialPostObservation(Base):
    """Imported social content kept separate from owner-confirmed business facts."""

    __tablename__ = "social_post_observations"
    __table_args__ = (UniqueConstraint("social_account_id", "source_post_id", name="uq_social_observation_source_post"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_post_id: Mapped[str] = mapped_column(String(200), nullable=False)
    post_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    permalink: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class BrandIntelligenceAnalysis(Base):
    """Versioned AI proposal that must be explicitly reviewed by an owner/admin."""

    __tablename__ = "brand_intelligence_analyses"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    proposal: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    conflicts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_observation_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reviewed_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
