"""Encrypted provider credentials, separate from public social account metadata."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class SocialCredential(Base):
    __tablename__ = "social_credentials"
    __table_args__ = (UniqueConstraint("social_account_id", name="uq_social_credential_account"),)
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    social_account_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_type: Mapped[str] = mapped_column(String(32), nullable=False, default="bearer", server_default="bearer")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
