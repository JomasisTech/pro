from datetime import date, datetime
from uuid import UUID, uuid4
from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class PlatformCostEntry(Base):
    """Manually verified operating-cost entry; amounts are stored in minor currency units."""
    __tablename__ = "platform_cost_entries"
    __table_args__ = (Index("ix_platform_cost_entries_period_currency", "period_start", "currency"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(240), nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
