from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class PaymentAdjustment(Base):
    """Verified provider refund/dispute events; no raw webhook payload is retained."""
    __tablename__ = "payment_adjustments"
    __table_args__ = (
        Index("ix_payment_adjustments_type_status_created", "adjustment_type", "status", "created_at"),
        Index("ix_payment_adjustments_payment", "payment_transaction_id"),
    )
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    payment_transaction_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False, default="paystack", server_default="paystack")
    provider_event_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    provider_adjustment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    adjustment_type: Mapped[str] = mapped_column(String(24), nullable=False)  # refund | chargeback
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # processed | pending | won | lost
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
