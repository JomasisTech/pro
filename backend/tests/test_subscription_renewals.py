from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

from cryptography.fernet import Fernet

from app.integrations import billing_crypto
from app.integrations.billing_crypto import encrypt_authorization_code
from app.models import Organization, Subscription, SubscriptionRenewalAttempt, PaymentTransaction, BillingNotification
from app.modules.billing import renewals, notifications
from app.modules.billing.renewal_reconciliation import reconcile_renewal_attempts


class RenewalPaystack:
    provider_id = "paystack"

    def __init__(self, status="success", raise_charge=False):
        self.status = status
        self.raise_charge = raise_charge
        self.charge_calls = 0

    async def charge_authorization(self, **kwargs):
        self.charge_calls += 1
        self.charge_payload = kwargs
        if self.raise_charge:
            raise RuntimeError("simulated network timeout")
        return {"status": self.status, "reference": kwargs["reference"]}

    async def verify_transaction(self, reference):
        return {
            "id": 555001, "status": "success", "reference": reference,
            "amount": 750000, "currency": "NGN",
            "customer": {"email": "billing@example.com", "customer_code": "CUS_renew"},
        }


def create_due_subscription(client, session_factory, monkeypatch, *, consent=True):
    auth_response = client.post("/api/v1/auth/register", json={
        "email": "owner-renew@example.com", "password": "StrongPass123!",
        "full_name": "Renewal Owner", "organization_name": "Renewal Workspace",
    })
    assert auth_response.status_code == 201, auth_response.text
    organization_id = UUID(auth_response.json()["organization"]["id"])
    key = Fernet.generate_key().decode("ascii")
    settings = SimpleNamespace(
        billing_renewals_enabled=True, billing_authorization_encryption_key=key,
        billing_grace_period_days=3, frontend_base_url="https://app.example.com",
        paystack_secret_key="sk_test_fake", paystack_public_key="pk_test_fake",
    )
    monkeypatch.setattr(renewals, "get_settings", lambda: settings)
    monkeypatch.setattr(billing_crypto, "get_settings", lambda: settings)
    with session_factory() as db:
        subscription = Subscription(
            organization_id=organization_id, provider="paystack", plan_id="standard", status="active",
            amount_minor=750000, currency="NGN", billing_interval="monthly",
            provider_authorization_code_encrypted=encrypt_authorization_code("AUTH_reusable_renewal"),
            provider_authorization_email="billing@example.com", provider_authorization_reusable=True,
            recurring_consent_at=datetime.now(timezone.utc) if consent else None,
            recurring_consent_version="paystack-recurring-v1" if consent else None,
            recurring_billing_notice_sent_at=datetime.now(timezone.utc),
            current_period_start=datetime.now(timezone.utc) - timedelta(days=31),
            current_period_end=datetime.now(timezone.utc) - timedelta(minutes=5),
            cancel_at_period_end=False,
        )
        db.add(subscription)
        db.commit()
        subscription_id = subscription.id
    return auth_response.json(), organization_id, subscription_id


def test_due_renewal_charges_once_and_fulfills_only_after_verification(client, session_factory, monkeypatch):
    _, organization_id, subscription_id = create_due_subscription(client, session_factory, monkeypatch)
    provider = RenewalPaystack()
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["charged"] == 1
        assert provider.charge_calls == 1
        assert provider.charge_payload["email"] == "billing@example.com"
        assert provider.charge_payload["amount_minor"] == 750000
        assert provider.charge_payload["authorization_code"] == "AUTH_reusable_renewal"
    with session_factory() as db:
        subscription = db.get(Subscription, subscription_id)
        assert subscription.status == "active"
        assert subscription.current_period_end > datetime.now(timezone.utc).replace(tzinfo=None)
        assert db.query(SubscriptionRenewalAttempt).one().status == "paid"
        payment = db.query(PaymentTransaction).one()
        assert payment.status == "paid"
        assert payment.organization_id == organization_id


def test_customer_action_response_is_not_recharged_for_same_period(client, session_factory, monkeypatch):
    _, _, subscription_id = create_due_subscription(client, session_factory, monkeypatch)
    provider = RenewalPaystack(status="pending")
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["needs_action"] == 1
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["skipped"] == 1
        assert provider.charge_calls == 1
        assert db.get(Subscription, subscription_id).status == "past_due"
        assert db.query(SubscriptionRenewalAttempt).one().status == "needs_action"


def test_ambiguous_provider_timeout_is_recorded_and_never_recharged(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    provider = RenewalPaystack(raise_charge=True)
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["verification_pending"] == 1
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        # A later verification-only pass can confirm a charge whose initial response timed out.
        assert result["charged"] == 1
        assert provider.charge_calls == 1
        assert db.query(SubscriptionRenewalAttempt).one().status == "paid"


def test_no_explicit_consent_means_no_renewal_charge(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch, consent=False)
    provider = RenewalPaystack()
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
    assert result["examined"] == 0
    assert provider.charge_calls == 0


def test_renewals_are_disabled_by_default(monkeypatch, session_factory):
    monkeypatch.setattr(renewals, "get_settings", lambda: SimpleNamespace(billing_renewals_enabled=False))
    provider = RenewalPaystack()
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
    assert result["enabled"] is False
    assert provider.charge_calls == 0


def test_paused_renewal_exposes_secure_customer_authentication_and_verifies(client, session_factory, monkeypatch):
    auth, organization_id, _ = create_due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: SimpleNamespace(billing_renewal_notifications_enabled=True))
    provider = RenewalPaystack(status="pending")
    async def challenge_charge(**kwargs):
        provider.charge_calls += 1
        provider.charge_payload = kwargs
        return {"status": "pending", "reference": kwargs["reference"], "paused": True,
                "authorization_url": "https://checkout.paystack.com/resume/test-challenge"}
    provider.charge_authorization = challenge_charge
    monkeypatch.setattr("app.api.v1.billing.get_payment_provider", lambda *args, **kwargs: provider)
    monkeypatch.setattr("app.modules.billing.renewals.get_settings", lambda: SimpleNamespace(
        billing_renewals_enabled=True, billing_authorization_encryption_key=Fernet.generate_key().decode("ascii"),
        billing_grace_period_days=3, frontend_base_url="https://app.example.com",
        paystack_secret_key="sk_test_fake", paystack_public_key="pk_test_fake"))
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["needs_action"] == 1
        attempt = db.query(SubscriptionRenewalAttempt).one()
        reference = db.get(PaymentTransaction, attempt.payment_transaction_id).reference
        assert attempt.authorization_url == "https://checkout.paystack.com/resume/test-challenge"
        notice = db.query(BillingNotification).one()
        assert notice.notification_type == "renewal_action_required"
        assert notice.status == "pending"
        assert provider.charge_payload["callback_url"] == f"https://app.example.com/billing?renewal_reference={reference}"
    token = auth["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    actions = client.get(f"/api/v1/billing/organizations/{organization_id}/renewal-actions", headers=headers)
    assert actions.status_code == 200, actions.text
    assert actions.json()["actions"][0]["authorization_url"] == "https://checkout.paystack.com/resume/test-challenge"
    verified = client.post(f"/api/v1/billing/organizations/{organization_id}/renewal-actions/{reference}/verify", headers=headers)
    assert verified.status_code == 200, verified.text
    assert verified.json()["payment_status"] == "paid"
    with session_factory() as db:
        attempt = db.query(SubscriptionRenewalAttempt).one()
        assert attempt.status == "paid"
        assert attempt.authorization_url is None


def test_renewal_action_url_is_not_saved_for_untrusted_host(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    provider = RenewalPaystack(status="pending")
    async def unsafe_charge(**kwargs):
        return {"status": "pending", "reference": kwargs["reference"], "paused": True,
                "authorization_url": "https://evil.example/phish"}
    provider.charge_authorization = unsafe_charge
    with session_factory() as db:
        renewals.process_due_subscription_renewals(db, provider=provider)
        attempt = db.query(SubscriptionRenewalAttempt).one()
        assert attempt.status == "needs_action"
        assert attempt.authorization_url is None


def test_declined_renewal_queues_one_failure_notice(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: SimpleNamespace(billing_renewal_notifications_enabled=True))
    provider = RenewalPaystack(status="failed")
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["failed"] == 1
        notice = db.query(BillingNotification).one()
        assert notice.notification_type == "renewal_payment_failed"
        assert notice.status == "pending"
        assert "not been renewed" in notice.body


def test_renewal_worker_will_not_charge_before_activation_notice_is_sent(client, session_factory, monkeypatch):
    _, _, subscription_id = create_due_subscription(client, session_factory, monkeypatch)
    with session_factory() as db:
        subscription = db.get(Subscription, subscription_id)
        subscription.recurring_billing_notice_sent_at = None
        db.commit()
    provider = RenewalPaystack()
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["examined"] == 0
        assert provider.charge_calls == 0


class FailedVerificationPaystack(RenewalPaystack):
    async def verify_transaction(self, reference):
        return {
            "id": 555002, "status": "failed", "reference": reference,
            "amount": 750000, "currency": "NGN",
            "customer": {"email": "billing@example.com"},
        }


class UnavailableVerificationPaystack(RenewalPaystack):
    async def verify_transaction(self, reference):
        raise RuntimeError("simulated Paystack verification outage")


def test_renewal_reconciliation_verifies_existing_reference_without_charging_again(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    charge_provider = RenewalPaystack(raise_charge=True)
    with session_factory() as db:
        first = renewals.process_due_subscription_renewals(db, provider=charge_provider)
        assert first["verification_pending"] == 1

    verification_provider = RenewalPaystack()
    with session_factory() as db:
        recovered = reconcile_renewal_attempts(
            db, provider_factory=lambda provider_id: verification_provider,
        )
        assert recovered["activated"] == 1
        assert verification_provider.charge_calls == 0
        assert charge_provider.charge_calls == 1
        assert db.query(SubscriptionRenewalAttempt).one().status == "paid"
        assert db.query(PaymentTransaction).one().status == "paid"


def test_stale_processing_renewal_becomes_verification_only_after_worker_crash(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    charge_provider = RenewalPaystack(raise_charge=True)
    with session_factory() as db:
        renewals.process_due_subscription_renewals(db, provider=charge_provider)
        attempt = db.query(SubscriptionRenewalAttempt).one()
        attempt.status = "processing"
        attempt.attempted_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()

    unavailable = UnavailableVerificationPaystack()
    with session_factory() as db:
        recovered = reconcile_renewal_attempts(
            db, provider_factory=lambda provider_id: unavailable,
        )
        assert recovered["provider_unavailable"] == 1
        assert unavailable.charge_calls == 0
        attempt = db.query(SubscriptionRenewalAttempt).one()
        assert attempt.status == "verification_pending"
        assert attempt.failure_code == "stale_processing_recovery"
        assert charge_provider.charge_calls == 1


def test_reconciliation_records_verified_decline_and_queues_failure_notice(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: SimpleNamespace(billing_renewal_notifications_enabled=True))
    monkeypatch.setattr("app.modules.billing.renewal_reconciliation.get_settings", lambda: SimpleNamespace(billing_grace_period_days=3))
    charge_provider = RenewalPaystack(raise_charge=True)
    with session_factory() as db:
        renewals.process_due_subscription_renewals(db, provider=charge_provider)

    failed_provider = FailedVerificationPaystack()
    with session_factory() as db:
        recovered = reconcile_renewal_attempts(
            db, provider_factory=lambda provider_id: failed_provider,
        )
        assert recovered["failed"] == 1
        assert db.query(SubscriptionRenewalAttempt).one().status == "failed"
        assert db.query(PaymentTransaction).one().status == "failed"
        notice = db.query(BillingNotification).one()
        assert notice.notification_type == "renewal_payment_failed"
        assert notice.status == "pending"


def test_paystack_explicit_retry_window_allows_one_delayed_reentry_with_new_reference(
    client, session_factory, monkeypatch,
):
    from app.integrations.payments.paystack_checkout import PaystackRetryWindowError

    create_due_subscription(client, session_factory, monkeypatch)
    now = datetime.now(timezone.utc)

    class Provider(RenewalPaystack):
        def __init__(self):
            super().__init__()
            self.references = []

        async def charge_authorization(self, **kwargs):
            self.charge_calls += 1
            self.references.append(kwargs["reference"])
            if self.charge_calls == 1:
                raise PaystackRetryWindowError("Paystack regulator wait", now + timedelta(minutes=5))
            return {"status": "success", "reference": kwargs["reference"]}

    provider = Provider()
    with session_factory() as db:
        first = renewals.process_due_subscription_renewals(db, provider=provider, now=now)
        assert first["retry_scheduled"] == 1
        attempt = db.query(SubscriptionRenewalAttempt).one()
        assert attempt.status == "retry_scheduled"
        assert attempt.retry_count == 0
        assert attempt.retry_at is not None
        original_reference = db.query(PaymentTransaction).one().reference

    with session_factory() as db:
        early = renewals.process_provider_directed_renewal_retries(
            db, provider=provider, now=now + timedelta(minutes=4)
        )
        assert early["examined"] == 0
        assert provider.charge_calls == 1

    with session_factory() as db:
        retried = renewals.process_provider_directed_renewal_retries(
            db, provider=provider, now=now + timedelta(minutes=6)
        )
        assert retried["retried"] == 1
        attempt = db.query(SubscriptionRenewalAttempt).one()
        assert attempt.status == "paid"
        assert attempt.retry_count == 1
        retried_reference = db.query(PaymentTransaction).one().reference
        assert retried_reference != original_reference
        assert retried_reference.startswith("bp-renew-retry-")
        assert attempt.previous_reference == original_reference
        assert provider.references == [original_reference, retried_reference]
        assert all("_" not in reference for reference in provider.references)


def test_ambiguous_timeout_is_not_eligible_for_provider_directed_retry(client, session_factory, monkeypatch):
    create_due_subscription(client, session_factory, monkeypatch)
    provider = RenewalPaystack(raise_charge=True)
    with session_factory() as db:
        result = renewals.process_due_subscription_renewals(db, provider=provider)
        assert result["verification_pending"] == 1
        assert result["retry_scheduled"] == 0
    with session_factory() as db:
        result = renewals.process_provider_directed_renewal_retries(
            db, provider=provider, now=datetime.now(timezone.utc) + timedelta(days=1)
        )
        assert result["examined"] == 0
        assert provider.charge_calls == 1
