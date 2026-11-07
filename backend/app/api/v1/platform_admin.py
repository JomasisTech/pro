"""Platform-owner-only customer and billing operations."""
from datetime import date, datetime, timedelta, timezone
import logging
import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.v1.billing import _is_platform_admin, require_platform_admin, require_platform_permission
from app.api.v1.auth import _send_reset_email
from app.config import get_settings
from app.core.database import get_db, SessionLocal
from app.integrations.payments.registry import PaymentProviderUnavailable, get_payment_provider
from app.models import Membership, Organization, PasswordResetToken, PaymentTransaction, PaymentWebhookEvent, PlatformAdminAudit, Subscription, User, PlatformLoginEvent, ActivityLog, UsageEvent, SocialAccount, ContentDraft, ScheduledPost, BusinessProfile, PlatformCostEntry, AIUsageRecord, PaymentAdjustment, PlatformAdminRole
from app.modules.billing.service import PaymentVerificationMismatch, PaymentVerificationUnavailable, verify_and_activate
from app.modules.billing.reconciliation import reconcile_pending_payments
from app.core.security import generate_reset_token, hash_reset_token
from app.integrations.email import send_email
from app.models import PlatformEmailCampaign, PlatformEmailRecipient, PlatformEmailSuppression, PlatformEmailProviderEvent

router = APIRouter(prefix="/platform-admin", tags=["platform-admin"])
log = logging.getLogger(__name__)


class CustomerStatusUpdate(BaseModel):
    is_active: bool


class PlatformCostEntryCreate(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    provider: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=240)
    amount_minor: int = Field(gt=0, le=2_000_000_000)
    currency: str = Field(pattern="^[A-Z]{3}$")
    period_start: date
    period_end: date
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("period_end")
    @classmethod
    def valid_period(cls, value: date, info):
        start = info.data.get("period_start")
        if start and value < start:
            raise ValueError("period_end must be on or after period_start")
        return value


class AdminPasswordRecoveryRequest(BaseModel):
    reason: str = Field(min_length=20, max_length=500)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 20:
            raise ValueError("Provide a meaningful support reason of at least 20 characters")
        return cleaned


def _customer_row(db: Session, user: User) -> dict:
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
    organizations = []
    for membership in memberships:
        org = db.get(Organization, membership.organization_id)
        if not org:
            continue
        subscription = db.scalar(select(Subscription).where(Subscription.organization_id == org.id))
        organizations.append({
            "id": str(org.id), "name": org.name, "slug": org.slug, "role": membership.role,
            "plan": org.plan,
            "subscription": None if subscription is None else {
                "status": subscription.status, "plan_id": subscription.plan_id,
                "provider": subscription.provider, "currency": subscription.currency,
                "amount_minor": subscription.amount_minor, "billing_interval": subscription.billing_interval,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "grace_period_ends_at": subscription.grace_period_ends_at,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "cancellation_requested_at": subscription.cancellation_requested_at,
            },
        })
    return {
        "id": str(user.id), "email": user.email, "full_name": user.full_name,
        "is_active": user.is_active, "has_password": user.has_password,
        "email_verified": user.email_verified_at is not None,
        "created_at": user.created_at, "organizations": organizations,
    }


@router.get("/overview")
def overview(_: User = Depends(require_platform_permission("overview.read")), db: Session = Depends(get_db)) -> dict:
    return {
        "customers": db.scalar(select(func.count(User.id))) or 0,
        "active_customers": db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))) or 0,
        "organizations": db.scalar(select(func.count(Organization.id))) or 0,
        "active_subscriptions": db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "active")) or 0,
        "past_due_subscriptions": db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "past_due")) or 0,
        "cancelled_subscriptions": db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "cancelled")) or 0,
        "expired_subscriptions": db.scalar(select(func.count(Subscription.id)).where(Subscription.status == "expired")) or 0,
        "pending_payments": db.scalar(select(func.count(PaymentTransaction.id)).where(PaymentTransaction.status == "pending")) or 0,
        "failed_webhooks": db.scalar(select(func.count(PaymentWebhookEvent.id)).where(PaymentWebhookEvent.status == "failed")) or 0,
    }


@router.get("/customers")
def list_customers(
    q: str | None = Query(default=None, max_length=160),
    status: str = Query(default="all", pattern="^(all|active|suspended)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_platform_permission("customers.read")), db: Session = Depends(get_db),
) -> dict:
    statement = select(User)
    if q and q.strip():
        term = f"%{q.strip()}%"
        statement = statement.where(or_(User.email.ilike(term), User.full_name.ilike(term)))
    if status == "active":
        statement = statement.where(User.is_active.is_(True))
    elif status == "suspended":
        statement = statement.where(User.is_active.is_(False))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    users = db.scalars(statement.order_by(User.created_at.desc()).offset(offset).limit(limit)).all()
    return {"items": [_customer_row(db, user) for user in users], "total": total, "limit": limit, "offset": offset}


@router.get("/top-customers")
def top_customers(
    currency: str = Query(default="NGN", pattern="^(NGN|USD)$"),
    sort: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=10, ge=1, le=10),
    _: User = Depends(require_platform_permission("finance.read")), db: Session = Depends(get_db),
) -> dict:
    """Rank the customers who initiated the most successful payments in one currency.

    NGN and USD are intentionally ranked separately: adding unlike currencies would
    produce a misleading lifetime-spend leaderboard without a documented FX source.
    """
    total_spend = func.sum(PaymentTransaction.amount_minor).label("total_spend_minor")
    payment_count = func.count(PaymentTransaction.id).label("successful_payment_count")
    last_payment = func.max(PaymentTransaction.paid_at).label("last_payment_at")
    ordering = total_spend.asc() if sort == "asc" else total_spend.desc()
    rows = db.execute(
        select(User, total_spend, payment_count, last_payment)
        .join(PaymentTransaction, PaymentTransaction.initiated_by_user_id == User.id)
        .where(
            PaymentTransaction.status == "paid",
            PaymentTransaction.currency == currency,
        )
        .group_by(User.id)
        .order_by(ordering, payment_count.desc(), User.created_at.asc(), User.id.asc())
        .limit(limit)
    ).all()
    items = []
    for rank, (user, spend, count, paid_at) in enumerate(rows, start=1):
        items.append({
            "rank": rank, "user_id": str(user.id), "full_name": user.full_name,
            "email": user.email, "is_active": user.is_active,
            "total_spend_minor": int(spend or 0), "currency": currency,
            "successful_payment_count": int(count or 0), "last_payment_at": paid_at,
        })
    return {"items": items, "currency": currency, "sort": sort, "limit": limit,
            "metric": "lifetime_successful_payment_spend",
            "note": "Ranked by successful payments initiated by each customer; currencies are ranked separately."}


@router.get("/customers/{user_id}")
def get_customer(user_id: UUID, _: User = Depends(require_platform_permission("customers.read")), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    row = _customer_row(db, user)
    org_ids = [UUID(item["id"]) for item in row["organizations"]]
    row["social_accounts"] = [
        {"id": str(a.id), "organization_id": str(a.organization_id), "provider": a.provider,
         "account_name": a.account_name, "account_type": a.account_type, "status": a.status,
         "connected_at": a.connected_at, "last_synced_at": a.last_synced_at}
        for a in db.scalars(select(SocialAccount).where(SocialAccount.organization_id.in_(org_ids))).all()
    ] if org_ids else []
    row["business_profiles"] = []
    if org_ids:
        for profile in db.scalars(select(BusinessProfile).where(BusinessProfile.organization_id.in_(org_ids))).all():
            row["business_profiles"].append({"organization_id": str(profile.organization_id),
                "business_name": getattr(profile, "business_name", None),
                "industry": getattr(profile, "industry", None), "niche": getattr(profile, "niche", None),
                "description": getattr(profile, "description", None)})
    row["recent_content"] = [{"id": str(d.id), "organization_id": str(d.organization_id),
        "topic": d.topic, "content_type": d.content_type, "status": d.status,
        "content_preview": d.content[:240], "created_at": d.created_at}
        for d in db.scalars(select(ContentDraft).where(ContentDraft.organization_id.in_(org_ids))
            .order_by(ContentDraft.created_at.desc()).limit(30)).all()] if org_ids else []
    row["scheduled_posts"] = [{"id": str(p.id), "organization_id": str(p.organization_id),
        "provider": p.provider, "title": p.title, "status": p.status,
        "scheduled_at": p.scheduled_at, "created_at": p.created_at}
        for p in db.scalars(select(ScheduledPost).where(ScheduledPost.organization_id.in_(org_ids))
            .order_by(ScheduledPost.created_at.desc()).limit(30)).all()] if org_ids else []
    row["usage"] = [{"metric": metric, "quantity": int(quantity)} for metric, quantity in
        db.execute(select(UsageEvent.metric, func.sum(UsageEvent.quantity)).where(
            UsageEvent.organization_id.in_(org_ids)).group_by(UsageEvent.metric)).all()] if org_ids else []
    row["login_history"] = [{"method": e.method, "user_agent": e.user_agent, "created_at": e.created_at}
        for e in db.scalars(select(PlatformLoginEvent).where(PlatformLoginEvent.user_id == user.id)
            .order_by(PlatformLoginEvent.created_at.desc()).limit(20)).all()]
    row["payment_transactions"] = [
        {"reference": p.reference, "provider": p.provider, "status": p.status,
         "amount_minor": p.amount_minor, "currency": p.currency, "plan_id": p.plan_id,
         "billing_interval": p.billing_interval, "created_at": p.created_at, "paid_at": p.paid_at}
        for p in db.scalars(select(PaymentTransaction).where(PaymentTransaction.initiated_by_user_id == user.id)
                            .order_by(PaymentTransaction.created_at.desc()).limit(50)).all()
    ]
    return row


@router.get("/financials")
def financial_analytics(
    days: int = Query(default=90, ge=7, le=365),
    _: User = Depends(require_platform_permission("finance.read")), db: Session = Depends(get_db),
) -> dict:
    """Revenue and usage reporting. Currency totals are deliberately never combined."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    paid = db.execute(select(PaymentTransaction.currency, func.sum(PaymentTransaction.amount_minor),
        func.count(PaymentTransaction.id)).where(PaymentTransaction.status == "paid",
        PaymentTransaction.paid_at >= since).group_by(PaymentTransaction.currency)).all()
    pending = db.execute(select(PaymentTransaction.currency, func.sum(PaymentTransaction.amount_minor),
        func.count(PaymentTransaction.id)).where(PaymentTransaction.status == "pending",
        PaymentTransaction.created_at >= since).group_by(PaymentTransaction.currency)).all()
    month_year = func.extract("year", PaymentTransaction.paid_at)
    month_number = func.extract("month", PaymentTransaction.paid_at)
    monthly = db.execute(select(PaymentTransaction.currency, month_year, month_number,
        func.sum(PaymentTransaction.amount_minor), func.count(PaymentTransaction.id))
        .where(PaymentTransaction.status == "paid", PaymentTransaction.paid_at >= since)
        .group_by(PaymentTransaction.currency, month_year, month_number)
        .order_by(month_year, month_number)).all()
    usage = db.execute(select(UsageEvent.metric, func.sum(UsageEvent.quantity), func.count(UsageEvent.id))
        .where(UsageEvent.created_at >= since).group_by(UsageEvent.metric)).all()
    ai_usage = db.execute(select(AIUsageRecord.provider, AIUsageRecord.model, AIUsageRecord.feature,
        func.sum(AIUsageRecord.prompt_tokens), func.sum(AIUsageRecord.completion_tokens),
        func.sum(AIUsageRecord.total_tokens), func.sum(AIUsageRecord.estimated_cost_usd_micros),
        func.count(AIUsageRecord.id)).where(AIUsageRecord.created_at >= since)
        .group_by(AIUsageRecord.provider, AIUsageRecord.model, AIUsageRecord.feature)
        .order_by(func.sum(AIUsageRecord.total_tokens).desc())).all()
    cost_rows = db.execute(select(PlatformCostEntry.currency, func.sum(PlatformCostEntry.amount_minor),
        func.count(PlatformCostEntry.id)).where(PlatformCostEntry.period_end >= since.date(), PlatformCostEntry.period_start <= date.today())
        .group_by(PlatformCostEntry.currency)).all()
    adjustments = db.execute(select(PaymentAdjustment.adjustment_type, PaymentAdjustment.status,
        PaymentAdjustment.currency, func.sum(PaymentAdjustment.amount_minor), func.count(PaymentAdjustment.id))
        .where(PaymentAdjustment.created_at >= since)
        .group_by(PaymentAdjustment.adjustment_type, PaymentAdjustment.status, PaymentAdjustment.currency)).all()
    adjustment_totals = [{"type": kind, "status": status, "currency": currency,
        "amount_minor": int(amount or 0), "events": int(count)} for kind, status, currency, amount, count in adjustments]
    return {
        "period_days": days,
        "revenue_by_currency": [{"currency": c, "paid_amount_minor": int(amount or 0), "paid_transactions": int(count)} for c, amount, count in paid],
        "pending_by_currency": [{"currency": c, "pending_amount_minor": int(amount or 0), "pending_transactions": int(count)} for c, amount, count in pending],
        "monthly_revenue": [{"currency": c, "month": f"{int(year):04d}-{int(month):02d}", "amount_minor": int(amount or 0), "transactions": int(count)} for c, year, month, amount, count in monthly],
        "usage_by_metric": [{"metric": metric, "quantity": int(quantity or 0), "events": int(count)} for metric, quantity, count in usage],
        "ai_usage_by_model": [{"provider": provider, "model": model, "feature": feature,
            "prompt_tokens": int(prompt or 0), "completion_tokens": int(completion or 0),
            "total_tokens": int(total or 0), "estimated_cost_usd_micros": int(cost) if cost is not None else None,
            "events": int(events)} for provider, model, feature, prompt, completion, total, cost, events in ai_usage],
        "ai_cost_estimation": {"configured": any(row[6] is not None for row in ai_usage),
            "note": "Costs are estimated only when explicit per-million-token rates are configured for the active model. Provider-reported token counts are retained independently."},
        "recorded_costs_by_currency": [{"currency": c, "recorded_cost_minor": int(amount or 0), "entries": int(count)} for c, amount, count in cost_rows],
        "payment_adjustments": adjustment_totals,
        "refund_chargeback_note": "Refunds, open disputes and lost disputes are reported separately. Do not subtract a dispute and a refund twice if the provider later links both to the same underlying amount; accounting reconciliation is required before declaring net revenue.",
        "cost_tracking": {"available": True, "source": "Manually entered, administrator-verified operating cost ledger", "note": "Only recorded expenses are included; unentered vendor invoices and usage-based provider charges are not inferred."},
        "profitability": {"available": False, "reason": "A complete net-profit figure still requires all operating-cost invoices and reconciliation of overlapping refunds, disputes, fees and reversals. Recorded expenses are not a complete cost base."},
        "currency_note": "Amounts are stored in minor units. Different currencies must be evaluated separately; no FX conversion is applied.",
    }


@router.get("/payment-adjustments")
def platform_payment_adjustments(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_platform_permission("finance.read")), db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(select(PaymentAdjustment).order_by(PaymentAdjustment.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(row.id), "payment_transaction_id": str(row.payment_transaction_id),
        "provider": row.provider, "provider_adjustment_id": row.provider_adjustment_id,
        "type": row.adjustment_type, "status": row.status, "amount_minor": row.amount_minor,
        "currency": row.currency, "reason": row.reason, "created_at": row.created_at,
        "resolved_at": row.resolved_at} for row in rows]}


@router.get("/ai-usage")
def platform_ai_usage(
    days: int = Query(default=90, ge=1, le=365),
    _: User = Depends(require_platform_permission("finance.read")), db: Session = Depends(get_db),
) -> dict:
    """Provider-reported token consumption; null cost means no rate is configured."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(select(AIUsageRecord.provider, AIUsageRecord.model, AIUsageRecord.feature,
        func.sum(AIUsageRecord.prompt_tokens), func.sum(AIUsageRecord.completion_tokens),
        func.sum(AIUsageRecord.total_tokens), func.sum(AIUsageRecord.estimated_cost_usd_micros),
        func.count(AIUsageRecord.id)).where(AIUsageRecord.created_at >= since)
        .group_by(AIUsageRecord.provider, AIUsageRecord.model, AIUsageRecord.feature)
        .order_by(func.sum(AIUsageRecord.total_tokens).desc())).all()
    return {"period_days": days, "items": [{"provider": p, "model": m, "feature": f,
        "prompt_tokens": int(inp or 0), "completion_tokens": int(out or 0), "total_tokens": int(total or 0),
        "estimated_cost_usd_micros": int(cost) if cost is not None else None, "events": int(events)}
        for p, m, f, inp, out, total, cost, events in rows],
        "cost_note": "Token counts come from provider response usage fields. Cost is null unless matching rates are configured; no cost is fabricated."}


@router.get("/cost-entries")
def list_platform_cost_entries(
    limit: int = Query(default=100, ge=1, le=250),
    _: User = Depends(require_platform_permission("finance.read")), db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(select(PlatformCostEntry).order_by(PlatformCostEntry.period_start.desc()).limit(limit)).all()
    return {"items": [{"id": str(row.id), "category": row.category, "provider": row.provider,
        "description": row.description, "amount_minor": row.amount_minor, "currency": row.currency,
        "period_start": row.period_start, "period_end": row.period_end, "notes": row.notes,
        "created_at": row.created_at} for row in rows]}


@router.post("/cost-entries", status_code=201)
def create_platform_cost_entry(
    payload: PlatformCostEntryCreate,
    actor: User = Depends(require_platform_permission("finance.manage")), db: Session = Depends(get_db),
) -> dict:
    row = PlatformCostEntry(**payload.model_dump(), created_by_user_id=actor.id)
    db.add(row)
    db.flush()
    db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=None,
        action="finance.cost_entry_created", summary=f"Recorded {payload.currency} {payload.amount_minor} minor units for {payload.category} ({payload.provider})"))
    db.commit()
    db.refresh(row)
    return {"id": str(row.id), "message": "Operating cost entry recorded.", "amount_minor": row.amount_minor, "currency": row.currency}


@router.get("/activity")
def platform_activity(
    limit: int = Query(default=50, ge=1, le=200),
    _: User = Depends(require_platform_permission("activity.read")), db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(select(ActivityLog, Organization.name, User.email)
        .join(Organization, Organization.id == ActivityLog.organization_id)
        .outerjoin(User, User.id == ActivityLog.actor_user_id)
        .order_by(ActivityLog.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(log.id), "organization_id": str(log.organization_id),
        "organization": org_name, "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
        "actor_name": log.actor_name, "actor_email": email, "action": log.action,
        "entity_type": log.entity_type, "entity_id": str(log.entity_id) if log.entity_id else None,
        "summary": log.summary, "created_at": log.created_at}
        for log, org_name, email in rows]}


@router.get("/login-events")
def platform_login_events(
    limit: int = Query(default=100, ge=1, le=250),
    _: User = Depends(require_platform_permission("login_events.read")), db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(select(PlatformLoginEvent, User.email, User.full_name)
        .join(User, User.id == PlatformLoginEvent.user_id)
        .order_by(PlatformLoginEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(event.id), "user_id": str(event.user_id), "email": email,
        "full_name": name, "method": event.method, "user_agent": event.user_agent,
        "created_at": event.created_at} for event, email, name in rows]}


@router.post("/customers/{user_id}/password-recovery", status_code=202)
def initiate_customer_password_recovery(
    user_id: UUID,
    payload: AdminPasswordRecoveryRequest,
    actor: User = Depends(require_platform_permission("customers.support")),
    db: Session = Depends(get_db),
) -> dict:
    """Send a one-time password reset link only to the customer's existing verified email."""
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if target.id == actor.id or _is_platform_admin(target):
        raise HTTPException(status_code=403, detail="Platform administrator recovery must use the separate owner recovery procedure")
    if not target.is_active:
        raise HTTPException(status_code=409, detail="Reactivate the customer account before initiating password recovery")
    if not target.email or target.email_verified_at is None:
        raise HTTPException(status_code=409, detail="This account has no verified email address. Use the documented manual identity-verification support process.")

    now = datetime.now(timezone.utc)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == target.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = generate_reset_token()
    db.add(PasswordResetToken(
        user_id=target.id,
        token_hash=hash_reset_token(token),
        expires_at=now + timedelta(minutes=get_settings().password_reset_ttl_minutes),
    ))
    db.add(PlatformAdminAudit(
        actor_user_id=actor.id,
        target_user_id=target.id,
        action="customer.password_recovery_initiated",
        summary=f"Administrator initiated password recovery for {target.email}; reason: {payload.reason.strip()[:250]}",
    ))
    db.commit()
    background_tasks.add_task(_send_reset_email, target.email, token)
    return {"message": "A one-time password reset link has been sent to the customer's verified email address. The customer must choose their own new password."}


@router.patch("/customers/{user_id}/status")
def set_customer_status(
    user_id: UUID, payload: CustomerStatusUpdate, actor: User = Depends(require_platform_permission("customers.support")), db: Session = Depends(get_db)
) -> dict:
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="You cannot suspend your own platform administrator account")
    if _is_platform_admin(target):
        raise HTTPException(status_code=403, detail="Another platform administrator cannot be suspended here")
    desired = payload.is_active
    if target.is_active == desired:
        return {"id": str(target.id), "is_active": target.is_active, "message": "No change was needed."}
    target.is_active = desired
    if not desired:
        target.token_version += 1
    db.add(PlatformAdminAudit(
        actor_user_id=actor.id, target_user_id=target.id,
        action="customer.reactivated" if desired else "customer.suspended",
        summary=f"Platform administrator {'reactivated' if desired else 'suspended'} customer {target.email or target.id}",
    ))
    db.commit()
    return {"id": str(target.id), "is_active": target.is_active,
            "message": "Customer reactivated." if desired else "Customer suspended; existing sessions have been invalidated."}


@router.get("/audit")
def list_platform_audit(
    limit: int = Query(default=50, ge=1, le=100),
    _: User = Depends(require_platform_permission("activity.read")), db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(select(PlatformAdminAudit).order_by(PlatformAdminAudit.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(row.id), "actor_user_id": str(row.actor_user_id),
                        "target_user_id": str(row.target_user_id) if row.target_user_id else None,
                        "action": row.action, "summary": row.summary, "created_at": row.created_at}
                       for row in rows]}


@router.get("/billing-operations")
def billing_operations(_: User = Depends(require_platform_permission("operations.read")), db: Session = Depends(get_db)) -> dict:
    """Expose safe operational diagnostics without returning payment secrets."""
    settings = get_settings()
    public_key = settings.paystack_public_key or ""
    secret_key = settings.paystack_secret_key or ""
    recent_payments = db.scalars(select(PaymentTransaction).order_by(PaymentTransaction.created_at.desc()).limit(30)).all()
    recent_webhooks = db.scalars(select(PaymentWebhookEvent).order_by(PaymentWebhookEvent.received_at.desc()).limit(30)).all()
    return {
        "paystack": {
            "credentials_configured": bool(public_key and secret_key),
            "webhook_secret_configured": bool(settings.paystack_webhook_secret),
            "mode": "test" if public_key.startswith("pk_test_") and secret_key.startswith("sk_test_") else
                    "live" if public_key.startswith("pk_live_") and secret_key.startswith("sk_live_") else "unknown",
            "google_pay": "Available through Paystack Checkout when enabled and eligible; verify in merchant dashboard/test checkout.",
        },
        "transactions": [{"reference": row.reference, "organization_id": str(row.organization_id),
                          "provider": row.provider, "status": row.status, "amount_minor": row.amount_minor,
                          "currency": row.currency, "plan_id": row.plan_id,
                          "created_at": row.created_at, "paid_at": row.paid_at} for row in recent_payments],
        "webhooks": [{"id": str(row.id), "event_type": row.event_type, "reference": row.transaction_reference,
                       "status": row.status, "received_at": row.received_at,
                       "processed_at": row.processed_at, "failure_message": row.failure_message}
                      for row in recent_webhooks],
        "live_verification": "Not performed by this application. Complete the documented merchant test checklist before switching to live keys.",
    }


@router.post("/webhooks/{event_id}/retry")
def retry_failed_webhook(
    event_id: UUID, actor: User = Depends(require_platform_permission("operations.manage")), db: Session = Depends(get_db)
) -> dict:
    """Retry a failed or stale Paystack charge-success receipt after fresh provider verification."""
    event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.id == event_id).with_for_update())
    if event is None:
        raise HTTPException(status_code=404, detail="Webhook event not found")
    stale_before = datetime.now(timezone.utc) - timedelta(minutes=10)
    received_at = event.received_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    retryable = event.status == "failed" or (event.status == "processing" and received_at < stale_before)
    if not retryable:
        raise HTTPException(status_code=409, detail="Only failed or processing events older than 10 minutes can be retried")
    if event.provider != "paystack" or event.event_type != "charge.success" or not event.transaction_reference:
        raise HTTPException(status_code=400, detail="This webhook event cannot activate a subscription")

    event.status = "processing"
    event.failure_message = None
    db.commit()
    try:
        provider = get_payment_provider("paystack")
        payment = verify_and_activate(db, reference=event.transaction_reference, provider=provider)
        event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.id == event_id))
        if event is None:
            raise HTTPException(status_code=404, detail="Webhook event not found")
        event.status = "processed" if payment.status == "paid" else "ignored"
        event.processed_at = datetime.now(timezone.utc)
        db.add(PlatformAdminAudit(
            actor_user_id=actor.id, target_user_id=payment.initiated_by_user_id,
            action="billing.webhook_retried",
            summary=f"Platform administrator retried Paystack webhook {event.event_key}; result: {event.status}",
        ))
        db.commit()
        return {"id": str(event.id), "status": event.status, "payment_status": payment.status,
                "message": "Webhook retry completed using fresh Paystack transaction verification."}
    except PaymentVerificationUnavailable as exc:
        db.rollback()
        event = db.get(PaymentWebhookEvent, event_id)
        if event:
            event.status = "failed"
            event.failure_message = str(exc)[:400]
            db.add(PlatformAdminAudit(
                actor_user_id=actor.id, target_user_id=None, action="billing.webhook_retry_failed",
                summary=f"Platform administrator retry failed for Paystack webhook {event.event_key}",
            ))
            db.commit()
        raise HTTPException(status_code=503, detail="Paystack verification is temporarily unavailable; the webhook remains retryable") from exc
    except (PaymentVerificationMismatch, HTTPException) as exc:
        db.rollback()
        event = db.get(PaymentWebhookEvent, event_id)
        if event:
            event.status = "failed"
            event.failure_message = (str(exc.detail) if isinstance(exc, HTTPException) else str(exc))[:400]
            db.add(PlatformAdminAudit(
                actor_user_id=actor.id, target_user_id=None, action="billing.webhook_retry_rejected",
                summary=f"Platform administrator retry rejected for Paystack webhook {event.event_key}",
            ))
            db.commit()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=409, detail="The Paystack transaction did not match the expected payment") from exc
    except PaymentProviderUnavailable as exc:
        db.rollback()
        event = db.get(PaymentWebhookEvent, event_id)
        if event:
            event.status = "failed"
            event.failure_message = "Paystack is not configured or unavailable"
            db.commit()
        raise HTTPException(status_code=503, detail="Paystack is not configured or unavailable") from exc


class ReconciliationRequest(BaseModel):
    limit: int = 50
    older_than_minutes: int = 10


@router.post("/billing/reconciliation/run")
def run_payment_reconciliation(
    request: ReconciliationRequest,
    actor: User = Depends(require_platform_permission("operations.manage")),
    db: Session = Depends(get_db),
) -> dict:
    """Run a bounded reconciliation pass; also callable by a hosting scheduler."""
    if request.limit < 1 or request.limit > 100:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 100")
    if request.older_than_minutes < 5 or request.older_than_minutes > 1440:
        raise HTTPException(status_code=422, detail="older_than_minutes must be between 5 and 1440")
    result = reconcile_pending_payments(
        db, limit=request.limit, older_than_minutes=request.older_than_minutes,
        provider_factory=get_payment_provider,
    )
    db.add(PlatformAdminAudit(
        actor_user_id=actor.id,
        target_user_id=None,
        action="billing.reconciliation_run",
        summary=(
            f"Manual payment reconciliation examined {result['examined']} attempts; "
            f"activated {result['activated']}, failed {result['failed']}, "
            f"needs attention {result['needs_attention']}."
        ),
    ))
    db.commit()
    return result


class PlatformAdminRoleGrant(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern="^(support|finance|operations|viewer)$")


@router.get("/admins")
def list_platform_admins(
    actor: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    if not _is_platform_admin(actor):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can manage administrator roles")
    rows = db.execute(select(PlatformAdminRole, User.email, User.full_name).join(User, User.id == PlatformAdminRole.user_id).order_by(User.email)).all()
    return {"items": [{"id": str(role.id), "user_id": str(role.user_id), "email": email,
        "full_name": name, "role": role.role, "created_at": role.created_at} for role, email, name in rows],
        "owner_access": "Configured PLATFORM_ADMIN_EMAILS accounts have implicit super-admin access and are not stored as delegated roles."}


@router.post("/admins", status_code=201)
def grant_platform_admin_role(
    payload: PlatformAdminRoleGrant, actor: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    if not _is_platform_admin(actor):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can grant administrator roles")
    target = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().casefold()))
    if target is None:
        raise HTTPException(status_code=404, detail="A registered user with that email was not found")
    if target.email_verified_at is None or not target.is_active:
        raise HTTPException(status_code=409, detail="The administrator must have a verified email and an active account")
    if _is_platform_admin(target):
        raise HTTPException(status_code=409, detail="This account already has owner-level access through configuration")
    existing = db.scalar(select(PlatformAdminRole).where(PlatformAdminRole.user_id == target.id))
    if existing:
        existing.role = payload.role
        action = "admin.role_updated"
    else:
        existing = PlatformAdminRole(user_id=target.id, role=payload.role, granted_by_user_id=actor.id)
        db.add(existing)
        action = "admin.role_granted"
    db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=target.id, action=action,
        summary=f"Assigned platform administrator role '{payload.role}' to {target.email}"))
    db.commit()
    return {"user_id": str(target.id), "email": target.email, "role": existing.role,
        "message": "Role assigned. The user must enable authenticator MFA before accessing platform administration."}


@router.delete("/admins/{user_id}")
def revoke_platform_admin_role(
    user_id: UUID, actor: User = Depends(require_platform_admin), db: Session = Depends(get_db),
) -> dict:
    if not _is_platform_admin(actor):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can revoke administrator roles")
    assignment = db.scalar(select(PlatformAdminRole).where(PlatformAdminRole.user_id == user_id))
    if assignment is None:
        raise HTTPException(status_code=404, detail="Delegated administrator role not found")
    target = db.get(User, user_id)
    db.delete(assignment)
    db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=user_id,
        action="admin.role_revoked", summary=f"Revoked delegated platform administrator access for {target.email if target else user_id}"))
    db.commit()
    return {"user_id": str(user_id), "message": "Delegated platform administrator access revoked."}


class EmailCampaignCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    body: str = Field(min_length=10, max_length=12000)
    confirm_all_recipients: bool = False

    @field_validator("subject", "body")
    @classmethod
    def clean_campaign_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank")
        return cleaned


def _owner_only(actor: User) -> None:
    if not _is_platform_admin(actor):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can access this security control")




@router.get("/security/sessions")
def admin_sessions(limit: int = Query(default=100, ge=1, le=250), actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    delegated_ids = select(PlatformAdminRole.user_id)
    rows = db.execute(select(PlatformLoginEvent, User.email, User.full_name, User.token_version)
        .join(User, User.id == PlatformLoginEvent.user_id)
        .where(User.id.in_(delegated_ids) | User.email.in_([x.strip() for x in get_settings().platform_admin_emails.split(",") if x.strip()]))
        .order_by(PlatformLoginEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"event_id": str(e.id), "user_id": str(e.user_id), "email": email, "full_name": name,
        "method": e.method, "ip_address": e.ip_address, "user_agent": e.user_agent, "success": e.success,
        "created_at": e.created_at, "session_status": "sign-in recorded" if e.success else "failed sign-in"} for e,email,name,_version in rows]}


@router.post("/security/users/{user_id}/revoke-sessions")
def revoke_admin_sessions(user_id: UUID, actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    target = db.get(User, user_id)
    if target is None or (not _is_platform_admin(target) and db.scalar(select(PlatformAdminRole.id).where(PlatformAdminRole.user_id == user_id)) is None):
        raise HTTPException(status_code=404, detail="Platform administrator not found")
    target.token_version += 1
    db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=target.id, action="security.sessions_revoked", summary=f"All active sessions revoked for {target.email}"))
    db.commit()
    return {"message": f"All sessions for {target.email} have been revoked. They must sign in again.", "token_version": target.token_version}


@router.get("/security/failed-logins")
def failed_admin_logins(limit: int = Query(default=100, ge=1, le=250), actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    admin_ids = select(PlatformAdminRole.user_id)
    owner_emails = [x.strip() for x in get_settings().platform_admin_emails.split(",") if x.strip()]
    rows = db.execute(select(PlatformLoginEvent, User.email).join(User, User.id == PlatformLoginEvent.user_id)
        .where(PlatformLoginEvent.success.is_(False), (User.id.in_(admin_ids) | User.email.in_(owner_emails)))
        .order_by(PlatformLoginEvent.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(e.id), "email": email, "ip_address": e.ip_address, "method": e.method,
        "user_agent": e.user_agent, "created_at": e.created_at} for e,email in rows]}


@router.get("/email-campaigns")
def list_email_campaigns(limit: int = Query(default=20, ge=1, le=100), actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    rows = db.scalars(select(PlatformEmailCampaign).order_by(PlatformEmailCampaign.created_at.desc()).limit(limit)).all()
    return {"items": [{"id": str(c.id), "subject": c.subject, "status": c.status, "recipient_count": c.recipient_count,
        "sent_count": c.sent_count, "failed_count": c.failed_count, "created_at": c.created_at, "completed_at": c.completed_at} for c in rows]}


@router.get("/email-campaigns/recipient-count")
def email_campaign_recipient_count(actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    count = db.scalar(select(func.count(User.id)).where(User.email.is_not(None), User.email_verified_at.is_not(None), ~func.lower(User.email).in_(select(PlatformEmailSuppression.email)))) or 0
    return {"recipient_count": count, "policy": "All registered accounts with a verified email address, excluding unsubscribed addresses"}


@router.post("/email-campaigns", status_code=202)
def create_email_campaign(payload: EmailCampaignCreate,
    actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    if not payload.confirm_all_recipients:
        raise HTTPException(status_code=400, detail="Explicitly confirm that this message should be sent to all eligible recipients")
    email_settings = get_settings()
    if email_settings.email_campaign_provider.lower() == "resend":
        if not email_settings.resend_api_key:
            raise HTTPException(status_code=503, detail="Resend campaign delivery is not configured.")
    elif not email_settings.smtp_host:
        raise HTTPException(status_code=503, detail="Email delivery is not configured. Set SMTP_HOST, SMTP_PORT and sender credentials before sending campaigns.")
    suppressed = select(PlatformEmailSuppression.email)
    recipients = db.execute(select(User.id, User.email).where(User.email.is_not(None), User.email_verified_at.is_not(None), ~func.lower(User.email).in_(suppressed)).order_by(User.created_at.asc())).all()
    if not recipients:
        raise HTTPException(status_code=409, detail="There are no registered users with verified email addresses")
    campaign = PlatformEmailCampaign(created_by_user_id=actor.id, subject=payload.subject, body=payload.body,
        status="queued", recipient_count=len(recipients))
    db.add(campaign); db.flush()
    for user_id, email in recipients:
        token = secrets.token_urlsafe(32)
        db.add(PlatformEmailRecipient(campaign_id=campaign.id, user_id=user_id, email=email, status="pending", unsubscribe_token_hash=hashlib.sha256(token.encode()).hexdigest()))
    db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=None, action="email_campaign.queued",
        summary=f"Queued campaign '{payload.subject}' for {len(recipients)} verified registered email address(es)"))
    db.commit(); db.refresh(campaign)
    return {"id": str(campaign.id), "status": campaign.status, "recipient_count": campaign.recipient_count,
        "message": "Campaign durably queued. Configure the scheduled email worker to process it and retry temporary failures."}


@router.get("/email-campaigns/{campaign_id}/analytics")
def email_campaign_analytics(campaign_id: UUID, actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    campaign = db.get(PlatformEmailCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    counts = dict(db.execute(select(PlatformEmailRecipient.status, func.count(PlatformEmailRecipient.id)).where(
        PlatformEmailRecipient.campaign_id == campaign_id).group_by(PlatformEmailRecipient.status)).all())
    return {"campaign_id": str(campaign_id), "status": campaign.status, "recipient_count": campaign.recipient_count,
        "sent_count": counts.get("sent", 0) + counts.get("delivered", 0), "delivered_count": counts.get("delivered", 0), "pending_count": counts.get("pending", 0),
        "retry_count": counts.get("retry", 0), "failed_count": counts.get("failed", 0),
        "bounced_count": counts.get("bounced", 0), "complained_count": counts.get("unsubscribed", 0), "unsubscribed_count": counts.get("unsubscribed", 0)}


@router.post("/email-campaigns/{campaign_id}/retry-failed", status_code=202)
def retry_failed_campaign_recipients(campaign_id: UUID, actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> dict:
    _owner_only(actor)
    campaign = db.get(PlatformEmailCampaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    rows = db.scalars(select(PlatformEmailRecipient).where(
        PlatformEmailRecipient.campaign_id == campaign_id, PlatformEmailRecipient.status == "failed",
        ~func.lower(PlatformEmailRecipient.email).in_(select(PlatformEmailSuppression.email)))).all()
    for row in rows:
        row.status = "retry"; row.attempts = 0; row.next_attempt_at = None; row.error = None
    if rows:
        campaign.status = "sending"; campaign.completed_at = None; campaign.failed_count = max(0, campaign.failed_count - len(rows))
        db.add(PlatformAdminAudit(actor_user_id=actor.id, target_user_id=None, action="email_campaign.retry_requested",
            summary=f"Re-queued {len(rows)} failed recipients for campaign {campaign_id}"))
    db.commit()
    return {"campaign_id": str(campaign_id), "requeued": len(rows), "message": "Failed recipients re-queued; the scheduled worker will retry them."}


def _verify_resend_webhook(raw_body: bytes, headers, secret: str) -> bool:
    """Verify Svix HMAC signatures using the exact raw request bytes."""
    import base64
    import hashlib
    import hmac
    import time
    if not secret or not headers.get("svix-id") or not headers.get("svix-timestamp") or not headers.get("svix-signature"):
        return False
    try:
        timestamp = int(headers.get("svix-timestamp"))
        if abs(time.time() - timestamp) > 300:
            return False
        secret_value = secret.removeprefix("whsec_")
        key = base64.b64decode(secret_value + "=" * (-len(secret_value) % 4))
        signed = headers.get("svix-id").encode() + b"." + headers.get("svix-timestamp").encode() + b"." + raw_body
        expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
        for candidate in headers.get("svix-signature", "").split():
            if "," in candidate:
                version, signature = candidate.split(",", 1)
                if version == "v1" and hmac.compare_digest(signature, expected):
                    return True
        return False
    except (ValueError, TypeError):
        return False


@router.post("/public/email/resend-webhook", status_code=200)
async def resend_email_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Accept signed Resend delivery events; provider retries are deduplicated by Svix event ID."""
    settings = get_settings()
    raw_body = await request.body()
    if not _verify_resend_webhook(raw_body, request.headers, settings.resend_webhook_secret):
        raise HTTPException(status_code=400, detail="Invalid email provider webhook signature")
    import json
    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
    event_id = request.headers.get("svix-id")
    event_type = payload.get("type") if isinstance(payload, dict) else None
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    message_id = data.get("email_id") if isinstance(data, dict) else None
    if not event_type or not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Malformed email provider event")
    if db.scalar(select(PlatformEmailProviderEvent.id).where(PlatformEmailProviderEvent.provider_event_id == event_id)):
        return {"received": True, "duplicate": True}
    event = PlatformEmailProviderEvent(provider_event_id=event_id, provider_message_id=message_id, event_type=event_type)
    db.add(event)
    if message_id and event_type in {"email.delivered", "email.bounced", "email.complained"}:
        recipient = db.scalar(select(PlatformEmailRecipient).where(PlatformEmailRecipient.provider_message_id == message_id))
        if recipient:
            if event_type == "email.delivered":
                recipient.status = "delivered"
                recipient.delivered_at = datetime.now(timezone.utc)
                recipient.error = None
            else:
                recipient.status = "bounced" if event_type == "email.bounced" else "unsubscribed"
                recipient.bounced_at = datetime.now(timezone.utc) if event_type == "email.bounced" else recipient.bounced_at
                recipient.error = "Email provider reported a permanent bounce" if event_type == "email.bounced" else "Recipient reported this email as spam"
                normalized = recipient.email.strip().casefold()
                suppression = db.scalar(select(PlatformEmailSuppression).where(func.lower(PlatformEmailSuppression.email) == normalized))
                if suppression is None:
                    db.add(PlatformEmailSuppression(email=normalized, reason="bounce" if event_type == "email.bounced" else "complaint"))
    try:
        db.commit()
    except Exception:
        db.rollback()
        # A concurrent duplicate may have inserted the unique provider event ID.
        if db.scalar(select(PlatformEmailProviderEvent.id).where(PlatformEmailProviderEvent.provider_event_id == event_id)):
            return {"received": True, "duplicate": True}
        raise
    return {"received": True, "duplicate": False}


@router.post("/public/email/unsubscribe")
def unsubscribe_platform_email(token: str, db: Session = Depends(get_db)) -> dict:
    """One-click unsubscribe endpoint. The URL token is an opaque per-recipient capability."""
    if len(token) < 32 or len(token) > 128:
        raise HTTPException(status_code=400, detail="Invalid unsubscribe token")
    token_hash = token
    recipient = db.scalar(select(PlatformEmailRecipient).where(PlatformEmailRecipient.unsubscribe_token_hash == token_hash))
    if recipient is None:
        raise HTTPException(status_code=404, detail="Unsubscribe link is invalid or expired")
    normalized = recipient.email.strip().casefold()
    suppression = db.scalar(select(PlatformEmailSuppression).where(func.lower(PlatformEmailSuppression.email) == normalized))
    if suppression is None:
        db.add(PlatformEmailSuppression(email=normalized, reason="unsubscribe"))
    recipient.status = "unsubscribed"
    recipient.error = "Recipient opted out of platform announcements"
    db.commit()
    return {"message": "You have been unsubscribed from platform announcement emails."}
