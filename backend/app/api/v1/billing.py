"""Billing catalog, customer checkout, verified payment fulfillment and price administration."""
import hashlib
import json
import secrets
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.core.demo import is_demo_platform_admin
from app.core.database import get_db
from app.core.plans import PLAN_LIMITS, PLAN_NAMES
from app.integrations.payments.base import CheckoutRequest, PROVIDER_CATALOG
from app.integrations.payments.registry import PaymentProviderUnavailable, get_payment_provider
from app.models import PaymentTransaction, PaymentWebhookEvent, Subscription, PaymentAdjustment
from app.api.v1.organizations import require_roles
from app.modules.billing.service import PaymentVerificationMismatch, PaymentVerificationUnavailable, verify_and_activate
from app.models import BillingPrice, BillingPriceChange, User, Membership, SubscriptionRenewalAttempt, PlatformAdminRole
from app.modules.billing.notifications import enqueue_renewal_status_notice

router = APIRouter(prefix="/billing", tags=["billing"])

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class PriceUpdateRequest(BaseModel):
    plan_id: str = Field(pattern=r"^(standard|premium)$")
    currency: str = Field(pattern=r"^(NGN|USD)$")
    billing_interval: str = Field(pattern=r"^(monthly|annual)$")
    amount_minor: int = Field(gt=0, le=100_000_000_000)
    enabled: bool = True


def _is_platform_admin(user: User) -> bool:
    allowed = {item.strip().casefold() for item in get_settings().platform_admin_emails.split(",") if item.strip()}
    # Require a verified email so an unverified registration cannot claim a configured admin address.
    return is_demo_platform_admin(user, get_settings()) or bool(user.email and user.email_verified_at is not None and user.email.casefold() in allowed)


def require_platform_admin(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> User:
    delegated = db.scalar(select(PlatformAdminRole).where(PlatformAdminRole.user_id == current_user.id))
    if not _is_platform_admin(current_user) and delegated is None:
        raise HTTPException(status_code=403, detail="Platform administrator access is required")
    # MFA remains mandatory everywhere except the explicitly isolated demo identity.
    if not is_demo_platform_admin(current_user, get_settings()) and (not current_user.totp_enabled or not current_user.totp_secret):
        raise HTTPException(status_code=403, detail="Platform administrator MFA is required. Enable authenticator-based two-factor authentication in account security, then sign in again.")
    return current_user


def require_platform_permission(permission: str):
    """Backend authorization for delegated admins; configured owners have all permissions."""
    def dependency(actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)) -> User:
        if _is_platform_admin(actor):
            return actor
        assignment = db.scalar(select(PlatformAdminRole).where(PlatformAdminRole.user_id == actor.id))
        role_permissions = {
            "support": {"customers.read", "customers.support", "activity.read", "login_events.read"},
            "finance": {"finance.read", "finance.manage", "customers.read"},
            "operations": {"operations.read", "operations.manage", "customers.read", "activity.read", "login_events.read"},
            "viewer": {"overview.read", "customers.read", "activity.read", "login_events.read"},
        }
        if assignment is None or permission not in role_permissions.get(assignment.role, set()):
            raise HTTPException(status_code=403, detail="Your platform administrator role does not permit this action")
        return actor
    return dependency


def _price_dict(price: BillingPrice) -> dict:
    return {
        "id": str(price.id), "plan_id": price.plan_id, "currency": price.currency,
        "billing_interval": price.billing_interval, "amount_minor": price.amount_minor,
        "enabled": price.enabled, "updated_at": price.updated_at,
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    prices = db.scalars(select(BillingPrice).order_by(BillingPrice.plan_id, BillingPrice.currency, BillingPrice.billing_interval)).all()
    configured = bool(prices)
    return {
        "prices_configured": configured,
        "plans": [
            {"id": key, "name": PLAN_NAMES[key], "limits": limits,
             "prices": [_price_dict(p) for p in prices if p.plan_id == key]}
            for key, limits in PLAN_LIMITS.items()
        ],
        "providers": PROVIDER_CATALOG,
        "payment_provider_ready": bool(settings.paystack_secret_key and settings.paystack_public_key),
        "checkout_enabled": bool(settings.paystack_secret_key and settings.paystack_public_key),
        "message": "Checkout initialization requires Paystack public and secret keys. Configure the webhook signing secret for modern signature verification.",
    }


@router.get("/readiness")
def billing_readiness() -> dict:
    settings = get_settings()
    paystack_ready = bool(settings.paystack_secret_key and settings.paystack_public_key)
    return {
        "provider": "paystack",
        "providers": {
            "paystack": {"implemented": True, "credentials_configured": paystack_ready,
                          "webhook_secret_configured": bool(settings.paystack_webhook_secret)},
            "paypal": {"implemented": False, "status": "future"},
            "flutterwave": {"implemented": False, "status": "future"},
        },
        "checkout_enabled": paystack_ready,
        "webhooks_enabled": bool(settings.paystack_webhook_secret or settings.paystack_secret_key),
        "reason": None if paystack_ready else "Configure Paystack public and secret keys to enable customer checkout.",
    }


class CheckoutRequestBody(BaseModel):
    recurring_consent: bool = False
    plan_id: str = Field(pattern=r"^(standard|premium)$")
    currency: str = Field(pattern=r"^(NGN|USD)$")
    billing_interval: str = Field(pattern=r"^(monthly|annual)$")
    provider: str = Field(default="paystack", pattern=r"^paystack$")


@router.post("/organizations/{organization_id}/checkout")
async def initialize_customer_checkout(
    organization_id: UUID,
    payload: CheckoutRequestBody,
    membership=Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Create a pending payment using a trusted, enabled price from the server catalog."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    settings = get_settings()
    if not settings.paystack_public_key or not settings.paystack_secret_key:
        raise HTTPException(status_code=503, detail="Online payments are not configured yet")
    if not _is_platform_admin(current_user):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can manage billing prices")
    price = db.scalar(select(BillingPrice).where(
        BillingPrice.plan_id == payload.plan_id,
        BillingPrice.currency == payload.currency,
        BillingPrice.billing_interval == payload.billing_interval,
        BillingPrice.enabled.is_(True),
    ))
    if price is None:
        raise HTTPException(status_code=400, detail="This plan, currency and billing interval are not currently available")
    if not membership.user.email:
        raise HTTPException(status_code=400, detail="Add an email address to your account before subscribing")

    reference = "bp_" + secrets.token_urlsafe(24).replace("-", "").replace("_", "")
    payment = PaymentTransaction(
        organization_id=organization_id,
        initiated_by_user_id=membership.user_id,
        provider=payload.provider,
        reference=reference,
        plan_id=price.plan_id,
        billing_interval=price.billing_interval,
        amount_minor=price.amount_minor,
        currency=price.currency,
        customer_email=membership.user.email,
        status="pending",
        recurring_consent_at=datetime.now(timezone.utc) if payload.recurring_consent else None,
        recurring_consent_version="paystack-recurring-v1" if payload.recurring_consent else None,
        recurring_consent_text=(
            "I consent to BizPilotPro securely retaining a reusable payment authorization for future renewals. "
            "Automatic renewal is not active yet; no future automatic charge will be made until the feature is activated "
            "and I am notified. If activated, the selected plan price will be charged monthly or annually as selected, "
            "until I cancel before a renewal. The first payment is charged now."
            if payload.recurring_consent else None
        ),
    )
    db.add(payment)
    db.flush()
    from app.modules.audit.activity import record_activity
    record_activity(db, membership, "billing.checkout_started", "payment_transaction", payment.id,
                    f"Started {price.plan_id.title()} {price.billing_interval} checkout in {price.currency}")
    db.commit()

    try:
        provider = get_payment_provider(payload.provider, settings)
        session = await provider.initialize_checkout(CheckoutRequest(
            reference=reference,
            email=membership.user.email,
            amount_minor=price.amount_minor,
            currency=price.currency,
            callback_url=f"{settings.frontend_base_url.rstrip('/')}/billing/return",
            metadata={"organization_id": str(organization_id), "plan_id": price.plan_id,
                      "billing_interval": price.billing_interval, "payment_transaction_id": str(payment.id),
                      "recurring_consent": payload.recurring_consent},
        ))
    except (PaymentProviderUnavailable, ValueError) as exc:
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=502, detail="Checkout could not be initialized. Please try again.") from exc
    return {"provider": payload.provider, "reference": reference,
            "authorization_url": session.authorization_url, "access_code": session.access_code,
            "amount_minor": payment.amount_minor, "currency": payment.currency,
            "plan_id": payment.plan_id, "billing_interval": payment.billing_interval}


@router.post("/organizations/{organization_id}/transactions/{reference}/verify")
def verify_customer_payment(
    organization_id: UUID,
    reference: str,
    membership=Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Verify the browser-returned reference with Paystack before showing an active plan."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        provider = get_payment_provider("paystack")
        payment = verify_and_activate(db, reference=reference, provider=provider,
                                      expected_organization_id=organization_id)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Paystack verification is not configured") from exc
    except PaymentVerificationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PaymentVerificationMismatch as exc:
        raise HTTPException(status_code=400, detail="The payment could not be verified against the expected amount.") from exc
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    return {"reference": payment.reference, "payment_status": payment.status,
            "subscription": _subscription_dict(subscription),
            "message": "Payment verified and subscription activated." if payment.status == "paid" else "Payment is not yet confirmed."}


@router.post("/organizations/{organization_id}/subscription/cancel")
def cancel_customer_subscription(
    organization_id: UUID,
    membership=Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> dict:
    """Schedule cancellation at the end of the already-paid period; do not revoke access immediately."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = db.scalar(select(Subscription).where(
        Subscription.organization_id == organization_id
    ).with_for_update())
    if subscription is None or subscription.status not in {"active", "past_due"} or subscription.current_period_end is None:
        raise HTTPException(status_code=409, detail="There is no paid subscription available to cancel")
    if subscription.cancel_at_period_end:
        return {"subscription": _subscription_dict(subscription), "message": "Cancellation is already scheduled."}
    now = datetime.now(timezone.utc)
    if _utc(subscription.current_period_end) <= now:
        raise HTTPException(status_code=409, detail="The paid subscription period has already ended")
    subscription.cancel_at_period_end = True
    subscription.cancellation_requested_at = now
    from app.modules.audit.activity import record_activity
    record_activity(db, membership, "billing.subscription_cancellation_scheduled", "subscription", subscription.id,
                    "Scheduled subscription cancellation at the end of the paid period")
    db.commit()
    db.refresh(subscription)
    return {"subscription": _subscription_dict(subscription), "message": "Cancellation scheduled. Your paid access remains available until the current period ends."}


@router.post("/organizations/{organization_id}/subscription/resume")
def resume_customer_subscription(
    organization_id: UUID,
    membership=Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> dict:
    """Undo a scheduled cancellation while the paid period is still active."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = db.scalar(select(Subscription).where(
        Subscription.organization_id == organization_id
    ).with_for_update())
    now = datetime.now(timezone.utc)
    if (subscription is None or not subscription.cancel_at_period_end
            or subscription.current_period_end is None or _utc(subscription.current_period_end) <= now):
        raise HTTPException(status_code=409, detail="There is no upcoming cancellation that can be reversed")
    subscription.cancel_at_period_end = False
    subscription.cancellation_requested_at = None
    from app.modules.audit.activity import record_activity
    record_activity(db, membership, "billing.subscription_cancellation_reversed", "subscription", subscription.id,
                    "Reversed scheduled subscription cancellation")
    db.commit()
    db.refresh(subscription)
    return {"subscription": _subscription_dict(subscription), "message": "Your subscription will continue through its normal renewal date."}


@router.post("/organizations/{organization_id}/subscription/authorization/revoke")
async def revoke_customer_recurring_authorization(
    organization_id: UUID,
    membership=Depends(require_roles("owner")),
    db: Session = Depends(get_db),
) -> dict:
    """Withdraw recurring-payment consent and deactivate the saved Paystack authorization."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = db.scalar(select(Subscription).where(
        Subscription.organization_id == organization_id
    ).with_for_update())
    if subscription is None or not subscription.provider_authorization_code_encrypted:
        raise HTTPException(status_code=409, detail="There is no saved reusable payment authorization to deactivate")
    from app.integrations.billing_crypto import decrypt_authorization_code
    try:
        authorization_code = decrypt_authorization_code(subscription.provider_authorization_code_encrypted)
        provider = get_payment_provider(subscription.provider)
        deactivate = getattr(provider, "deactivate_authorization", None)
        if deactivate is None:
            raise PaymentProviderUnavailable("The configured payment provider cannot deactivate authorizations")
        await deactivate(authorization_code=authorization_code)
    except PaymentProviderUnavailable as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Payment authorization management is not available") from exc
    except Exception as exc:
        db.rollback()
        # Keep the encrypted authorization until Paystack confirms deactivation. This avoids
        # claiming revocation when the provider call failed or its outcome is ambiguous.
        raise HTTPException(status_code=502, detail="Paystack could not confirm deactivation. Please retry or contact support.") from exc

    subscription.provider_authorization_code_encrypted = None
    subscription.provider_authorization_reusable = False
    subscription.provider_authorization_email = None
    subscription.authorization_card_last4 = None
    subscription.authorization_card_type = None
    subscription.authorization_card_exp_month = None
    subscription.authorization_card_exp_year = None
    subscription.recurring_billing_notice_sent_at = None
    from app.modules.audit.activity import record_activity
    record_activity(db, membership, "billing.recurring_authorization_revoked", "subscription", subscription.id,
                    "Customer withdrew recurring-payment consent and deactivated the saved Paystack authorization")
    db.commit()
    db.refresh(subscription)
    return {"subscription": _subscription_dict(subscription),
            "message": "The saved payment authorization has been deactivated. No future automatic renewal can use it."}


@router.get("/organizations/{organization_id}/renewal-actions")
def list_customer_renewal_actions(
    organization_id: UUID,
    membership=Depends(require_roles("owner", "admin", "member")),
    db: Session = Depends(get_db),
) -> dict:
    """Return tenant-scoped Paystack renewal attempts that need customer authentication."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    rows = db.execute(
        select(SubscriptionRenewalAttempt, PaymentTransaction)
        .join(PaymentTransaction, PaymentTransaction.id == SubscriptionRenewalAttempt.payment_transaction_id)
        .where(PaymentTransaction.organization_id == organization_id, SubscriptionRenewalAttempt.status == "needs_action")
        .order_by(SubscriptionRenewalAttempt.created_at.desc()).limit(10)
    ).all()
    return {"actions": [{
        "reference": payment.reference, "status": attempt.status,
        "authorization_url": attempt.authorization_url if membership.role in {"owner", "admin"} else None,
        "amount_minor": payment.amount_minor, "currency": payment.currency,
        "plan_id": payment.plan_id, "billing_interval": payment.billing_interval,
        "created_at": attempt.created_at,
    } for attempt, payment in rows]}


@router.post("/organizations/{organization_id}/renewal-actions/{reference}/verify")
def verify_customer_renewal_action(
    organization_id: UUID, reference: str,
    membership=Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict:
    """Verify an authenticated renewal server-to-server before fulfilling the billing period."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    payment = db.scalar(select(PaymentTransaction).where(
        PaymentTransaction.reference == reference, PaymentTransaction.organization_id == organization_id,
    ))
    if payment is None:
        raise HTTPException(status_code=404, detail="Renewal payment not found")
    attempt = db.scalar(select(SubscriptionRenewalAttempt).where(
        SubscriptionRenewalAttempt.payment_transaction_id == payment.id,
    ).with_for_update())
    if attempt is None or attempt.status != "needs_action":
        raise HTTPException(status_code=409, detail="This renewal is not waiting for customer authentication")
    try:
        provider = get_payment_provider("paystack")
        verified_payment = verify_and_activate(db, reference=reference, provider=provider,
                                               expected_organization_id=organization_id)
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Paystack verification is not configured") from exc
    except PaymentVerificationMismatch:
        return {"payment_status": payment.status, "message": "Paystack has not confirmed the authenticated renewal yet. Please wait and verify again."}
    except HTTPException as exc:
        if exc.status_code == 409:
            attempt.status = "failed"
            attempt.failure_code = "provider_declined_after_customer_action"
            attempt.authorization_url = None
            subscription = db.scalar(select(Subscription).where(Subscription.id == attempt.subscription_id))
            if subscription is not None:
                enqueue_renewal_status_notice(db, subscription, attempt, payment.amount_minor, payment.currency, payment.reference, "failed")
            db.commit()
            return {"payment_status": "failed", "message": "The bank did not approve this renewal. Please choose a new payment method or contact your workspace owner."}
        raise
    except PaymentVerificationUnavailable as exc:
        raise HTTPException(status_code=503, detail="Paystack could not verify the renewal yet. Please try again shortly.") from exc
    attempt = db.scalar(select(SubscriptionRenewalAttempt).where(
        SubscriptionRenewalAttempt.payment_transaction_id == verified_payment.id,
    ))
    if attempt is not None:
        attempt.status = "paid"
        attempt.completed_at = datetime.now(timezone.utc)
        attempt.authorization_url = None
        db.commit()
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    return {"payment_status": verified_payment.status, "subscription": _subscription_dict(subscription),
            "message": "Renewal payment verified and subscription access extended."}


@router.get("/organizations/{organization_id}/transactions")
def list_customer_transactions(
    organization_id: UUID,
    membership=Depends(require_roles("owner", "admin", "member")),
    db: Session = Depends(get_db),
) -> dict:
    """Return a bounded, tenant-scoped payment history without provider secrets or raw payloads."""
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    rows = db.scalars(select(PaymentTransaction).where(
        PaymentTransaction.organization_id == organization_id
    ).order_by(PaymentTransaction.created_at.desc()).limit(50)).all()
    return {"transactions": [{
        "reference": row.reference, "provider": row.provider, "plan_id": row.plan_id,
        "billing_interval": row.billing_interval, "amount_minor": row.amount_minor,
        "currency": row.currency, "status": row.status, "paid_at": row.paid_at,
        "created_at": row.created_at,
    } for row in rows]}


@router.get("/organizations/{organization_id}/subscription")
def get_customer_subscription(
    organization_id: UUID,
    membership=Depends(require_roles("owner", "admin", "member")),
    db: Session = Depends(get_db),
) -> dict:
    if membership.organization_id != organization_id:
        raise HTTPException(status_code=404, detail="Organization not found")
    subscription = db.scalar(select(Subscription).where(Subscription.organization_id == organization_id))
    return {"subscription": _subscription_dict(subscription), "organization_plan": membership.organization.plan}


def _subscription_dict(subscription: Subscription | None) -> dict | None:
    if subscription is None:
        return None
    return {"plan_id": subscription.plan_id, "status": subscription.status,
            "amount_minor": subscription.amount_minor, "currency": subscription.currency,
            "billing_interval": subscription.billing_interval,
            "current_period_start": subscription.current_period_start,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "grace_period_ends_at": subscription.grace_period_ends_at,
            "cancellation_requested_at": subscription.cancellation_requested_at, "provider": subscription.provider,
            "authorization_saved": bool(subscription.provider_authorization_reusable and subscription.provider_authorization_code_encrypted),
            "authorization_card_last4": subscription.authorization_card_last4,
            "authorization_card_type": subscription.authorization_card_type,
            "recurring_consent_recorded": subscription.recurring_consent_at is not None}


@router.post("/webhooks/paystack")
async def receive_paystack_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Accept signed Paystack events, deduplicate them and verify successful charges server-to-server."""
    raw_body = await request.body()
    try:
        provider = get_payment_provider("paystack")
    except PaymentProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail="Paystack is not configured") from exc
    if not provider.verify_webhook(raw_body, dict(request.headers)):
        raise HTTPException(status_code=401, detail="Invalid payment webhook signature")
    try:
        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid webhook payload") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("event"), str):
        raise HTTPException(status_code=400, detail="Invalid webhook event")
    event_type = payload["event"][:80]
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    reference_value = data.get("reference")
    reference = reference_value if isinstance(reference_value, str) and len(reference_value) <= 120 else None
    digest = hashlib.sha256(raw_body).hexdigest()
    stable_id = str(data.get("id") or reference or digest)[:100]
    event_key = f"paystack:{event_type}:{stable_id}"[:128]
    event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_key == event_key))
    if event is None:
        event = PaymentWebhookEvent(provider="paystack", event_key=event_key, event_type=event_type,
                                    transaction_reference=reference, payload_sha256=digest, status="received")
        db.add(event)
        try:
            db.commit()
            db.refresh(event)
        except IntegrityError:
            db.rollback()
            event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_key == event_key))
    if event and event.status == "processed":
        return {"received": True, "duplicate": True, "status": "processed"}
    if event and event.status == "processing":
        return {"received": True, "duplicate": True, "status": "processing"}
    if event is None:
        raise HTTPException(status_code=503, detail="Could not record webhook receipt")
    event.status = "processing"
    event.failure_message = None
    db.commit()

    # Refund and dispute events are accepted only after the provider signature check above.
    # Keep a minimal adjustment ledger; never persist the raw provider payload.
    if event_type in {"charge.refund", "dispute.create", "dispute.resolve"}:
        nested_transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
        ref = reference or nested_transaction.get("reference") or data.get("transaction_reference")
        payment = db.scalar(select(PaymentTransaction).where(
            PaymentTransaction.reference == ref, PaymentTransaction.provider == "paystack"
        )) if isinstance(ref, str) else None
        if payment is None:
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            db.commit()
            return {"received": True, "status": "unmatched"}
        adjustment_id = str(data.get("id") or data.get("dispute_id") or "")[:100] or None
        currency = str(data.get("currency") or payment.currency).upper()
        amount_value = data.get("amount")
        if currency != payment.currency or (amount_value is not None and (not isinstance(amount_value, int) or amount_value <= 0)):
            event.status = "failed"
            event.failure_message = "Adjustment amount or currency did not match the payment format"
            db.commit()
            return {"received": True, "status": "rejected"}
        if event_type == "dispute.resolve":
            resolution = str(data.get("resolution") or data.get("status") or "").casefold()
            outcome = "won" if any(term in resolution for term in ("won", "merchant_won", "merchant-won")) else "lost" if any(term in resolution for term in ("lost", "merchant_lost", "merchant-lost")) else "pending"
            adjustment = db.scalar(select(PaymentAdjustment).where(
                PaymentAdjustment.payment_transaction_id == payment.id,
                PaymentAdjustment.adjustment_type == "chargeback",
                PaymentAdjustment.provider_adjustment_id == adjustment_id
            )) if adjustment_id else None
            if adjustment:
                adjustment.status = outcome
                adjustment.resolved_at = datetime.now(timezone.utc) if outcome in {"won", "lost"} else None
                adjustment.reason = str(data.get("reason") or adjustment.reason or "")[:240] or None
        else:
            if amount_value is None:
                amount_value = payment.amount_minor if event_type == "dispute.create" else None
            if amount_value is None:
                event.status = "failed"
                event.failure_message = "Provider refund event did not include an amount"
                db.commit()
                return {"received": True, "status": "rejected"}
            kind = "refund" if event_type == "charge.refund" else "chargeback"
            status = "processed" if kind == "refund" else "pending"
            existing = db.scalar(select(PaymentAdjustment).where(PaymentAdjustment.provider_event_key == event_key))
            if existing is None:
                db.add(PaymentAdjustment(
                    payment_transaction_id=payment.id, provider="paystack", provider_event_key=event_key,
                    provider_adjustment_id=adjustment_id, adjustment_type=kind, status=status,
                    amount_minor=amount_value, currency=currency,
                    reason=str(data.get("reason") or data.get("message") or "")[:240] or None,
                ))
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return {"received": True, "status": "processed"}

    if event_type != "charge.success" or not reference:
        event.status = "processed"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return {"received": True, "status": "ignored"}
    try:
        payment = verify_and_activate(db, reference=reference, provider=provider)
        event.status = "processed" if payment.status == "paid" else "ignored"
        event.processed_at = datetime.now(timezone.utc)
        db.commit()
        return {"received": True, "status": event.status}
    except PaymentVerificationUnavailable as exc:
        event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_key == event_key))
        if event:
            event.status = "failed"
            event.failure_message = str(exc)[:400]
            db.commit()
        raise HTTPException(status_code=503, detail="Payment verification is temporarily unavailable") from exc
    except (PaymentVerificationMismatch, HTTPException) as exc:
        event = db.scalar(select(PaymentWebhookEvent).where(PaymentWebhookEvent.event_key == event_key))
        if event:
            event.status = "failed"
            event.failure_message = (str(exc.detail) if isinstance(exc, HTTPException) else str(exc))[:400]
            db.commit()
        if isinstance(exc, HTTPException) and exc.status_code == 404:
            return {"received": True, "status": "unmatched"}
        return {"received": True, "status": "rejected"}


@router.get("/admin/prices")
def list_admin_prices(
    actor: User = Depends(require_platform_admin), db: Session = Depends(get_db)
) -> dict:
    if not _is_platform_admin(actor):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can manage billing prices")
    prices = db.scalars(select(BillingPrice).order_by(BillingPrice.plan_id, BillingPrice.currency, BillingPrice.billing_interval)).all()
    changes = db.scalars(select(BillingPriceChange).order_by(BillingPriceChange.created_at.desc()).limit(100)).all()
    return {
        "prices": [_price_dict(p) for p in prices],
        "history": [{"id": str(c.id), "plan_id": c.plan_id, "currency": c.currency,
                     "billing_interval": c.billing_interval, "previous_amount_minor": c.previous_amount_minor,
                     "new_amount_minor": c.new_amount_minor, "previous_enabled": c.previous_enabled,
                     "new_enabled": c.new_enabled, "actor_user_id": str(c.actor_user_id) if c.actor_user_id else None,
                     "created_at": c.created_at} for c in changes],
    }


@router.put("/admin/prices", status_code=200)
def update_admin_price(
    payload: PriceUpdateRequest,
    current_user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not _is_platform_admin(current_user):
        raise HTTPException(status_code=403, detail="Only the configured platform owner can manage billing prices")
    price = db.scalar(select(BillingPrice).where(
        BillingPrice.plan_id == payload.plan_id,
        BillingPrice.currency == payload.currency,
        BillingPrice.billing_interval == payload.billing_interval,
    ))
    if price is None:
        raise HTTPException(status_code=404, detail="The requested plan price does not exist in the configured catalog")
    previous_amount = price.amount_minor
    previous_enabled = price.enabled
    if previous_amount == payload.amount_minor and previous_enabled == payload.enabled:
        return _price_dict(price)
    price.amount_minor = payload.amount_minor
    price.enabled = payload.enabled
    price.updated_by_user_id = current_user.id
    db.add(BillingPriceChange(
        price_id=price.id, actor_user_id=current_user.id, plan_id=price.plan_id,
        currency=price.currency, billing_interval=price.billing_interval,
        previous_amount_minor=previous_amount, new_amount_minor=price.amount_minor,
        previous_enabled=previous_enabled, new_enabled=price.enabled,
    ))
    try:
        db.commit()
        db.refresh(price)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The price update could not be saved") from None
    return _price_dict(price)
