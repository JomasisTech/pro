"""Opt-in, one-charge-per-period Paystack renewal processing.

The unique subscription/period ledger deliberately prevents automatic recharging
of an ambiguous or failed attempt. Recovery is verification-only; a new charge
requires a later period or an explicit future customer action.
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.integrations.billing_crypto import decrypt_authorization_code
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.paystack_checkout import PaystackRetryWindowError
from app.models import Membership, Organization, PaymentTransaction, Subscription, SubscriptionRenewalAttempt
from app.modules.audit.activity import record_activity
from app.modules.billing.service import verify_and_activate
from app.modules.billing.notifications import enqueue_renewal_status_notice


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _call_charge(provider: PaymentProvider, **kwargs) -> dict:
    method = getattr(provider, "charge_authorization", None)
    if method is None:
        raise RuntimeError("The configured payment provider does not support authorization charges")
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(method(**kwargs))
    raise RuntimeError("Renewal processing must run in a dedicated synchronous scheduler process")


def _mark_past_due(db: Session, subscription: Subscription, *, now: datetime, grace_period_days: int, action: str, detail: str) -> None:
    organization = db.scalar(select(Organization).where(Organization.id == subscription.organization_id).with_for_update())
    if organization is None:
        return
    if subscription.status == "active":
        subscription.status = "past_due"
        subscription.grace_period_ends_at = _utc(subscription.current_period_end) + timedelta(days=grace_period_days)
    member = db.scalar(select(Membership).where(
        Membership.organization_id == organization.id
    ).order_by(Membership.role != "owner", Membership.created_at).options(joinedload(Membership.user)).limit(1))
    if member is not None:
        record_activity(db, member, action, "subscription", subscription.id, detail)


def process_due_subscription_renewals(
    db: Session, *, provider: PaymentProvider, limit: int = 50,
    now: datetime | None = None, grace_period_days: int | None = None,
) -> dict:
    """Charge each eligible subscription at most once for its current period boundary."""
    settings = get_settings()
    if not settings.billing_renewals_enabled:
        return {"enabled": False, "examined": 0, "charged": 0, "needs_action": 0, "failed": 0, "verification_pending": 0, "retry_scheduled": 0, "skipped": 0}
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if grace_period_days is None:
        grace_period_days = settings.billing_grace_period_days
    if not 0 <= grace_period_days <= 14:
        raise ValueError("grace_period_days must be between 0 and 14")
    now = now or datetime.now(timezone.utc)
    due = db.scalars(select(Subscription).where(
        Subscription.provider == "paystack",
        Subscription.status.in_(("active", "past_due")),
        Subscription.current_period_end.is_not(None),
        Subscription.current_period_end <= now,
        Subscription.cancel_at_period_end.is_(False),
        Subscription.provider_authorization_reusable.is_(True),
        Subscription.provider_authorization_code_encrypted.is_not(None),
        Subscription.recurring_consent_at.is_not(None),
        Subscription.recurring_consent_version.is_not(None),
        Subscription.recurring_billing_notice_sent_at.is_not(None),
    ).order_by(Subscription.current_period_end.asc()).limit(limit)).all()
    result = {"enabled": True, "examined": len(due), "charged": 0, "needs_action": 0, "failed": 0, "verification_pending": 0, "retry_scheduled": 0, "skipped": 0}

    for candidate in due:
        subscription = db.scalar(select(Subscription).where(Subscription.id == candidate.id).with_for_update())
        if subscription is None or subscription.current_period_end is None or subscription.cancel_at_period_end:
            result["skipped"] += 1
            continue
        period_end = _utc(subscription.current_period_end)
        existing = db.scalar(select(SubscriptionRenewalAttempt).where(
            SubscriptionRenewalAttempt.subscription_id == subscription.id,
            SubscriptionRenewalAttempt.period_end == period_end,
        ).with_for_update())
        if existing is not None:
            if existing.status == "verification_pending":
                payment = db.get(PaymentTransaction, existing.payment_transaction_id)
                if payment is not None:
                    try:
                        verify_and_activate(db, reference=payment.reference, provider=provider,
                                            expected_organization_id=payment.organization_id)
                    except Exception:
                        result["verification_pending"] += 1
                    else:
                        existing.status = "paid"
                        existing.completed_at = now
                        db.commit()
                        result["charged"] += 1
                else:
                    result["skipped"] += 1
            else:
                result["skipped"] += 1
            continue

        try:
            authorization_code = decrypt_authorization_code(subscription.provider_authorization_code_encrypted)
        except (RuntimeError, ValueError, TypeError):
            result["skipped"] += 1
            continue
        reference = "bp-renew-" + secrets.token_hex(20)
        payment = PaymentTransaction(
            organization_id=subscription.organization_id,
            provider="paystack", reference=reference, plan_id=subscription.plan_id,
            billing_interval=subscription.billing_interval or "monthly",
            amount_minor=subscription.amount_minor or 0, currency=subscription.currency or "NGN",
            customer_email=subscription.provider_authorization_email or "", status="pending",
        )
        if payment.amount_minor <= 0 or not payment.customer_email:
            result["skipped"] += 1
            continue
        db.add(payment)
        db.flush()
        attempt = SubscriptionRenewalAttempt(
            subscription_id=subscription.id, payment_transaction_id=payment.id,
            period_end=period_end, status="processing",
        )
        db.add(attempt)
        member = db.scalar(select(Membership).where(
            Membership.organization_id == subscription.organization_id
        ).order_by(Membership.role != "owner", Membership.created_at)
         .options(joinedload(Membership.user)).limit(1))
        if member is not None:
            record_activity(db, member, "billing.renewal_attempt_started", "subscription", subscription.id,
                            f"Started scheduled {payment.billing_interval} Paystack renewal attempt")
        # Persist the unique period lock and reference before calling the payment network.
        db.commit()
        try:
            charge = _call_charge(
                provider, authorization_code=authorization_code,
                email=payment.customer_email, amount_minor=payment.amount_minor,
                currency=payment.currency, reference=reference,
                metadata={"subscription_id": str(subscription.id), "renewal_attempt_id": str(attempt.id),
                          "plan_id": payment.plan_id, "billing_interval": payment.billing_interval},
                callback_url=f"{settings.frontend_base_url.rstrip('/')}/billing?renewal_reference={reference}",
            )
        except PaystackRetryWindowError as exc:
            # Re-enter only when Paystack explicitly supplies a retry window (e.g. its
            # recurring-card regulator). One delayed re-entry maximum for this period.
            retry_at = _utc(exc.retry_at)
            if attempt.retry_count < 1 and now < retry_at <= now + timedelta(hours=24):
                attempt.status = "retry_scheduled"
                attempt.retry_at = retry_at
                attempt.failure_code = "provider_directed_retry_window"
                attempt.provider_status = "retry_scheduled"
                db.commit()
                result["retry_scheduled"] += 1
            else:
                attempt.status = "failed"
                attempt.failure_code = "provider_retry_window_invalid_or_exhausted"
                payment.status = "failed"
                _mark_past_due(db, subscription, now=now, grace_period_days=grace_period_days,
                               action="billing.renewal_failed", detail="Paystack did not provide an eligible further retry window")
                enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "failed")
                db.commit()
                result["failed"] += 1
            continue
        except Exception:
            # Network failure may be ambiguous: never send a second charge for this period.
            attempt.status = "verification_pending"
            attempt.failure_code = "provider_response_unavailable"
            db.commit()
            result["verification_pending"] += 1
            continue

        provider_status = str(charge.get("status", "unknown")).lower() if isinstance(charge, dict) else "unknown"
        attempt.provider_status = provider_status[:32]
        if charge.get("paused") is True or (isinstance(charge.get("authorization_url"), str) and charge.get("authorization_url")):
            provider_status = "customer_action_required"
            attempt.provider_status = provider_status
        if provider_status == "success":
            try:
                verify_and_activate(db, reference=reference, provider=provider,
                                    expected_organization_id=subscription.organization_id)
            except Exception:
                attempt = db.scalar(select(SubscriptionRenewalAttempt).where(SubscriptionRenewalAttempt.id == attempt.id))
                if attempt is not None:
                    attempt.status = "verification_pending"
                    attempt.failure_code = "server_verification_pending"
                    db.commit()
                result["verification_pending"] += 1
            else:
                attempt = db.scalar(select(SubscriptionRenewalAttempt).where(SubscriptionRenewalAttempt.id == attempt.id))
                if attempt is not None:
                    attempt.status = "paid"
                    attempt.completed_at = now
                    db.commit()
                result["charged"] += 1
        elif charge.get("paused") is True or (isinstance(charge.get("authorization_url"), str) and charge.get("authorization_url")) or provider_status in {"pending", "ongoing", "otp", "queued", "customer_action_required"}:
            attempt.status = "needs_action"
            attempt.failure_code = "customer_action_required"
            authorization_url = charge.get("authorization_url")
            if isinstance(authorization_url, str) and len(authorization_url) <= 500:
                parsed_url = urlsplit(authorization_url)
                if parsed_url.scheme == "https" and parsed_url.hostname == "checkout.paystack.com" and parsed_url.username is None and parsed_url.password is None:
                    attempt.authorization_url = authorization_url
            _mark_past_due(db, subscription, now=now, grace_period_days=grace_period_days,
                           action="billing.renewal_requires_customer_action",
                           detail="Paystack requested additional customer authentication for a subscription renewal")
            enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "needs_action")
            db.commit()
            result["needs_action"] += 1
        elif provider_status in {"failed", "abandoned", "reversed"}:
            attempt.status = "failed"
            attempt.failure_code = "provider_declined"
            payment.status = "failed"
            _mark_past_due(db, subscription, now=now, grace_period_days=grace_period_days,
                           action="billing.renewal_failed", detail="Paystack declined the scheduled subscription renewal")
            enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "failed")
            db.commit()
            result["failed"] += 1
        else:
            attempt.status = "verification_pending"
            attempt.failure_code = "unrecognized_provider_status"
            db.commit()
            result["verification_pending"] += 1

    return result


def process_provider_directed_renewal_retries(
    db: Session, *, provider: PaymentProvider, limit: int = 50, now: datetime | None = None,
) -> dict:
    """Perform at most one retry, and only after Paystack explicitly supplied retry_at.

    Ambiguous timeouts, OTP/3DS challenges, ordinary declines and generic HTTP failures
    are never eligible. The provider-rejected reference is retained for audit and
    a fresh unique reference is generated for the permitted new transaction request.
    """
    settings = get_settings()
    if not settings.billing_renewals_enabled:
        return {"enabled": False, "examined": 0, "retried": 0, "verification_pending": 0, "failed": 0, "skipped": 0}
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    now = now or datetime.now(timezone.utc)
    candidates = db.scalars(select(SubscriptionRenewalAttempt.id).where(
        SubscriptionRenewalAttempt.status == "retry_scheduled",
        SubscriptionRenewalAttempt.retry_at <= now,
    ).order_by(SubscriptionRenewalAttempt.retry_at.asc()).limit(limit)).all()
    result = {"enabled": True, "examined": len(candidates), "retried": 0, "verification_pending": 0, "failed": 0, "skipped": 0}
    for attempt_id in candidates:
        attempt = db.scalar(select(SubscriptionRenewalAttempt).where(
            SubscriptionRenewalAttempt.id == attempt_id
        ).with_for_update())
        if attempt is None or attempt.status != "retry_scheduled" or attempt.retry_at is None or _utc(attempt.retry_at) > now:
            result["skipped"] += 1
            continue
        if attempt.retry_count >= 1:
            attempt.status = "failed"
            attempt.failure_code = "provider_retry_limit_reached"
            db.commit()
            result["failed"] += 1
            continue
        subscription = db.get(Subscription, attempt.subscription_id)
        payment = db.get(PaymentTransaction, attempt.payment_transaction_id)
        if (subscription is None or payment is None or payment.status != "pending"
                or subscription.cancel_at_period_end or not subscription.provider_authorization_reusable
                or not subscription.provider_authorization_code_encrypted
                or subscription.recurring_consent_at is None or subscription.recurring_consent_version is None
                or subscription.current_period_end is None
                or _utc(subscription.current_period_end) != _utc(attempt.period_end)):
            attempt.status = "failed"
            attempt.failure_code = "retry_no_longer_eligible"
            db.commit()
            result["skipped"] += 1
            continue
        try:
            authorization_code = decrypt_authorization_code(subscription.provider_authorization_code_encrypted)
        except (RuntimeError, ValueError, TypeError):
            attempt.status = "failed"
            attempt.failure_code = "authorization_unavailable_for_retry"
            db.commit()
            result["failed"] += 1
            continue
        # The regulator explicitly rejected the first request before it could be
        # fulfilled. Paystack requires a unique reference per transaction, so keep
        # the rejected reference for audit and assign a fresh reference to this retry.
        attempt.previous_reference = payment.reference
        payment.reference = "bp-renew-retry-" + secrets.token_hex(20)
        attempt.status = "processing"
        attempt.retry_count += 1
        attempt.retry_at = None
        attempt.attempted_at = now
        db.commit()
        try:
            charge = _call_charge(
                provider, authorization_code=authorization_code, email=payment.customer_email,
                amount_minor=payment.amount_minor, currency=payment.currency, reference=payment.reference,
                metadata={"subscription_id": str(subscription.id), "renewal_attempt_id": str(attempt.id),
                          "plan_id": payment.plan_id, "billing_interval": payment.billing_interval,
                          "provider_directed_retry": True},
                callback_url=f"{settings.frontend_base_url.rstrip('/')}/billing?renewal_reference={payment.reference}",
            )
        except PaystackRetryWindowError:
            # Paystack has already given this billing period its single delayed re-entry.
            attempt.status = "failed"
            attempt.failure_code = "provider_retry_limit_reached"
            payment.status = "failed"
            _mark_past_due(db, subscription, now=now, grace_period_days=settings.billing_grace_period_days,
                           action="billing.renewal_failed", detail="Paystack still restricted the card after the one permitted provider-directed retry")
            enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "failed")
            db.commit()
            result["failed"] += 1
            continue
        except Exception:
            # Generic errors can be ambiguous; never issue another charge. Verify only.
            attempt.status = "verification_pending"
            attempt.failure_code = "provider_directed_retry_response_ambiguous"
            db.commit()
            result["verification_pending"] += 1
            continue
        provider_status = str(charge.get("status", "unknown")).lower() if isinstance(charge, dict) else "unknown"
        attempt.provider_status = provider_status[:32]
        if provider_status == "success":
            try:
                verify_and_activate(db, reference=payment.reference, provider=provider,
                                    expected_organization_id=payment.organization_id)
            except Exception:
                attempt = db.get(SubscriptionRenewalAttempt, attempt_id)
                if attempt is not None:
                    attempt.status = "verification_pending"
                    attempt.failure_code = "retry_server_verification_pending"
                    db.commit()
                result["verification_pending"] += 1
            else:
                attempt = db.get(SubscriptionRenewalAttempt, attempt_id)
                if attempt is not None:
                    attempt.status = "paid"
                    attempt.completed_at = now
                    attempt.failure_code = None
                    db.commit()
                result["retried"] += 1
        elif charge.get("paused") is True or charge.get("authorization_url") or provider_status in {"pending", "ongoing", "otp", "queued", "customer_action_required"}:
            attempt.status = "needs_action"
            attempt.failure_code = "customer_action_required"
            authorization_url = charge.get("authorization_url")
            if isinstance(authorization_url, str) and len(authorization_url) <= 500:
                parsed_url = urlsplit(authorization_url)
                if parsed_url.scheme == "https" and parsed_url.hostname == "checkout.paystack.com" and parsed_url.username is None and parsed_url.password is None:
                    attempt.authorization_url = authorization_url
            _mark_past_due(db, subscription, now=now, grace_period_days=settings.billing_grace_period_days,
                           action="billing.renewal_requires_customer_action",
                           detail="Paystack requested customer authentication during a provider-directed retry")
            enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "needs_action")
            db.commit()
            result["retried"] += 1
        elif provider_status in {"failed", "abandoned", "reversed"}:
            attempt.status = "failed"
            attempt.failure_code = "provider_declined_after_directed_retry"
            payment.status = "failed"
            _mark_past_due(db, subscription, now=now, grace_period_days=settings.billing_grace_period_days,
                           action="billing.renewal_failed", detail="Paystack declined the one permitted provider-directed retry")
            enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "failed")
            db.commit()
            result["failed"] += 1
        else:
            attempt.status = "verification_pending"
            attempt.failure_code = "retry_unrecognized_provider_status"
            db.commit()
            result["verification_pending"] += 1
    return result
