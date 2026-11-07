"""Singleton database lease preventing overlapping campaign workers."""
from datetime import datetime
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class PlatformEmailWorkerLease(Base):
    __tablename__ = "platform_email_worker_leases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
