"""Idempotent billing-notice enqueueing and bounded SMTP outbox delivery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.integrations.email import send_email
from app.models import BillingNotification, Membership, Subscription, SubscriptionRenewalAttempt

MAX_DELIVERY_ATTEMPTS = 5
SENDING_LEASE_MINUTES = 20


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _owner_email(db: Session, subscription: Subscription) -> str | None:
    owner = db.scalar(
        select(Membership)
        .where(Membership.organization_id == subscription.organization_id, Membership.role == "owner")
        .order_by(Membership.created_at.asc())
        .options(joinedload(Membership.user))
        .limit(1)
    )
    if owner is not None and owner.user is not None and owner.user.email:
        return owner.user.email
    # Paystack requires the original authorization email; it is the safe fallback when an owner
    # signed up through a phone-only identity and has no account email.
    return subscription.provider_authorization_email or None


def _money(subscription: Subscription) -> str:
    amount = (subscription.amount_minor or 0) / 100
    return f"{subscription.currency or 'NGN'} {amount:,.2f}"


def enqueue_billing_notification(
    db: Session,
    subscription: Subscription,
    *,
    notification_type: str,
    event_key: str,
    subject: str,
    body: str,
    attempt: SubscriptionRenewalAttempt | None = None,
) -> bool:
    """Add one notification to the outbox; the unique event key makes enqueue idempotent."""
    settings = get_settings()
    if not getattr(settings, "billing_renewal_notifications_enabled", False):
        return False
    recipient = _owner_email(db, subscription)
    if not recipient:
        return False
    existing = db.scalar(select(BillingNotification.id).where(BillingNotification.event_key == event_key))
    if existing is not None:
        return False
    try:
        with db.begin_nested():
            db.add(BillingNotification(
                organization_id=subscription.organization_id,
                subscription_id=subscription.id,
                renewal_attempt_id=attempt.id if attempt else None,
                event_key=event_key[:240],
                notification_type=notification_type,
                recipient_email=recipient[:320],
                subject=subject[:180],
                body=body,
                status="pending",
            ))
            db.flush()
    except IntegrityError:
        return False
    return True


def enqueue_automatic_renewal_activation_notices(
    db: Session, *, limit: int = 500,
) -> dict:
    """Queue the one-time advance notice required before an opted-in authorization can be charged."""
    settings = get_settings()
    if not getattr(settings, "billing_renewal_notifications_enabled", False):
        return {"enabled": False, "examined": 0, "queued": 0, "skipped": 0}
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    subscriptions = db.scalars(select(Subscription).where(
        Subscription.provider == "paystack",
        Subscription.status.in_(("active", "past_due")),
        Subscription.cancel_at_period_end.is_(False),
        Subscription.provider_authorization_reusable.is_(True),
        Subscription.provider_authorization_code_encrypted.is_not(None),
        Subscription.recurring_consent_at.is_not(None),
        Subscription.recurring_consent_version.is_not(None),
        Subscription.recurring_billing_notice_sent_at.is_(None),
    ).order_by(Subscription.created_at.asc()).limit(limit)).all()
    queued = skipped = 0
    for subscription in subscriptions:
        recipient = _owner_email(db, subscription)
        if not recipient:
            skipped += 1
            continue
        next_date = _utc(subscription.current_period_end).strftime("%B %d, %Y") if subscription.current_period_end else "your next billing date"
        subject = "Important: automatic renewal notice for your BizPilot Pro subscription"
        body = (
            "You previously gave explicit consent for BizPilot Pro to retain a reusable payment authorization "
            "for subscription renewals. We are preparing the automatic-renewal service for opted-in accounts.\n\n"
            f"Your next scheduled renewal is {next_date}. The expected amount is {_money(subscription)} "
            f"({subscription.billing_interval or 'monthly'}).\n\n"
            "No automatic charge will be made while automatic renewals remain disabled. Before any automatic "
            "renewal is attempted, this notice must be delivered and the billing service must be enabled. "
            "You can cancel the upcoming renewal or revoke the saved payment authorization from the Billing page.\n\n"
            "We will send advance reminders before subsequent renewal dates. If you do not want automatic "
            "renewal, please update your billing settings before the next renewal date."
        )
        event_key = f"automatic-renewal-activation:{subscription.id}:{subscription.recurring_consent_at.isoformat()}"
        if enqueue_billing_notification(
            db, subscription, notification_type="automatic_renewal_activation", event_key=event_key,
            subject=subject, body=body,
        ):
            queued += 1
        else:
            skipped += 1
    db.commit()
    return {"enabled": True, "examined": len(subscriptions), "queued": queued, "skipped": skipped}


def enqueue_due_renewal_reminders(
    db: Session, *, now: datetime | None = None, limit: int = 100,
) -> dict:
    """Queue one reminder inside the configured pre-renewal window for each eligible subscription."""
    settings = get_settings()
    if not getattr(settings, "billing_renewal_notifications_enabled", False):
        return {"enabled": False, "examined": 0, "queued": 0, "skipped": 0}
    if not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    now = now or datetime.now(timezone.utc)
    cutoff = now + timedelta(days=settings.billing_renewal_reminder_days)
    subscriptions = db.scalars(select(Subscription).where(
        Subscription.provider == "paystack",
        Subscription.status == "active",
        Subscription.current_period_end > now,
        Subscription.current_period_end <= cutoff,
        Subscription.cancel_at_period_end.is_(False),
        Subscription.provider_authorization_reusable.is_(True),
        Subscription.provider_authorization_code_encrypted.is_not(None),
        Subscription.recurring_consent_at.is_not(None),
        Subscription.recurring_consent_version.is_not(None),
        Subscription.recurring_billing_notice_sent_at.is_not(None),
    ).order_by(Subscription.current_period_end.asc()).limit(limit)).all()
    queued = skipped = 0
    for subscription in subscriptions:
        period_end = _utc(subscription.current_period_end)
        notice_sent_at = _utc(subscription.recurring_billing_notice_sent_at)
        # The activation notice itself serves as the advance reminder if it was delivered
        # inside the configured reminder window; avoid sending two emails together.
        if notice_sent_at >= period_end - timedelta(days=settings.billing_renewal_reminder_days):
            skipped += 1
            continue
        event_key = f"renewal-reminder:{subscription.id}:{period_end.isoformat()}"
        recipient = _owner_email(db, subscription)
        if not recipient:
            skipped += 1
            continue
        date_label = period_end.strftime("%B %d, %Y")
        subject = "Your BizPilot Pro subscription renewal is approaching"
        body = (
            f"Your {subscription.plan_id.title()} subscription is scheduled to renew on {date_label}.\n\n"
            f"Expected amount: {_money(subscription)} ({subscription.billing_interval or 'monthly'}).\n\n"
            "A reusable payment method and your recorded recurring-payment consent are on file. "
            + ("If automatic renewal is enabled for your account, the payment may be attempted on the renewal date. "
               if getattr(settings, "billing_renewals_enabled", False) else
               "Automatic renewal is currently disabled, so no automatic charge will be attempted while it remains disabled. ")
            + "You can review your plan, payment method, or cancellation settings from the Billing page in BizPilot Pro.\n\n"
            "If you have already cancelled or updated your billing settings, you can ignore this reminder."
        )
        if enqueue_billing_notification(
            db, subscription, notification_type="renewal_reminder", event_key=event_key,
            subject=subject, body=body,
        ):
            queued += 1
        else:
            skipped += 1
    db.commit()
    return {"enabled": True, "examined": len(subscriptions), "queued": queued, "skipped": skipped}


def process_billing_notification_outbox(
    db: Session, *, limit: int = 50, now: datetime | None = None,
) -> dict:
    """Deliver a bounded batch. SMTP is at-least-once if a worker dies after send but before commit."""
    settings = get_settings()
    if not getattr(settings, "billing_renewal_notifications_enabled", False):
        return {"enabled": False, "examined": 0, "sent": 0, "retrying": 0, "failed": 0}
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    now = now or datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=SENDING_LEASE_MINUTES)
    candidates = db.scalars(select(BillingNotification.id).where(or_(
        (BillingNotification.status == "pending") & (BillingNotification.next_attempt_at <= now),
        (BillingNotification.status == "sending") & (BillingNotification.updated_at <= stale_before),
    )).order_by(BillingNotification.created_at.asc()).limit(limit)).all()
    result = {"enabled": True, "examined": len(candidates), "sent": 0, "retrying": 0, "failed": 0}

    for notification_id in candidates:
        claim = db.execute(update(BillingNotification).where(
            BillingNotification.id == notification_id,
            or_(
                (BillingNotification.status == "pending") & (BillingNotification.next_attempt_at <= now),
                (BillingNotification.status == "sending") & (BillingNotification.updated_at <= stale_before),
            ),
        ).values(status="sending", attempt_count=BillingNotification.attempt_count + 1, updated_at=now))
        db.commit()
        if claim.rowcount != 1:
            continue
        notification = db.get(BillingNotification, notification_id)
        delivered = send_email(
            settings, notification.recipient_email, notification.subject, notification.body, log_body=False,
        )
        if delivered:
            notification.status = "sent"
            notification.sent_at = now
            notification.last_error_code = None
            if notification.notification_type == "automatic_renewal_activation":
                subscription = db.get(Subscription, notification.subscription_id) if notification.subscription_id else None
                if subscription is not None and subscription.recurring_billing_notice_sent_at is None:
                    subscription.recurring_billing_notice_sent_at = now
            result["sent"] += 1
        else:
            notification.last_error_code = "smtp_delivery_failed"
            if notification.attempt_count >= MAX_DELIVERY_ATTEMPTS:
                notification.status = "failed"
                result["failed"] += 1
            else:
                retry_minutes = (1, 5, 30, 120)[min(notification.attempt_count - 1, 3)]
                notification.status = "pending"
                notification.next_attempt_at = now + timedelta(minutes=retry_minutes)
                result["retrying"] += 1
        db.commit()
    return result


def enqueue_renewal_status_notice(
    db: Session, subscription: Subscription, attempt: SubscriptionRenewalAttempt,
    payment_amount_minor: int, payment_currency: str, payment_reference: str, status: str,
) -> bool:
    """Queue an action-required or failed-payment message once per renewal attempt."""
    if status == "needs_action":
        notification_type = "renewal_action_required"
        subject = "Action required to complete your BizPilot Pro renewal"
        message = (
            "Paystack needs you to complete an additional bank/card authentication step before this renewal can be confirmed. "
            "Sign in to BizPilot Pro, open Billing, and select Complete authentication. "
            "Your subscription has not been renewed yet; access may be limited after the grace period if payment is not completed."
        )
    elif status == "failed":
        notification_type = "renewal_payment_failed"
        subject = "Your BizPilot Pro subscription payment was not approved"
        message = (
            "Your bank did not approve the scheduled renewal payment. Your subscription has not been renewed. "
            "Please sign in to BizPilot Pro, open Billing, and choose an available payment method or contact your workspace owner. "
            "Your current access follows the subscription grace-period policy."
        )
    else:
        raise ValueError("Unsupported renewal notification status")
    amount = (payment_amount_minor or 0) / 100
    body = (
        f"{message}\n\n"
        f"Attempted amount: {payment_currency} {amount:,.2f}.\n"
        f"Renewal reference: {payment_reference}.\n\n"
        "For security, do not reply with your card number, PIN, password, or one-time code."
    )
    return enqueue_billing_notification(
        db, subscription, notification_type=notification_type,
        event_key=f"{notification_type}:{attempt.id}", subject=subject, body=body, attempt=attempt,
    )
