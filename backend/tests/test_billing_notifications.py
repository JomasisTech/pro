from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

from cryptography.fernet import Fernet

from app.models import BillingNotification, Subscription
from app.modules.billing import notifications


def _settings(*, enabled=True, renewals=False, reminder_days=3):
    return SimpleNamespace(
        billing_renewal_notifications_enabled=enabled,
        billing_renewals_enabled=renewals,
        billing_renewal_reminder_days=reminder_days,
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="mailer",
        smtp_password="not-a-real-secret",
        smtp_use_starttls=True,
        email_from="BizPilot Pro <billing@example.com>",
        app_env="test",
    )


def _due_subscription(client, session_factory, monkeypatch, *, period_end=None, consent=True, notice_sent=True):
    response = client.post("/api/v1/auth/register", json={
        "email": "billing-notice@example.com", "password": "StrongPass123!",
        "full_name": "Billing Notice Owner", "organization_name": "Billing Notice Workspace",
    })
    assert response.status_code == 201, response.text
    organization_id = UUID(response.json()["organization"]["id"])
    monkeypatch.setattr(notifications, "get_settings", lambda: _settings())
    with session_factory() as db:
        subscription = Subscription(
            organization_id=organization_id, provider="paystack", plan_id="standard", status="active",
            amount_minor=750000, currency="NGN", billing_interval="monthly",
            provider_authorization_code_encrypted=b"encrypted-placeholder",
            provider_authorization_email="billing-notice@example.com", provider_authorization_reusable=True,
            recurring_consent_at=datetime.now(timezone.utc) if consent else None,
            recurring_consent_version="paystack-recurring-v1" if consent else None,
            recurring_billing_notice_sent_at=(datetime.now(timezone.utc) - timedelta(days=5)) if notice_sent else None,
            current_period_start=datetime.now(timezone.utc) - timedelta(days=28),
            current_period_end=period_end or datetime.now(timezone.utc) + timedelta(days=2),
            cancel_at_period_end=False,
        )
        db.add(subscription)
        db.commit()
        subscription_id = subscription.id
    return organization_id, subscription_id


def test_due_reminder_is_queued_once_for_recurring_subscription(client, session_factory, monkeypatch):
    _, subscription_id = _due_subscription(client, session_factory, monkeypatch)
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        first = notifications.enqueue_due_renewal_reminders(db, now=now)
        second = notifications.enqueue_due_renewal_reminders(db, now=now)
        assert first["queued"] == 1
        assert second["queued"] == 0
        row = db.query(BillingNotification).one()
        assert row.notification_type == "renewal_reminder"
        assert row.status == "pending"
        assert row.recipient_email == "billing-notice@example.com"
        assert "Automatic renewal is currently disabled" in row.body
        assert str(subscription_id) in row.event_key


def test_reminder_not_queued_without_recurring_consent(client, session_factory, monkeypatch):
    _due_subscription(client, session_factory, monkeypatch, consent=False)
    with session_factory() as db:
        result = notifications.enqueue_due_renewal_reminders(db)
        assert result["queued"] == 0
        assert db.query(BillingNotification).count() == 0


def test_outbox_marks_successful_email_as_sent(client, session_factory, monkeypatch):
    _, subscription_id = _due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: _settings())
    with session_factory() as db:
        subscription = db.get(Subscription, subscription_id)
        queued = notifications.enqueue_billing_notification(
            db, subscription, notification_type="test", event_key="test-event-1",
            subject="Test billing notice", body="A test message",
        )
        db.commit()
        assert queued is True
    sent = []
    monkeypatch.setattr(notifications, "send_email", lambda *args, **kwargs: sent.append(args[1]) or True)
    with session_factory() as db:
        result = notifications.process_billing_notification_outbox(db)
        assert result["sent"] == 1
        row = db.query(BillingNotification).one()
        assert row.status == "sent"
        assert row.sent_at is not None
        assert row.attempt_count == 1
        assert sent == ["billing-notice@example.com"]
    with session_factory() as db:
        again = notifications.process_billing_notification_outbox(db)
        assert again["sent"] == 0


def test_smtp_failure_is_retried_with_backoff_then_bounded(client, session_factory, monkeypatch):
    _, subscription_id = _due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: _settings())
    with session_factory() as db:
        subscription = db.get(Subscription, subscription_id)
        notifications.enqueue_billing_notification(
            db, subscription, notification_type="test", event_key="test-event-fail",
            subject="Test billing notice", body="A test message",
        )
        db.commit()
    monkeypatch.setattr(notifications, "send_email", lambda *args, **kwargs: False)
    now = datetime.now(timezone.utc)
    for expected_count in range(1, notifications.MAX_DELIVERY_ATTEMPTS + 1):
        with session_factory() as db:
            result = notifications.process_billing_notification_outbox(db, now=now)
            row = db.query(BillingNotification).one()
            assert row.attempt_count == expected_count
            if expected_count < notifications.MAX_DELIVERY_ATTEMPTS:
                assert result["retrying"] == 1
                assert row.status == "pending"
                now = row.next_attempt_at + timedelta(seconds=1)
            else:
                assert result["failed"] == 1
                assert row.status == "failed"
                assert row.last_error_code == "smtp_delivery_failed"


def test_notifications_can_be_disabled_without_touching_outbox(client, session_factory, monkeypatch):
    _, subscription_id = _due_subscription(client, session_factory, monkeypatch)
    monkeypatch.setattr(notifications, "get_settings", lambda: _settings(enabled=False))
    with session_factory() as db:
        result = notifications.enqueue_due_renewal_reminders(db)
        delivery = notifications.process_billing_notification_outbox(db)
        assert result["enabled"] is False
        assert delivery["enabled"] is False
        assert db.query(BillingNotification).count() == 0


def test_activation_notice_must_be_delivered_before_renewal_can_be_charged(client, session_factory, monkeypatch):
    _, subscription_id = _due_subscription(client, session_factory, monkeypatch, notice_sent=False)
    monkeypatch.setattr(notifications, "get_settings", lambda: _settings(renewals=True))
    with session_factory() as db:
        queued = notifications.enqueue_automatic_renewal_activation_notices(db)
        assert queued["queued"] == 1
        row = db.query(BillingNotification).one()
        assert row.notification_type == "automatic_renewal_activation"
        assert "No automatic charge will be made while automatic renewals remain disabled" in row.body
    monkeypatch.setattr(notifications, "send_email", lambda *args, **kwargs: True)
    with session_factory() as db:
        delivered = notifications.process_billing_notification_outbox(db)
        assert delivered["sent"] == 1
        subscription = db.get(Subscription, subscription_id)
        assert subscription.recurring_billing_notice_sent_at is not None
        assert db.query(BillingNotification).one().status == "sent"


def test_smtp_transport_uses_starttls_auth_and_sends_message(monkeypatch):
    from types import SimpleNamespace
    from app.integrations import email as email_module

    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))
        def __enter__(self):
            return self
        def __exit__(self, *args):
            calls.append(("close",))
        def starttls(self, context):
            calls.append(("starttls", context is not None))
        def login(self, username, password):
            calls.append(("login", username, password))
        def send_message(self, message):
            calls.append(("send", message["To"], message["Subject"]))

    monkeypatch.setattr(email_module.smtplib, "SMTP", FakeSMTP)
    settings = SimpleNamespace(
        smtp_host="smtp.example.test", smtp_port=587, smtp_use_starttls=True,
        smtp_username="mailer", smtp_password="test-only", email_from="BizPilotPro <test@example.test>",
        app_env="test",
    )
    assert email_module.send_email(settings, "qa@example.test", "Test subject", "Test body") is True
    assert calls[0] == ("connect", "smtp.example.test", 587, 15)
    assert ("starttls", True) in calls
    assert ("login", "mailer", "test-only") in calls
    assert ("send", "qa@example.test", "Test subject") in calls
