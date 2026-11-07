from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BusinessProfile(Base):
    """The business context for one organization (one profile per organization)."""

    __tablename__ = "business_profiles"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_business_profile_organization"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_name: Mapped[str] = mapped_column(String(160), nullable=False)
    industry_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("industry_categories.id", ondelete="SET NULL"), nullable=True
    )
    niche: Mapped[str | None] = mapped_column(String(160), nullable=True)
    subcategory_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("industry_categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    products_services: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    audience_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    geographic_market: Mapped[str | None] = mapped_column(String(160), nullable=True)
    unique_selling_points: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preferred_tone: Mapped[str | None] = mapped_column(String(120), nullable=True)
    preferred_words: Mapped[str | None] = mapped_column(Text, nullable=True)
    avoided_words: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Voice source is explicit so approved social insights never silently override owner choices.
    brand_voice_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="hybrid", server_default="hybrid")
    custom_ai_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(35), nullable=False, default="en", server_default="en")
    marketing_goals: Mapped[str | None] = mapped_column(Text, nullable=True)
    posting_frequency: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    onboarding_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
