from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base


class User(Base):
    """A person who can sign in and belong to one or more organizations."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    # Null for accounts created through WhatsApp, which gives us a phone number and no email address.
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # False for accounts created through Google/WhatsApp: password_hash then holds a random value nobody knows.
    has_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    # Bumped on password change/reset and "sign out everywhere"; tokens carrying an older value are rejected.
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # TOTP enrollment is staged: secret is pending until the first valid authenticator code.
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_pending_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
