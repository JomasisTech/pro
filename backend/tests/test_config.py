import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_the_default_development_secret(monkeypatch) -> None:
    monkeypatch.delenv("SECRET_KEY", raising=False)  # CI sets a real one; this test needs the default
    with pytest.raises(ValidationError):
        Settings(app_env="production", _env_file=None)


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="production", secret_key="too-short", _env_file=None)


def test_production_accepts_a_long_unique_secret() -> None:
    settings = Settings(app_env="production", secret_key="x" * 40, cors_origins="https://app.example.com", media_public_base_url="https://api.example.com", frontend_base_url="https://app.example.com", smtp_host="smtp.example.net", email_from="AutoBizPro <no-reply@autobizpro.example>", redis_url="rediss://redis.example.com:6379/0", _env_file=None)
    assert settings.app_env == "production"


def test_development_allows_the_default_secret() -> None:
    assert Settings(app_env="development", _env_file=None).secret_key


def test_automatic_renewals_require_notification_delivery_and_smtp():
    with pytest.raises(ValidationError, match="BILLING_RENEWAL_NOTIFICATIONS_ENABLED"):
        Settings(
            billing_renewals_enabled=True,
            paystack_secret_key="sk_test_example",
            billing_authorization_encryption_key="test-fernet-key",
            _env_file=None,
        )


def test_automatic_renewals_require_smtp_even_when_notices_are_enabled():
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        Settings(
            billing_renewals_enabled=True,
            billing_renewal_notifications_enabled=True,
            paystack_secret_key="sk_test_example",
            billing_authorization_encryption_key="test-fernet-key",
            _env_file=None,
        )
