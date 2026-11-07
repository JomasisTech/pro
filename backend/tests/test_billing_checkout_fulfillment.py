from datetime import datetime, timezone
from uuid import UUID
from types import SimpleNamespace

from app.api.v1 import billing
from app.integrations.payments.base import CheckoutSession
from app.models import BillingPrice, Organization, PaymentTransaction, PaymentWebhookEvent, Subscription


class FakePaystack:
    provider_id = "paystack"

    async def initialize_checkout(self, request):
        self.checkout_request = request
        return CheckoutSession("https://checkout.paystack.com/test-session", "access-code", request.reference)

    async def verify_transaction(self, reference):
        return {
            "id": 99123,
            "status": "success",
            "reference": reference,
            "amount": 750000,
            "currency": "NGN",
            "customer": {"email": "customer@example.com", "customer_code": "CUS_test"},
        }

    def verify_webhook(self, raw_body, headers):
        return headers.get("x-test-signature") == "valid"

    async def deactivate_authorization(self, *, authorization_code):
        self.deactivated_authorization = authorization_code
        return {"status": True, "message": "Authorization has been deactivated"}


def register(client, email="customer@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": "Customer",
        "organization_name": "Customer Workspace",
    })
    assert response.status_code == 201
    return response.json(), {"Authorization": f"Bearer {response.json()['access_token']}"}


def configured(monkeypatch, fake):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(
        paystack_public_key="pk_test", paystack_secret_key="sk_test",
        paystack_webhook_secret="whsec_test", frontend_base_url="https://app.example.com",
        platform_admin_emails="",
    ))
    monkeypatch.setattr(billing, "get_payment_provider", lambda *_args, **_kwargs: fake)


def test_checkout_uses_database_price_and_records_pending_payment(client, session_factory, monkeypatch):
    auth, headers = register(client)
    fake = FakePaystack()
    configured(monkeypatch, fake)
    with session_factory() as db:
        db.add(BillingPrice(plan_id="standard", currency="NGN", billing_interval="monthly", amount_minor=750000, enabled=True))
        db.commit()

    response = client.post(f"/api/v1/billing/organizations/{auth['organization']['id']}/checkout", headers=headers, json={
        "plan_id": "standard", "currency": "NGN", "billing_interval": "monthly", "provider": "paystack",
    })
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["authorization_url"] == "https://checkout.paystack.com/test-session"
    assert fake.checkout_request.amount_minor == 750000
    with session_factory() as db:
        payment = db.query(PaymentTransaction).one()
        assert payment.status == "pending"
        assert payment.amount_minor == 750000
        assert payment.billing_interval == "monthly"
        assert db.query(Organization).one().plan == "free"


def test_checkout_records_explicit_recurring_consent_and_snapshot(client, session_factory, monkeypatch):
    auth, headers = register(client)
    fake = FakePaystack()
    configured(monkeypatch, fake)
    with session_factory() as db:
        db.add(BillingPrice(plan_id="standard", currency="NGN", billing_interval="monthly", amount_minor=750000, enabled=True))
        db.commit()

    response = client.post(f"/api/v1/billing/organizations/{auth['organization']['id']}/checkout", headers=headers, json={
        "plan_id": "standard", "currency": "NGN", "billing_interval": "monthly", "provider": "paystack",
        "recurring_consent": True,
    })
    assert response.status_code == 200, response.text
    assert fake.checkout_request.metadata["recurring_consent"] is True
    with session_factory() as db:
        payment = db.query(PaymentTransaction).one()
        assert payment.recurring_consent_at is not None
        assert payment.recurring_consent_version == "paystack-recurring-v1"
        assert "cancel" in payment.recurring_consent_text.lower()


def test_checkout_without_consent_is_one_time_only(client, session_factory, monkeypatch):
    auth, headers = register(client)
    configured(monkeypatch, FakePaystack())
    with session_factory() as db:
        db.add(BillingPrice(plan_id="standard", currency="NGN", billing_interval="monthly", amount_minor=750000, enabled=True))
        db.commit()

    response = client.post(f"/api/v1/billing/organizations/{auth['organization']['id']}/checkout", headers=headers, json={
        "plan_id": "standard", "currency": "NGN", "billing_interval": "monthly", "provider": "paystack",
    })
    assert response.status_code == 200, response.text
    with session_factory() as db:
        payment = db.query(PaymentTransaction).one()
        assert payment.recurring_consent_at is None
        assert payment.recurring_consent_version is None
        assert payment.recurring_consent_text is None


def test_customer_verification_activates_subscription_only_after_provider_success(client, session_factory, monkeypatch):
    auth, headers = register(client)
    fake = FakePaystack()
    configured(monkeypatch, fake)
    with session_factory() as db:
        db.add(PaymentTransaction(
            organization_id=UUID(auth["organization"]["id"]), initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_verify_test", plan_id="standard", billing_interval="monthly",
            amount_minor=750000, currency="NGN", customer_email="customer@example.com", status="pending",
        ))
        db.commit()

    response = client.post(
        f"/api/v1/billing/organizations/{auth['organization']['id']}/transactions/bp_verify_test/verify",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["payment_status"] == "paid"
    with session_factory() as db:
        assert db.query(Organization).one().plan == "standard"
        subscription = db.query(Subscription).one()
        assert subscription.status == "active"
        assert subscription.plan_id == "standard"
        assert subscription.current_period_end is not None
        payment = db.query(PaymentTransaction).one()
        assert payment.provider_transaction_id == "99123"


def test_verified_reusable_authorization_is_encrypted_only_with_consent(client, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.modules.billing import service as billing_service
    from app.integrations import billing_crypto
    from app.integrations.billing_crypto import decrypt_authorization_code

    auth, headers = register(client)
    fake = FakePaystack()
    fake.verify_transaction = async_reusable_verification
    configured(monkeypatch, fake)
    key = Fernet.generate_key().decode("ascii")
    encryption_settings = SimpleNamespace(billing_authorization_encryption_key=key)
    monkeypatch.setattr(billing_service, "get_settings", lambda: encryption_settings)
    monkeypatch.setattr(billing_crypto, "get_settings", lambda: encryption_settings)
    with session_factory() as db:
        db.add(PaymentTransaction(
            organization_id=UUID(auth["organization"]["id"]), initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_auth_consent", plan_id="standard", billing_interval="monthly",
            amount_minor=750000, currency="NGN", customer_email="customer@example.com", status="pending",
            recurring_consent_at=datetime.now(timezone.utc), recurring_consent_version="paystack-recurring-v1",
            recurring_consent_text="Explicit recurring billing consent.",
        ))
        db.commit()

    response = client.post(
        f"/api/v1/billing/organizations/{auth['organization']['id']}/transactions/bp_auth_consent/verify",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    with session_factory() as db:
        subscription = db.query(Subscription).one()
        assert subscription.provider_authorization_reusable is True
        assert subscription.provider_authorization_email == "customer@example.com"
        assert subscription.provider_authorization_code_encrypted != b"AUTH_reusable_test"
        assert decrypt_authorization_code(subscription.provider_authorization_code_encrypted) == "AUTH_reusable_test"
        assert subscription.authorization_card_last4 == "4242"
        assert subscription.authorization_card_type == "visa"
        assert subscription.recurring_consent_at is not None


async def async_reusable_verification(reference):
    return {
        "id": 99124, "status": "success", "reference": reference, "amount": 750000, "currency": "NGN",
        "customer": {"email": "customer@example.com", "customer_code": "CUS_test"},
        "authorization": {"authorization_code": "AUTH_reusable_test", "reusable": True,
                         "card": {"last4": "4242", "type": "visa", "exp_month": "12", "exp_year": "2030"}},
    }


def test_paystack_webhook_is_signed_deduplicated_and_activates_once(client, session_factory, monkeypatch):
    auth, headers = register(client)
    fake = FakePaystack()
    configured(monkeypatch, fake)
    with session_factory() as db:
        db.add(PaymentTransaction(
            organization_id=UUID(auth["organization"]["id"]), initiated_by_user_id=UUID(auth["user"]["id"]),
            provider="paystack", reference="bp_webhook_test", plan_id="standard", billing_interval="monthly",
            amount_minor=750000, currency="NGN", customer_email="customer@example.com", status="pending",
        ))
        db.commit()
    body = {"event": "charge.success", "data": {"id": 99123, "reference": "bp_webhook_test"}}
    response = client.post("/api/v1/billing/webhooks/paystack", headers={"x-test-signature": "valid"}, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "processed"
    duplicate = client.post("/api/v1/billing/webhooks/paystack", headers={"x-test-signature": "valid"}, json=body)
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    with session_factory() as db:
        assert db.query(Subscription).count() == 1
        assert db.query(PaymentWebhookEvent).one().status == "processed"
        assert db.query(PaymentTransaction).one().status == "paid"


def test_paystack_webhook_rejects_invalid_signature(client, monkeypatch):
    configured(monkeypatch, FakePaystack())
    response = client.post("/api/v1/billing/webhooks/paystack", headers={"x-test-signature": "wrong"}, json={"event": "charge.success"})
    assert response.status_code == 401


def test_subscription_status_is_tenant_scoped(client):
    auth, headers = register(client)
    response = client.get(f"/api/v1/billing/organizations/{auth['organization']['id']}/subscription", headers=headers)
    assert response.status_code == 200
    assert response.json()["organization_plan"] == "free"
    assert response.json()["subscription"] is None


def test_owner_can_revoke_saved_recurring_authorization(client, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.integrations import billing_crypto
    from app.integrations.billing_crypto import encrypt_authorization_code

    auth, headers = register(client)
    fake = FakePaystack()
    configured(monkeypatch, fake)
    key = Fernet.generate_key().decode("ascii")
    encryption_settings = SimpleNamespace(billing_authorization_encryption_key=key)
    monkeypatch.setattr(billing_crypto, "get_settings", lambda: encryption_settings)
    with session_factory() as db:
        subscription = Subscription(
            organization_id=UUID(auth["organization"]["id"]), provider="paystack", plan_id="standard",
            status="active", amount_minor=750000, currency="NGN", billing_interval="monthly",
            provider_authorization_code_encrypted=encrypt_authorization_code("AUTH_revoke_me"),
            provider_authorization_email="customer@example.com", provider_authorization_reusable=True,
            authorization_card_last4="4242", recurring_consent_at=datetime.now(timezone.utc),
            recurring_consent_version="paystack-recurring-v1",
        )
        db.add(subscription)
        db.commit()

    response = client.post(
        f"/api/v1/billing/organizations/{auth['organization']['id']}/subscription/authorization/revoke",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert fake.deactivated_authorization == "AUTH_revoke_me"
    assert response.json()["subscription"]["authorization_saved"] is False
    with session_factory() as db:
        saved = db.query(Subscription).one()
        assert saved.provider_authorization_code_encrypted is None
        assert saved.provider_authorization_reusable is False
        assert saved.recurring_consent_at is not None  # retain historical consent evidence
        assert saved.authorization_card_last4 is None


def test_failed_provider_revocation_keeps_encrypted_authorization(client, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.integrations import billing_crypto
    from app.integrations.billing_crypto import encrypt_authorization_code

    auth, headers = register(client)
    fake = FakePaystack()
    async def fail_deactivation(*, authorization_code):
        raise RuntimeError("provider unavailable")
    fake.deactivate_authorization = fail_deactivation
    configured(monkeypatch, fake)
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setattr(billing_crypto, "get_settings", lambda: SimpleNamespace(billing_authorization_encryption_key=key))
    with session_factory() as db:
        db.add(Subscription(
            organization_id=UUID(auth["organization"]["id"]), provider="paystack", plan_id="standard",
            status="active", amount_minor=750000, currency="NGN", billing_interval="monthly",
            provider_authorization_code_encrypted=encrypt_authorization_code("AUTH_keep_if_failed"),
            provider_authorization_email="customer@example.com", provider_authorization_reusable=True,
        ))
        db.commit()
    response = client.post(
        f"/api/v1/billing/organizations/{auth['organization']['id']}/subscription/authorization/revoke",
        headers=headers,
    )
    assert response.status_code == 502
    with session_factory() as db:
        saved = db.query(Subscription).one()
        assert saved.provider_authorization_code_encrypted is not None
        assert saved.provider_authorization_reusable is True
