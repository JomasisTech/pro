"""Read-only activity log for an organization. There is deliberately no way to edit or delete entries."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.organizations import require_roles
from app.core.database import get_db
from app.models import ActivityLog, Membership
from app.schemas import ActivityResponse

router = APIRouter(prefix="/organizations/{organization_id}/activity", tags=["activity"])


@router.get("", response_model=list[ActivityResponse])
def list_activity(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    entity_type: str | None = Query(default=None, max_length=64),
    action_prefix: str | None = Query(default=None, max_length=64, description="e.g. 'draft.' for all draft events"),
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> list[ActivityLog]:
    """Newest first, optionally filtered by entity type or action prefix. Restricted to owners and admins."""
    query = select(ActivityLog).where(ActivityLog.organization_id == membership.organization_id)
    if entity_type:
        query = query.where(ActivityLog.entity_type == entity_type)
    if action_prefix:
        query = query.where(ActivityLog.action.startswith(action_prefix, autoescape=True))
    return list(
        db.scalars(
            query
            .order_by(ActivityLog.created_at.desc(), ActivityLog.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
