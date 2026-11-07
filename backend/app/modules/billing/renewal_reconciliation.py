"""Verification-only recovery for interrupted automatic-renewal attempts.

This module never starts a new charge. It verifies the durable Paystack reference
for an existing attempt and only fulfills a subscription after trusted verification.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.payments.registry import PaymentProviderUnavailable, get_payment_provider
from app.models import PaymentTransaction, Subscription, SubscriptionRenewalAttempt
from app.modules.billing.notifications import enqueue_renewal_status_notice
from app.modules.billing.renewals import _mark_past_due, _utc
from app.modules.billing.service import (
    PaymentVerificationMismatch,
    PaymentVerificationUnavailable,
    verify_and_activate,
)


def reconcile_renewal_attempts(
    db: Session,
    *,
    limit: int = 50,
    older_than_minutes: int = 10,
    provider_factory: Callable = get_payment_provider,
    now: datetime | None = None,
) -> dict:
    """Recover old uncertain attempts by verification only; never issue another charge."""
    if not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if not 1 <= older_than_minutes <= 1440:
        raise ValueError("older_than_minutes must be between 1 and 1440")

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=older_than_minutes)
    candidates = db.scalars(
        select(SubscriptionRenewalAttempt.id)
        .where(or_(
            SubscriptionRenewalAttempt.status == "verification_pending",
            (SubscriptionRenewalAttempt.status == "processing") &
            (SubscriptionRenewalAttempt.attempted_at <= cutoff),
        ))
        .order_by(SubscriptionRenewalAttempt.attempted_at.asc())
        .limit(limit)
    ).all()
    summary = {
        "examined": len(candidates), "activated": 0, "already_paid": 0,
        "failed": 0, "provider_unavailable": 0, "needs_attention": 0,
        "skipped": 0,
    }
    providers = {}

    for attempt_id in candidates:
        attempt = db.scalar(
            select(SubscriptionRenewalAttempt)
            .where(SubscriptionRenewalAttempt.id == attempt_id)
            .with_for_update()
        )
        if attempt is None or attempt.status not in {"verification_pending", "processing"}:
            summary["skipped"] += 1
            continue

        if attempt.status == "processing":
            # A worker may have died after persisting the attempt but before saving
            # the provider response. Treat it as uncertain, not as permission to charge.
            if _utc(attempt.attempted_at) > cutoff:
                summary["skipped"] += 1
                continue
            attempt.status = "verification_pending"
            attempt.failure_code = "stale_processing_recovery"
            db.commit()

        payment_id = attempt.payment_transaction_id
        subscription_id = attempt.subscription_id
        payment = db.get(PaymentTransaction, payment_id)
        subscription = db.get(Subscription, subscription_id)
        if payment is None or subscription is None:
            attempt.failure_code = "renewal_recovery_record_missing"
            db.commit()
            summary["needs_attention"] += 1
            continue
        if payment.status == "paid":
            attempt.status = "paid"
            attempt.completed_at = attempt.completed_at or now
            attempt.authorization_url = None
            db.commit()
            summary["already_paid"] += 1
            continue
        if payment.provider != "paystack":
            summary["skipped"] += 1
            continue

        try:
            provider = providers.get(payment.provider)
            if provider is None:
                provider = provider_factory(payment.provider)
                providers[payment.provider] = provider
            verified_payment = verify_and_activate(
                db, reference=payment.reference, provider=provider,
                expected_organization_id=payment.organization_id,
            )
            attempt = db.get(SubscriptionRenewalAttempt, attempt_id)
            if attempt is not None and verified_payment.status == "paid":
                attempt.status = "paid"
                attempt.completed_at = now
                attempt.authorization_url = None
                attempt.failure_code = None
                db.commit()
                summary["activated"] += 1
        except PaymentVerificationUnavailable:
            db.rollback()
            summary["provider_unavailable"] += 1
        except PaymentVerificationMismatch:
            db.rollback()
            fresh = db.get(SubscriptionRenewalAttempt, attempt_id)
            if fresh is not None:
                fresh.status = "verification_pending"
                fresh.failure_code = "verification_mismatch_review_required"
                db.commit()
            summary["needs_attention"] += 1
        except PaymentProviderUnavailable:
            db.rollback()
            summary["provider_unavailable"] += 1
        except HTTPException as exc:
            db.rollback()
            fresh_attempt = db.get(SubscriptionRenewalAttempt, attempt_id)
            fresh_payment = db.get(PaymentTransaction, payment_id)
            fresh_subscription = db.get(Subscription, subscription_id)
            if fresh_attempt is None or fresh_payment is None or fresh_subscription is None:
                summary["needs_attention"] += 1
                continue
            if fresh_payment.status == "paid":
                fresh_attempt.status = "paid"
                fresh_attempt.completed_at = fresh_attempt.completed_at or now
                fresh_attempt.authorization_url = None
                db.commit()
                summary["already_paid"] += 1
            elif fresh_payment.status == "failed":
                fresh_attempt.status = "failed"
                fresh_attempt.failure_code = "provider_declined"
                fresh_attempt.authorization_url = None
                settings = get_settings()
                _mark_past_due(
                    db, fresh_subscription, now=now,
                    grace_period_days=settings.billing_grace_period_days,
                    action="billing.renewal_failed",
                    detail="Paystack verification confirmed that the interrupted subscription renewal was declined",
                )
                enqueue_renewal_status_notice(
                    db, fresh_subscription, fresh_attempt, fresh_payment.amount_minor,
                    fresh_payment.currency, fresh_payment.reference, "failed",
                )
                db.commit()
                summary["failed"] += 1
            else:
                fresh_attempt.failure_code = f"verification_http_{exc.status_code}"[:80]
                db.commit()
                summary["needs_attention"] += 1
        except Exception:
            db.rollback()
            fresh = db.get(SubscriptionRenewalAttempt, attempt_id)
            if fresh is not None:
                fresh.failure_code = "renewal_reconciliation_unexpected_error"
                db.commit()
            summary["needs_attention"] += 1

    return summary
