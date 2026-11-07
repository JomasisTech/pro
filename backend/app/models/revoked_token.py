from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class RevokedToken(Base):
    """An access token (by `jti`) that was signed out before it expired.

    Rows are only needed until `expires_at`; expired rows are pruned opportunistically on logout.
    """

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (Index("ix_revoked_tokens_expires_at", "expires_at"), Index("ix_revoked_tokens_user_id", "user_id"))
