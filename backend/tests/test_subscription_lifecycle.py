from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select

from app.models import Membership, Organization, PaymentTransaction, Subscription
from app.modules.billing.lifecycle import process_subscription_lifecycle


def register(client, email="lifecycle@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": "Lifecycle Owner",
        "organization_name": "Lifecycle Workspace",
    })
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def test_owner_can_schedule_and_reverse_cancellation(client, session_factory):
    auth, headers = register(client)
    org_id = UUID(auth["organization"]["id"])
    with session_factory() as db:
        db.add(Subscription(
            organization_id=org_id, provider="paystack", plan_id="standard", status="active",
            amount_minor=750000, currency="NGN", billing_interval="monthly",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
        ))
        db.commit()

    cancelled = client.post(f"/api/v1/billing/organizations/{org_id}/subscription/cancel", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["subscription"]["cancel_at_period_end"] is True
    assert "paid access remains" in cancelled.json()["message"]

    resumed = client.post(f"/api/v1/billing/organizations/{org_id}/subscription/resume", headers=headers)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["subscription"]["cancel_at_period_end"] is False


def test_member_cannot_cancel_subscription(client, session_factory):
    auth, _ = register(client)
    org_id = UUID(auth["organization"]["id"])
    member_auth, _ = register(client, "member-lifecycle@example.com")
    member_id = UUID(member_auth["user"]["id"])
    with session_factory() as db:
        # Attach the second registered user to the first workspace as a normal member.
        own_membership = db.scalar(select(Membership).where(Membership.user_id == member_id))
        own_org = db.get(Organization, own_membership.organization_id)
        db.delete(own_membership); db.delete(own_org)
        db.add(Membership(user_id=member_id, organization_id=org_id, role="member"))
        db.add(Subscription(
            organization_id=org_id, provider="paystack", plan_id="standard", status="active",
            amount_minor=750000, currency="NGN", billing_interval="monthly",
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
        ))
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "member-lifecycle@example.com", "password": "StrongPass123!"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(f"/api/v1/billing/organizations/{org_id}/subscription/cancel", headers=headers)
    assert response.status_code == 403


def test_lifecycle_enters_grace_then_expires_and_downgrades(client, session_factory):
    auth, _ = register(client, "grace@example.com")
    org_id = UUID(auth["organization"]["id"])
    with session_factory() as db:
        db.add(Subscription(
            organization_id=org_id, provider="paystack", plan_id="premium", status="active",
            amount_minor=199900, currency="USD", billing_interval="monthly",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=35),
            current_period_end=datetime.now(timezone.utc) - timedelta(days=2),
        ))
        org = db.get(Organization, org_id); org.plan = "premium"; db.commit()

    with session_factory() as db:
        result = process_subscription_lifecycle(db, grace_period_days=3)
        assert result["entered_grace"] == 1
        sub = db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
        assert sub.status == "past_due"
        assert sub.grace_period_ends_at is not None
        assert db.get(Organization, org_id).plan == "premium"
        sub.grace_period_ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    with session_factory() as db:
        result = process_subscription_lifecycle(db, grace_period_days=3)
        assert result["expired"] == 1
        sub = db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
        assert sub.status == "expired"
        assert db.get(Organization, org_id).plan == "free"


def test_cancelled_subscription_ends_at_period_boundary(client, session_factory):
    auth, _ = register(client, "cancel-boundary@example.com")
    org_id = UUID(auth["organization"]["id"])
    with session_factory() as db:
        db.add(Subscription(
            organization_id=org_id, provider="paystack", plan_id="standard", status="active",
            amount_minor=750000, currency="NGN", billing_interval="monthly",
            current_period_start=datetime.now(timezone.utc) - timedelta(days=31),
            current_period_end=datetime.now(timezone.utc) - timedelta(seconds=1), cancel_at_period_end=True,
        ))
        org = db.get(Organization, org_id); org.plan = "standard"; db.commit()
    with session_factory() as db:
        result = process_subscription_lifecycle(db)
        assert result["cancelled"] == 1
        sub = db.scalar(select(Subscription).where(Subscription.organization_id == org_id))
        assert sub.status == "cancelled"
        assert db.get(Organization, org_id).plan == "free"


def test_customer_payment_history_is_organization_scoped(client, session_factory):
    auth, headers = register(client, "history@example.com")
    org_id = UUID(auth["organization"]["id"])
    with session_factory() as db:
        db.add(PaymentTransaction(
            organization_id=org_id, provider="paystack", reference="history_ref_1", plan_id="standard",
            billing_interval="monthly", amount_minor=750000, currency="NGN",
            customer_email="history@example.com", status="failed",
        )); db.commit()
    response = client.get(f"/api/v1/billing/organizations/{org_id}/transactions", headers=headers)
    assert response.status_code == 200, response.text
    assert len(response.json()["transactions"]) == 1
    assert response.json()["transactions"][0]["status"] == "failed"
