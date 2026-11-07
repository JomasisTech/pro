from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class PaymentTransaction(Base):
    """A server-created payment attempt; never treat browser input as proof of payment."""

    __tablename__ = "payment_transactions"
    __table_args__ = (
        Index("ix_payment_transactions_org_created", "organization_id", "created_at"),
        Index("ix_payment_transactions_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    initiated_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="paystack", server_default="paystack")
    reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    plan_id: Mapped[str] = mapped_column(String(32), nullable=False)
    billing_interval: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly", server_default="monthly")
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    recurring_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurring_consent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recurring_consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(80), nullable=True, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
