from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BillingNotification(Base):
    """Durable transactional email outbox with an idempotency key and bounded retries."""

    __tablename__ = "billing_notifications"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_billing_notification_event_key"),
        Index("ix_billing_notification_delivery", "status", "next_attempt_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True
    )
    renewal_attempt_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("subscription_renewal_attempts.id", ondelete="SET NULL"), nullable=True
    )
    event_key: Mapped[str] = mapped_column(String(240), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
