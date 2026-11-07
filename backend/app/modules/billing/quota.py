"""Plan-limit enforcement and usage counting. Limits come only from app/core/plans.py."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership
from app.core.database import get_db
from app.core.plans import METRIC_LABELS, get_limit, plan_name
from app.models import Membership, UsageEvent


def period_start(now: datetime | None = None) -> datetime:
    """Start of the current calendar month, UTC."""
    now = now or datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def get_used(db: Session, organization_id: UUID, metric: str, now: datetime | None = None) -> int:
    """How much of `metric` the organization has used this month."""
    total = db.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.metric == metric,
            UsageEvent.created_at >= period_start(now),
        )
    )
    return int(total or 0)


def record_usage(db: Session, organization_id: UUID, metric: str, quantity: int = 1) -> None:
    """Count a successful action. Call only after the action succeeded so failures never use up quota."""
    db.add(UsageEvent(organization_id=organization_id, metric=metric, quantity=quantity))
    db.commit()


def require_quota(metric: str):
    """Dependency factory: member-only, and rejects with 402 once the plan's monthly limit for `metric` is used up.

    Use it instead of `get_membership` on any endpoint that consumes a limited resource.
    Note: two simultaneous requests can both pass just before the limit; that small overshoot is accepted for now.
    """

    def dependency(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)) -> Membership:
        plan = membership.organization.plan
        limit = get_limit(plan, metric)
        if limit is not None and get_used(db, membership.organization_id, metric) >= limit:
            label = METRIC_LABELS.get(metric, metric)
            raise HTTPException(
                status_code=402,
                detail=f"Your {plan_name(plan)} plan allows {limit} {label} per month and you have used them all. "
                "Upgrade your plan to continue",
            )
        return membership

    return dependency
