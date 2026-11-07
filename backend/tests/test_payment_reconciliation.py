from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models import Organization, PaymentTransaction, Subscription
from app.modules.billing.reconciliation import reconcile_pending_payments


class SuccessfulProvider:
    provider_id = "paystack"

    async def verify_transaction(self, reference):
        return {
            "id": 77123,
            "status": "success",
            "reference": reference,
            "amount": 750000,
            "currency": "NGN",
            "customer": {"email": "reconcile@example.com", "customer_code": "CUS_reconcile"},
        }


def _create_customer_payment(client, session_factory):
    response = client.post("/api/v1/auth/register", json={
        "email": "reconcile@example.com", "password": "StrongPass123!",
        "full_name": "Reconcile Customer", "organization_name": "Reconcile Workspace",
    })
    assert response.status_code == 201, response.text
    auth = response.json()
    with session_factory() as db:
        payment = PaymentTransaction(
            organization_id=UUID(auth["organization"]["id"]),
            initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_reconcile_success", plan_id="standard",
            billing_interval="monthly", amount_minor=750000, currency="NGN",
            customer_email="reconcile@example.com", status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
        db.add(payment)
        db.commit()
    return auth


def test_reconciliation_activates_verified_old_pending_payment_once(client, session_factory):
    _create_customer_payment(client, session_factory)
    with session_factory() as db:
        result = reconcile_pending_payments(
            db, provider_factory=lambda _provider: SuccessfulProvider()
        )
    assert result["examined"] == 1
    assert result["activated"] == 1
    with session_factory() as db:
        payment = db.query(PaymentTransaction).one()
        assert payment.status == "paid"
        assert db.query(Organization).one().plan == "standard"
        subscription = db.query(Subscription).one()
        first_period_end = subscription.current_period_end
        assert subscription.status == "active"

    # A subsequent run finds no pending row and cannot grant another period.
    with session_factory() as db:
        second = reconcile_pending_payments(
            db, provider_factory=lambda _provider: SuccessfulProvider()
        )
    assert second["examined"] == 0
    with session_factory() as db:
        assert db.query(Subscription).one().current_period_end == first_period_end


def test_reconciliation_does_not_process_recent_or_non_paystack_payments(session_factory):
    from app.models import Organization

    with session_factory() as db:
        organization = Organization(name="Recent Workspace", slug="recent-workspace")
        db.add(organization)
        db.flush()
        db.add_all([
            PaymentTransaction(
                organization_id=organization.id, provider="paystack", reference="recent_pending",
                plan_id="standard", billing_interval="monthly", amount_minor=750000,
                currency="NGN", customer_email="recent@example.com", status="pending",
                created_at=datetime.now(timezone.utc),
            ),
            PaymentTransaction(
                organization_id=organization.id, provider="paypal", reference="future_provider",
                plan_id="standard", billing_interval="monthly", amount_minor=999,
                currency="USD", customer_email="recent@example.com", status="pending",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            ),
        ])
        db.commit()
        result = reconcile_pending_payments(db, provider_factory=lambda _provider: SuccessfulProvider())
    assert result["examined"] == 1
    assert result["activated"] == 0
    assert result["skipped_provider"] == 1
    with session_factory() as db:
        rows = {row.reference: row.status for row in db.query(PaymentTransaction).all()}
    assert rows["recent_pending"] == "pending"
    assert rows["future_provider"] == "pending"
