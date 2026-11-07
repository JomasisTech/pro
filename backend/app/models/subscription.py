from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class Subscription(Base):
    """Persisted subscription state; only trusted verified-payment workflows may activate it."""

    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="paystack", server_default="paystack")
    plan_id: Mapped[str] = mapped_column(String(32), nullable=False, default="free", server_default="free")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="inactive", server_default="inactive")
    amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    billing_interval: Mapped[str | None] = mapped_column(String(16), nullable=True)
    provider_customer_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provider_subscription_code: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    provider_authorization_code_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    provider_authorization_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    provider_authorization_reusable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    authorization_card_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    authorization_card_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    authorization_card_exp_month: Mapped[str | None] = mapped_column(String(2), nullable=True)
    authorization_card_exp_year: Mapped[str | None] = mapped_column(String(4), nullable=True)
    recurring_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurring_consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recurring_billing_notice_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    grace_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
