from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, Index, String, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class PlatformLoginEvent(Base):
    """Minimal successful sign-in telemetry for platform security and support."""
    __tablename__ = "platform_login_events"
    __table_args__ = (Index("ix_platform_login_events_user_created", "user_id", "created_at"),
                      Index("ix_platform_login_events_created", "created_at"))
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="password", server_default="password")
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
