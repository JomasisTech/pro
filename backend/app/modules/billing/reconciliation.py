"""Scheduled reconciliation for pending payment attempts.

This job never trusts webhook payloads or browser callbacks. It asks the configured
payment adapter to verify each old pending reference, then uses the same locked,
idempotent fulfillment service as checkout return and webhook processing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.payments.registry import PaymentProviderUnavailable, get_payment_provider
from app.models import PaymentTransaction
from app.modules.billing.service import (
    PaymentVerificationMismatch,
    PaymentVerificationUnavailable,
    verify_and_activate,
)


def reconcile_pending_payments(
    db: Session,
    *,
    limit: int = 50,
    older_than_minutes: int = 10,
    provider_factory: Callable = get_payment_provider,
) -> dict:
    """Reconcile a bounded batch of old pending payments; safe to run repeatedly."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=older_than_minutes)
    candidates = db.scalars(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.status == "pending",
            PaymentTransaction.created_at <= cutoff,
        )
        .order_by(PaymentTransaction.created_at.asc())
        .limit(limit)
    ).all()

    summary = {
        "examined": len(candidates),
        "activated": 0,
        "failed": 0,
        "needs_attention": 0,
        "provider_unavailable": 0,
        "skipped_provider": 0,
    }

    providers = {}
    for candidate in candidates:
        # verify_and_activate obtains a row lock and re-checks paid state before
        # fulfillment. Repeated scheduler runs therefore cannot extend twice.
        if candidate.provider != "paystack":
            summary["skipped_provider"] += 1
            continue
        try:
            provider = providers.get(candidate.provider)
            if provider is None:
                provider = provider_factory(candidate.provider)
                providers[candidate.provider] = provider
            payment = verify_and_activate(db, reference=candidate.reference, provider=provider)
            if payment.status == "paid":
                summary["activated"] += 1
        except PaymentVerificationUnavailable:
            db.rollback()
            summary["provider_unavailable"] += 1
        except PaymentVerificationMismatch:
            db.rollback()
            summary["needs_attention"] += 1
        except HTTPException as exc:
            db.rollback()
            if exc.status_code == 409:
                # Provider explicitly reported a failed/abandoned payment, or
                # another worker already completed/cancelled this attempt.
                fresh = db.scalar(select(PaymentTransaction).where(PaymentTransaction.id == candidate.id))
                if fresh is not None and fresh.status == "failed":
                    summary["failed"] += 1
                elif fresh is not None and fresh.status == "paid":
                    summary["already_paid"] += 1
                else:
                    summary["needs_attention"] += 1
            else:
                summary["needs_attention"] += 1
        except PaymentProviderUnavailable:
            db.rollback()
            summary["provider_unavailable"] += 1
        except Exception:
            db.rollback()
            summary["needs_attention"] += 1

    return summary
