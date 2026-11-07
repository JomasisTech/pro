"""Read-only industry category list used by onboarding and the business profile form."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.core.database import get_db
from app.models import IndustryCategory, User
from app.schemas import CategoryResponse

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    _current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CategoryResponse]:
    """Return industries with their subcategories, ordered for display."""
    rows = db.scalars(select(IndustryCategory).order_by(IndustryCategory.sort_order, IndustryCategory.name)).all()
    children: dict = {}
    for row in rows:
        if row.parent_id is not None:
            children.setdefault(row.parent_id, []).append(
                CategoryResponse(id=row.id, slug=row.slug, name=row.name)
            )
    return [
        CategoryResponse(id=row.id, slug=row.slug, name=row.name, subcategories=children.get(row.id, []))
        for row in rows
        if row.parent_id is None
    ]
