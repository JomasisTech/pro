from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BillingPrice(Base):
    """Owner-managed platform price for one plan, currency and billing interval."""

    __tablename__ = "billing_prices"
    __table_args__ = (
        UniqueConstraint("plan_id", "currency", "billing_interval", name="uq_billing_price_plan_currency_interval"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    plan_id: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BillingPriceChange(Base):
    """Append-only audit trail for platform price changes."""

    __tablename__ = "billing_price_changes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    price_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    plan_id: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    previous_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    new_amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    new_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
