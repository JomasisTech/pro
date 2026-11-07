from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class AuthIdentity(Base):
    """External sign-in identity, keyed by provider subject rather than email."""
    __tablename__ = "auth_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_auth_identity_provider_subject"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
