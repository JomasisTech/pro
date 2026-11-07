from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class SubscriptionRenewalAttempt(Base):
    """One durable, idempotent renewal attempt for a subscription period."""

    __tablename__ = "subscription_renewal_attempts"
    __table_args__ = (
        UniqueConstraint("subscription_id", "period_end", name="uq_renewal_subscription_period"),
        Index("ix_renewal_attempt_status_created", "status", "created_at"),
        Index("ix_renewal_attempt_retry_at", "status", "retry_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    subscription_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    payment_transaction_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="processing", server_default="processing")
    provider_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorization_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # Only populated when Paystack explicitly supplies a retry window (e.g. card regulator).
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    previous_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
