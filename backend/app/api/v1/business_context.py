"""Read-only, organization-scoped context for downstream AI features."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership
from app.core.database import get_db
from app.models import Membership
from app.modules.business.context import build_business_context
from app.schemas import BusinessContextResponse

router = APIRouter(prefix="/organizations/{organization_id}/business-context", tags=["business context"])


@router.get("", response_model=BusinessContextResponse)
def get_business_context(
    membership: Membership = Depends(get_membership), db: Session = Depends(get_db)
) -> dict:
    """Return user-provided business facts and profile completeness to organization members."""
    context = build_business_context(db, membership.organization_id)
    if context is None:
        raise HTTPException(status_code=404, detail="Business profile has not been set up yet")
    return context
