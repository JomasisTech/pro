"""Provider-reported token usage for successful AI calls."""
from datetime import UTC, datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AIUsageRecord(Base):
    __tablename__ = "ai_usage_records"
    __table_args__ = (Index("ix_ai_usage_records_created_model", "created_at", "model"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    feature: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd_micros: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, server_default=func.now())
