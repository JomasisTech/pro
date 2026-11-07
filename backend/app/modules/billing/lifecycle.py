"""Bounded subscription lifecycle transitions for cancellation and renewal grace periods."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, Organization, Subscription
from app.modules.audit.activity import record_activity

DEFAULT_GRACE_PERIOD_DAYS = 3


def process_subscription_lifecycle(
    db: Session, *, limit: int = 100, grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS,
) -> dict:
    """Expire cancelled subscriptions at period end and grant a short renewal grace window otherwise.

    This does not charge customers. It only transitions local access after a one-time payment period ends.
    """
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if not 0 <= grace_period_days <= 14:
        raise ValueError("grace_period_days must be between 0 and 14")
    now = datetime.now(timezone.utc)
    due = db.scalars(select(Subscription).where(
        Subscription.status.in_(("active", "past_due")),
        Subscription.current_period_end.is_not(None),
        Subscription.current_period_end <= now,
    ).order_by(Subscription.current_period_end.asc()).limit(limit)).all()
    summary = {"examined": len(due), "cancelled": 0, "entered_grace": 0, "expired": 0}

    for candidate in due:
        subscription = db.scalar(select(Subscription).where(
            Subscription.id == candidate.id
        ).with_for_update())
        if subscription is None or subscription.current_period_end is None:
            continue
        organization = db.scalar(select(Organization).where(
            Organization.id == subscription.organization_id
        ).with_for_update())
        if organization is None:
            continue
        actor = db.scalar(select(Membership).where(
            Membership.organization_id == organization.id
        ).order_by(Membership.role != "owner", Membership.created_at).limit(1))

        if subscription.cancel_at_period_end:
            subscription.status = "cancelled"
            subscription.cancel_at_period_end = False
            subscription.grace_period_ends_at = None
            organization.plan = "free"
            summary["cancelled"] += 1
            action = "billing.subscription_cancelled"
            detail = "Subscription ended at the customer's requested period boundary"
        elif subscription.status == "active":
            subscription.status = "past_due"
            period_end = subscription.current_period_end
            if period_end.tzinfo is None:
                period_end = period_end.replace(tzinfo=timezone.utc)
            subscription.grace_period_ends_at = period_end + timedelta(days=grace_period_days)
            if grace_period_days == 0 or subscription.grace_period_ends_at <= now:
                subscription.status = "expired"
                organization.plan = "free"
                summary["expired"] += 1
                action = "billing.subscription_expired"
                detail = "Subscription expired after its renewal grace period"
            else:
                summary["entered_grace"] += 1
                action = "billing.subscription_past_due"
                detail = f"Subscription entered a {grace_period_days}-day renewal grace period"
        elif subscription.status == "past_due" and subscription.grace_period_ends_at is not None:
            grace_end = subscription.grace_period_ends_at
            if grace_end.tzinfo is None:
                grace_end = grace_end.replace(tzinfo=timezone.utc)
            if grace_end <= now:
                subscription.status = "expired"
                organization.plan = "free"
                summary["expired"] += 1
                action = "billing.subscription_expired"
                detail = "Subscription expired after its renewal grace period"
            else:
                continue
        else:
            continue

        if actor is not None:
            from sqlalchemy.orm import joinedload
            actor = db.scalar(select(Membership).where(Membership.id == actor.id).options(joinedload(Membership.user)))
            if actor is not None:
                record_activity(db, actor, action, "subscription", subscription.id, detail)
    db.commit()
    return summary
