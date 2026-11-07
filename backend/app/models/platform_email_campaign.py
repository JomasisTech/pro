from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class PlatformEmailCampaign(Base):
    __tablename__ = "platform_email_campaigns"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    created_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    subject: Mapped[str] = mapped_column(String(180), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", server_default="queued")
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class PlatformEmailRecipient(Base):
    __tablename__ = "platform_email_recipients"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    campaign_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("platform_email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unsubscribe_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bounced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
