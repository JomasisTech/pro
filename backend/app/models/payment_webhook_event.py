from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class PaymentWebhookEvent(Base):
    """Minimal webhook receipt for deduplication; raw payment payloads are not stored."""

    __tablename__ = "payment_webhook_events"
    __table_args__ = (Index("ix_payment_webhook_events_status_received", "status", "received_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="paystack", server_default="paystack")
    event_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    transaction_reference: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", server_default="received")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(400), nullable=True)
