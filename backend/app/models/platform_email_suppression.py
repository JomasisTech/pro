from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid
from app.core.database import Base

class PlatformEmailSuppression(Base):
    __tablename__ = "platform_email_suppressions"
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(24), nullable=False, default="unsubscribe")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
