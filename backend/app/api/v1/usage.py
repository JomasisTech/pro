"""Shows an organization's plan, limits, and usage so the UI can display them."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership
from app.core.database import get_db
from app.core.plans import METRIC_LABELS, PLAN_LIMITS, get_limit, plan_name, resolve_plan
from app.models import Membership
from app.modules.billing.quota import get_used, period_start
from app.schemas import UsageItem, UsageResponse

router = APIRouter(prefix="/organizations/{organization_id}/usage", tags=["usage"])


@router.get("", response_model=UsageResponse)
def get_usage(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)) -> UsageResponse:
    """Plan and this month's usage for every limited metric; any member may read it."""
    plan = membership.organization.plan
    items = []
    for metric in PLAN_LIMITS[resolve_plan(plan)]:
        limit = get_limit(plan, metric)
        used = get_used(db, membership.organization_id, metric)
        items.append(
            UsageItem(
                metric=metric,
                label=METRIC_LABELS.get(metric, metric),
                limit=limit,
                used=used,
                remaining=None if limit is None else max(0, limit - used),
            )
        )
    return UsageResponse(plan=resolve_plan(plan), plan_name=plan_name(plan), period_start=period_start(), metrics=items)
