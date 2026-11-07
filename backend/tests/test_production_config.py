import pytest
from pydantic import ValidationError
from app.config import Settings


def test_production_requires_explicit_non_local_cors_origin_and_media_url():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            app_env="production", secret_key="x" * 40,
            database_url="postgresql+psycopg://app:password@db.example.com:5432/app",
            redis_url="rediss://redis.example.com:6379/0",
            frontend_base_url="https://app.example.com", smtp_host="smtp.example.net",
            email_from="AutoBizPro <no-reply@autobizpro.example>",
        )


def test_production_accepts_explicit_https_origins_and_media_url():
    settings = Settings(
        app_env="production", secret_key="x" * 40,
        cors_origins="https://app.example.com,https://admin.example.com",
        media_public_base_url="https://api.example.com",
        frontend_base_url="https://app.example.com", smtp_host="smtp.example.net",
        email_from="AutoBizPro <no-reply@autobizpro.example>",
        redis_url="rediss://:test-password@redis.example.com:6379/0",
    )
    assert "https://app.example.com" in settings.cors_origins


def test_production_requires_shared_redis_for_rate_limits():
    with pytest.raises(ValidationError, match="REDIS_URL"):
        Settings(
            app_env="production", secret_key="x" * 40,
            cors_origins="https://app.example.com",
            media_public_base_url="https://api.example.com",
            frontend_base_url="https://app.example.com", smtp_host="smtp.example.net",
            email_from="AutoBizPro <no-reply@autobizpro.example>",
            _env_file=None,
        )


def test_production_rejects_invalid_redis_url():
    with pytest.raises(ValidationError, match="valid redis"):
        Settings(
            app_env="production", secret_key="x" * 40,
            cors_origins="https://app.example.com",
            media_public_base_url="https://api.example.com",
            redis_url="https://not-redis.example.com",
            _env_file=None,
        )


def _valid_production_settings(**overrides):
    values = {
        "app_env": "production",
        "secret_key": "x" * 40,
        "database_url": "postgresql+psycopg://app:password@db.example.com:5432/app",
        "redis_url": "rediss://redis.example.com:6379/0",
        "cors_origins": "https://app.example.com",
        "frontend_base_url": "https://app.example.com",
        "media_public_base_url": "https://api.example.com",
        "smtp_host": "smtp.example.com",
        "email_from": "AutoBizPro <no-reply@autobizpro.example>",
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_rejects_sqlite_database():
    with pytest.raises(ValidationError, match="PostgreSQL"):
        _valid_production_settings(database_url="sqlite:///./app.db")


def test_production_requires_https_frontend_url():
    with pytest.raises(ValidationError, match="FRONTEND_BASE_URL"):
        _valid_production_settings(frontend_base_url="http://app.example.com")


def test_production_requires_smtp_for_account_emails():
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        _valid_production_settings(smtp_host="")


def test_production_rejects_non_https_cors_origins():
    with pytest.raises(ValidationError, match="HTTPS frontend"):
        _valid_production_settings(cors_origins="http://app.example.com")


def test_production_rejects_placeholder_sender_address():
    with pytest.raises(ValidationError, match="EMAIL_FROM"):
        _valid_production_settings(email_from="AutoBizPro <no-reply@localhost>")
