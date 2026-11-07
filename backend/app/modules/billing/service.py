"""Trusted payment verification and subscription fulfillment workflows."""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.integrations.payments.base import PaymentProvider
from app.integrations.billing_crypto import encrypt_authorization_code
from app.config import get_settings
from app.integrations.payments.paystack_transactions import transaction_matches_expected
from app.models import Membership, Organization, PaymentTransaction, Subscription
from app.modules.audit.activity import record_activity


logger = logging.getLogger(__name__)


class PaymentVerificationUnavailable(RuntimeError):
    """The provider could not be reached or did not return a verifiable result."""


class PaymentVerificationMismatch(RuntimeError):
    """Provider data did not match the server-created transaction snapshot."""


def _add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def verify_and_activate(
    db: Session,
    *,
    reference: str,
    provider: PaymentProvider,
    expected_organization_id: UUID | None = None,
) -> PaymentTransaction:
    """Verify a payment with its processor and atomically apply its subscription."""
    payment = db.scalar(
        select(PaymentTransaction).where(PaymentTransaction.reference == reference).with_for_update()
    )
    if payment is None or (expected_organization_id and payment.organization_id != expected_organization_id):
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    if payment.provider != provider.provider_id:
        raise HTTPException(status_code=400, detail="Payment provider does not match this transaction")
    if payment.status == "paid":
        return payment
    if payment.status in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="This payment attempt is no longer active. Please start checkout again.")

    try:
        verified = _run_provider_verification(provider, reference)
    except Exception as exc:
        db.rollback()
        raise PaymentVerificationUnavailable("The payment provider could not verify this transaction. Please retry shortly.") from exc

    if not transaction_matches_expected(
        verified,
        reference=payment.reference,
        amount_minor=payment.amount_minor,
        currency=payment.currency,
        customer_email=payment.customer_email,
    ):
        provider_status = verified.get("status") if isinstance(verified, dict) else None
        if provider_status in {"failed", "abandoned" }:
            payment.status = "failed"
            db.commit()
            raise HTTPException(status_code=409, detail="The payment was not completed successfully.")
        db.rollback()
        raise PaymentVerificationMismatch("The provider transaction did not match the expected amount, currency, reference and customer.")

    organization = db.scalar(select(Organization).where(Organization.id == payment.organization_id).with_for_update())
    if organization is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="The workspace for this payment no longer exists")

    now = datetime.now(timezone.utc)
    subscription = db.scalar(select(Subscription).where(
        Subscription.organization_id == organization.id
    ).with_for_update())
    if subscription is None:
        subscription = Subscription(organization_id=organization.id)
        db.add(subscription)
        db.flush()

    period_start = now
    if (
        subscription.status in {"active", "past_due"}
        and subscription.plan_id == payment.plan_id
        and subscription.current_period_end is not None
    ):
        previous_end = subscription.current_period_end
        if previous_end.tzinfo is None:
            previous_end = previous_end.replace(tzinfo=timezone.utc)
        period_start = max(now, previous_end)

    months = 12 if payment.billing_interval == "annual" else 1
    subscription.provider = payment.provider
    subscription.plan_id = payment.plan_id
    subscription.status = "active"
    subscription.amount_minor = payment.amount_minor
    subscription.currency = payment.currency
    subscription.billing_interval = payment.billing_interval
    customer = verified.get("customer") if isinstance(verified, dict) else None
    subscription.provider_customer_code = str(customer.get("customer_code"))[:100] if isinstance(customer, dict) and customer.get("customer_code") else None
    authorization = verified.get("authorization") if isinstance(verified, dict) else None
    if payment.recurring_consent_at is not None and isinstance(authorization, dict) and authorization.get("reusable") is True:
        authorization_code = authorization.get("authorization_code")
        authorization_email = payment.customer_email
        if isinstance(authorization_code, str) and authorization_code.strip() and isinstance(authorization_email, str) and authorization_email.strip():
            # Encryption is deliberately optional at checkout; without the dedicated key we retain consent evidence
            # but never persist a reusable credential in plaintext or make it available for charging.
            if get_settings().billing_authorization_encryption_key:
                try:
                    encrypted_authorization = encrypt_authorization_code(authorization_code)
                except RuntimeError:
                    # A malformed/missing key must never break fulfillment of an already-paid first charge.
                    logger.warning("Reusable Paystack authorization was not retained because billing encryption is unavailable")
                else:
                    subscription.provider_authorization_code_encrypted = encrypted_authorization
                    subscription.provider_authorization_email = authorization_email[:320]
                    subscription.provider_authorization_reusable = True
                    card = authorization.get("card") if isinstance(authorization.get("card"), dict) else {}
                    last4 = card.get("last4")
                    subscription.authorization_card_last4 = str(last4)[-4:] if isinstance(last4, (str, int)) and str(last4).isdigit() else None
                    card_type = card.get("type")
                    subscription.authorization_card_type = str(card_type)[:40] if isinstance(card_type, str) else None
                    exp_month = card.get("exp_month")
                    exp_year = card.get("exp_year")
                    subscription.authorization_card_exp_month = str(exp_month)[:2] if exp_month is not None else None
                    subscription.authorization_card_exp_year = str(exp_year)[:4] if exp_year is not None else None
                    subscription.recurring_consent_at = payment.recurring_consent_at
                    subscription.recurring_consent_version = payment.recurring_consent_version
                    # A newly saved authorization requires a fresh activation notice before any auto-charge.
                    subscription.recurring_billing_notice_sent_at = None
    subscription.current_period_start = period_start
    subscription.current_period_end = _add_months(period_start, months)
    subscription.cancel_at_period_end = False
    subscription.grace_period_ends_at = None
    subscription.cancellation_requested_at = None

    organization.plan = payment.plan_id
    payment.status = "paid"
    payment.paid_at = now
    provider_id = verified.get("id") if isinstance(verified, dict) else None
    if provider_id is not None:
        payment.provider_transaction_id = str(provider_id)[:80]

    actor_membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization.id,
            Membership.user_id == payment.initiated_by_user_id,
        ).options(joinedload(Membership.user))
    ) if payment.initiated_by_user_id else None
    if actor_membership is None:
        actor_membership = db.scalar(
            select(Membership).where(Membership.organization_id == organization.id)
            .order_by(Membership.role != "owner", Membership.created_at)
            .options(joinedload(Membership.user)).limit(1)
        )
    if actor_membership is None:
        db.rollback()
        raise HTTPException(status_code=409, detail="No workspace member is available for the billing audit record")

    record_activity(
        db, actor_membership, "billing.subscription_activated", "subscription", subscription.id,
        f"Activated {payment.plan_id.title()} subscription ({payment.currency} {payment.amount_minor / 100:.2f}, {payment.billing_interval})",
    )
    db.commit()
    db.refresh(payment)
    return payment


def _run_provider_verification(provider: PaymentProvider, reference: str) -> dict:
    """Run the async provider method from a synchronous FastAPI workflow safely."""
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(provider.verify_transaction(reference))
    # The route is synchronous, so this is only a defensive fallback for direct callers.
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, provider.verify_transaction(reference)).result(timeout=20)
