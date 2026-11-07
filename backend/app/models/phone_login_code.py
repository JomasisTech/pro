from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class PhoneLoginCode(Base):
    """A one-time sign-in code sent to a WhatsApp number. Only a keyed hash of the code is stored."""

    __tablename__ = "phone_login_codes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
