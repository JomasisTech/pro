from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Organization, PaymentTransaction, PaymentWebhookEvent, Subscription, User


def _identity(session):
    user = User(email=f"owner-{uuid4()}@example.com", password_hash="not-a-real-login-hash", full_name="Test Owner")
    organization = Organization(name="Test workspace", slug=f"workspace-{uuid4().hex}")
    session.add_all([user, organization])
    session.commit()
    return user, organization


def test_payment_records_can_be_persisted_with_safe_pending_defaults(session_factory):
    with session_factory() as session:
        user, organization = _identity(session)
        payment = PaymentTransaction(
            organization_id=organization.id,
            initiated_by_user_id=user.id,
            reference=f"pay-{uuid4().hex}",
            plan_id="standard",
            amount_minor=250000,
            currency="NGN",
            customer_email=user.email,
        )
        subscription = Subscription(organization_id=organization.id)
        event = PaymentWebhookEvent(
            event_key=f"paystack:{uuid4().hex}",
            event_type="charge.success",
            payload_sha256="a" * 64,
        )
        session.add_all([payment, subscription, event])
        session.commit()

        assert payment.status == "pending"
        assert subscription.status == "inactive"
        assert subscription.plan_id == "free"
        assert event.status == "received"
        assert payment.amount_minor == 250000


def test_payment_reference_is_unique(session_factory):
    with session_factory() as session:
        user, organization = _identity(session)
        reference = f"unique-{uuid4().hex}"
        values = dict(
            organization_id=organization.id,
            initiated_by_user_id=user.id,
            reference=reference,
            plan_id="standard",
            amount_minor=250000,
            currency="NGN",
            customer_email=user.email,
        )
        session.add(PaymentTransaction(**values))
        session.commit()
        session.add(PaymentTransaction(**values))
        with pytest.raises(IntegrityError):
            session.commit()


def test_webhook_event_key_is_unique(session_factory):
    with session_factory() as session:
        event_key = f"paystack:{uuid4().hex}"
        session.add_all([
            PaymentWebhookEvent(event_key=event_key, event_type="charge.success", payload_sha256="b" * 64),
        ])
        session.commit()
        session.add(PaymentWebhookEvent(event_key=event_key, event_type="charge.success", payload_sha256="b" * 64))
        with pytest.raises(IntegrityError):
            session.commit()


def test_only_one_subscription_row_per_organization(session_factory):
    with session_factory() as session:
        _, organization = _identity(session)
        session.add(Subscription(organization_id=organization.id))
        session.commit()
        session.add(Subscription(organization_id=organization.id))
        with pytest.raises(IntegrityError):
            session.commit()
