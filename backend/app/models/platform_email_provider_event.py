"""Idempotency ledger for verified email-provider webhook events."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base


class PlatformEmailProviderEvent(Base):
    __tablename__ = "platform_email_provider_events"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="resend", server_default="resend")
    provider_event_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
