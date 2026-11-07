from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.v1 import billing
from app.models import PlatformAdminAudit, User


def register(client, email, name):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": name,
        "organization_name": f"{name} Workspace",
    })
    assert response.status_code == 201
    return response.json(), {"Authorization": f"Bearer {response.json()['access_token']}"}


def verify(session_factory, email):
    with session_factory() as db:
        user = db.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        db.commit()
        return user.id


def test_platform_admin_can_search_and_suspend_customer(client, session_factory, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    _, customer_headers = register(client, "customer@example.com", "Customer")
    verify(session_factory, "owner@example.com")
    customer_id = verify(session_factory, "customer@example.com")

    listing = client.get("/api/v1/platform-admin/customers?q=customer", headers=admin_headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["email"] == "customer@example.com"

    suspended = client.patch(f"/api/v1/platform-admin/customers/{customer_id}/status", headers=admin_headers,
                             json={"is_active": False})
    assert suspended.status_code == 200
    assert suspended.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=customer_headers).status_code == 401

    with session_factory() as db:
        assert db.query(PlatformAdminAudit).count() == 1
        customer = db.get(User, customer_id)
        assert customer is not None and customer.token_version == 1


def test_non_admin_cannot_access_platform_customer_directory(client, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, headers = register(client, "ordinary@example.com", "Ordinary")
    response = client.get("/api/v1/platform-admin/customers", headers=headers)
    assert response.status_code == 403


def test_platform_admin_cannot_suspend_self(client, session_factory, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    auth, headers = register(client, "owner@example.com", "Owner")
    owner_id = verify(session_factory, "owner@example.com")
    response = client.patch(f"/api/v1/platform-admin/customers/{owner_id}/status", headers=headers,
                            json={"is_active": False})
    assert response.status_code == 400


def test_platform_admin_can_retry_failed_paystack_webhook(client, session_factory, monkeypatch):
    from uuid import UUID
    from app.api.v1 import platform_admin
    from app.models import Organization, PaymentTransaction, PaymentWebhookEvent, Subscription

    class FakeProvider:
        provider_id = "paystack"

        async def verify_transaction(self, reference):
            return {
                "id": "retry-tx-1", "status": "success", "reference": reference,
                "amount": 750000, "currency": "NGN",
                "customer": {"email": "customer@example.com", "customer_code": "CUS_retry"},
            }

    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    auth, _ = register(client, "customer@example.com", "Customer")
    verify(session_factory, "owner@example.com")
    with session_factory() as db:
        org = db.get(Organization, UUID(auth["organization"]["id"]))
        payment = PaymentTransaction(
            organization_id=org.id, initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_retry_test", plan_id="standard", billing_interval="monthly",
            amount_minor=750000, currency="NGN", customer_email="customer@example.com", status="pending",
        )
        db.add(payment)
        event = PaymentWebhookEvent(
            provider="paystack", event_key="paystack:charge.success:retry-1", event_type="charge.success",
            transaction_reference="bp_retry_test", payload_sha256="a" * 64, status="failed",
            failure_message="Temporary provider timeout",
        )
        db.add(event)
        db.commit()
        event_id = event.id

    monkeypatch.setattr(platform_admin, "get_payment_provider", lambda *_args, **_kwargs: FakeProvider())
    response = client.post(f"/api/v1/platform-admin/webhooks/{event_id}/retry", headers=admin_headers)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processed"
    with session_factory() as db:
        assert db.query(Subscription).count() == 1
        assert db.query(PaymentTransaction).one().status == "paid"
        assert db.get(PaymentWebhookEvent, event_id).status == "processed"
        audit = db.query(PlatformAdminAudit).filter_by(action="billing.webhook_retried").one()
        assert "retry-1" in audit.summary


def test_platform_admin_cannot_retry_recent_processing_webhook(client, session_factory, monkeypatch):
    from app.models import PaymentWebhookEvent

    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    verify(session_factory, "owner@example.com")
    with session_factory() as db:
        event = PaymentWebhookEvent(
            provider="paystack", event_key="paystack:charge.success:busy", event_type="charge.success",
            transaction_reference="bp_busy", payload_sha256="b" * 64, status="processing",
        )
        db.add(event)
        db.commit()
        event_id = event.id
    response = client.post(f"/api/v1/platform-admin/webhooks/{event_id}/retry", headers=admin_headers)
    assert response.status_code == 409


def test_platform_admin_can_run_bounded_payment_reconciliation(client, session_factory, monkeypatch):
    from datetime import timedelta
    from uuid import UUID
    from app.api.v1 import platform_admin
    from app.models import Organization, PaymentTransaction

    class FakeProvider:
        provider_id = "paystack"

        async def verify_transaction(self, reference):
            return {
                "id": "scheduled-reconcile-1", "status": "success", "reference": reference,
                "amount": 750000, "currency": "NGN",
                "customer": {"email": "reconcile-admin@example.com", "customer_code": "CUS_admin"},
            }

    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    auth, _ = register(client, "reconcile-admin@example.com", "Customer")
    verify(session_factory, "owner@example.com")
    with session_factory() as db:
        org = db.get(Organization, UUID(auth["organization"]["id"]))
        db.add(PaymentTransaction(
            organization_id=org.id, initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_admin_reconcile", plan_id="standard",
            billing_interval="monthly", amount_minor=750000, currency="NGN",
            customer_email="reconcile-admin@example.com", status="pending",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        ))
        db.commit()

    monkeypatch.setattr(platform_admin, "get_payment_provider", lambda *_args, **_kwargs: FakeProvider())
    response = client.post("/api/v1/platform-admin/billing/reconciliation/run", headers=admin_headers,
                           json={"limit": 25, "older_than_minutes": 10})
    assert response.status_code == 200, response.text
    assert response.json()["activated"] == 1
    with session_factory() as db:
        assert db.query(PlatformAdminAudit).filter_by(action="billing.reconciliation_run").count() == 1


def test_platform_admin_top_customers_rank_paid_spend_in_both_directions_and_separate_currencies(client, session_factory, monkeypatch):
    from uuid import UUID
    from app.models import Organization, PaymentTransaction

    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    verify(session_factory, "owner@example.com")

    customers = []
    for index in range(11):
        email = f"leader{index:02d}@example.com"
        auth, _ = register(client, email, f"Leader {index:02d}")
        customers.append((UUID(auth["user"]["id"]), UUID(auth["organization"]["id"]), email, 10000 + index * 1000))

    with session_factory() as db:
        for user_id, org_id, email, amount in customers:
            db.add(PaymentTransaction(
                organization_id=org_id, initiated_by_user_id=user_id, provider="paystack",
                reference=f"rank_paid_{email.split('@')[0]}", plan_id="standard", billing_interval="monthly",
                amount_minor=amount, currency="NGN", customer_email=email, status="paid",
                paid_at=datetime.now(timezone.utc),
            ))
        # A larger pending payment and a larger USD payment must not affect the NGN ranking.
        first_id, first_org, first_email, _ = customers[0]
        db.add(PaymentTransaction(
            organization_id=first_org, initiated_by_user_id=first_id, provider="paystack",
            reference="rank_pending_excluded", plan_id="premium", billing_interval="monthly",
            amount_minor=90000000, currency="NGN", customer_email=first_email, status="pending",
        ))
        db.add(PaymentTransaction(
            organization_id=first_org, initiated_by_user_id=first_id, provider="paystack",
            reference="rank_usd_excluded", plan_id="premium", billing_interval="monthly",
            amount_minor=90000000, currency="USD", customer_email=first_email, status="paid",
            paid_at=datetime.now(timezone.utc),
        ))
        db.commit()

    descending = client.get("/api/v1/platform-admin/top-customers?currency=NGN&sort=desc", headers=admin_headers)
    assert descending.status_code == 200, descending.text
    data = descending.json()
    assert len(data["items"]) == 10
    assert data["items"][0]["email"] == "leader10@example.com"
    assert data["items"][0]["rank"] == 1
    assert data["items"][0]["total_spend_minor"] == 20000
    assert all(row["currency"] == "NGN" for row in data["items"])
    assert "leader00@example.com" not in [row["email"] for row in data["items"]]

    ascending = client.get("/api/v1/platform-admin/top-customers?currency=NGN&sort=asc", headers=admin_headers)
    assert ascending.status_code == 200, ascending.text
    low = ascending.json()["items"]
    assert low[0]["email"] == "leader00@example.com"
    assert low[0]["rank"] == 1
    assert low[-1]["email"] == "leader09@example.com"

    usd = client.get("/api/v1/platform-admin/top-customers?currency=USD&sort=desc", headers=admin_headers)
    assert usd.status_code == 200, usd.text
    assert len(usd.json()["items"]) == 1
    assert usd.json()["items"][0]["email"] == "leader00@example.com"


def test_non_admin_cannot_access_top_customer_leaderboard(client, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, headers = register(client, "ordinary@example.com", "Ordinary")
    response = client.get("/api/v1/platform-admin/top-customers", headers=headers)
    assert response.status_code == 403


def test_platform_admin_can_initiate_password_recovery_for_verified_customer(client, session_factory, monkeypatch):
    from app.api.v1 import platform_admin
    from app.models import PasswordResetToken

    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    sent = []
    monkeypatch.setattr(platform_admin, "_send_reset_email", lambda email, token: sent.append((email, token)))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    verify(session_factory, "owner@example.com")
    _, customer_headers = register(client, "recover@example.com", "Recover Customer")
    customer_id = verify(session_factory, "recover@example.com")

    response = client.post(
        f"/api/v1/platform-admin/customers/{customer_id}/password-recovery",
        headers=admin_headers, json={"reason": "Customer contacted support after losing access to their password."},
    )
    assert response.status_code == 202, response.text
    assert "verified email" in response.json()["message"]
    assert sent and sent[0][0] == "recover@example.com"
    with session_factory() as db:
        token_row = db.query(PasswordResetToken).one()
        assert token_row.user_id == customer_id
        assert token_row.token_hash != sent[0][1]
        audit = db.query(PlatformAdminAudit).filter_by(action="customer.password_recovery_initiated").one()
        assert audit.target_user_id == customer_id


def test_platform_admin_cannot_initiate_recovery_for_unverified_customer(client, session_factory, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, admin_headers = register(client, "owner@example.com", "Owner")
    verify(session_factory, "owner@example.com")
    auth, _ = register(client, "unverified@example.com", "Unverified Customer")
    response = client.post(
        f"/api/v1/platform-admin/customers/{auth['user']['id']}/password-recovery",
        headers=admin_headers, json={"reason": "Customer contacted support and requested account recovery."},
    )
    assert response.status_code == 409


def test_non_admin_cannot_initiate_customer_password_recovery(client, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    _, headers = register(client, "ordinary@example.com", "Ordinary")
    response = client.post(
        "/api/v1/platform-admin/customers/00000000-0000-0000-0000-000000000001/password-recovery",
        headers=headers, json={"reason": "Customer contacted support and requested account recovery."},
    )
    assert response.status_code == 403
