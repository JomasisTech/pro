from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class BusinessProduct(Base):
    """A structured product or service owned by one organization."""

    __tablename__ = "business_products"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
