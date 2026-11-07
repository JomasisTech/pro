from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.core.database import Base


class IndustryCategory(Base):
    """An industry (top level, `parent_id` is null) or a subcategory inside an industry.

    Stored as data so the list can change without a frontend release.
    """

    __tablename__ = "industry_categories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("industry_categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
