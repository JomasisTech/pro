import secrets
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Keep the local environment file path independent of the directory from which
# Uvicorn or a test command is started. Environment variables still take priority.
BACKEND_DIR = Path(__file__).resolve().parents[1]


_DEFAULT_SECRET_KEY = "development-only-change-this-secret-key-before-deploying"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or backend/.env."""

    app_name: str = "Business Automation Platform API"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    redis_url: str = ""
    database_url: str = (
        "postgresql+psycopg://app_user:change_me@localhost:5432/business_automation"
    )
    secret_key: str = _DEFAULT_SECRET_KEY
    # Demo mode (local only): seeds a ready-made demo account, sample business and categories at startup so you can
    # sign in without registering, verifying email or setting up social login. Refused when APP_ENV=production.
    demo_mode: bool = False
    demo_email: str = "customer-demo@example.com"
    demo_password: str = "pass"
    demo_full_name: str = "Demo Customer"
    demo_organization_name: str = "Demo Business"
    # Separate identity for the isolated platform-owner demo; never reuse the customer demo account.
    demo_admin_email: str = "platform-owner-demo@example.com"
    demo_admin_full_name: str = "Demo Platform Owner"
    access_token_expire_minutes: int = 30
    login_max_failed_attempts: int = 5
    login_lockout_seconds: int = 900
    # Number of reverse proxies in front of the API (0 = none). Needed to see real client addresses.
    trusted_proxy_count: int = 0
    # Failed logins allowed per client address across ALL emails (0 = disabled).
    login_ip_max_failed_attempts: int = 0
    # Workspaces one user may belong to (until plans define this).
    max_workspaces_per_user: int = 10
    # Password reset. Links point at the frontend; the token travels in the URL fragment.
    frontend_base_url: str = "http://localhost:3000"
    password_reset_ttl_minutes: int = 30
    email_verification_ttl_minutes: int = 60
    email_verification_required: bool = False
    email_verification_max_requests: int = 3
    email_verification_window_seconds: int = 3600
    # Reset requests allowed per email and per client address inside one window (always answers 202).
    password_reset_max_requests: int = 3
    password_reset_window_seconds: int = 3600
    # Outgoing email (SMTP). Leave SMTP_HOST empty to disable sending: in development the reset link is
    # written to the server log instead; in production nothing is sent and a warning is logged.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_starttls: bool = True
    email_from: str = "AutoBizPro <no-reply@localhost>"
    # Campaign delivery can use Resend; SMTP remains available for transactional email.
    email_campaign_provider: str = "smtp"
    resend_api_key: str = ""
    resend_webhook_secret: str = ""
    email_provider_timeout_seconds: float = Field(default=15.0, ge=3.0, le=60.0)
    # Paystack credentials are server-side only. Checkout requires the public and secret keys; webhooks should use the signing secret.
    paystack_public_key: str = ""
    paystack_secret_key: str = ""
    paystack_webhook_secret: str = ""
    # Paid workspaces retain access for this many days after a missed renewal; set 0 to disable grace.
    billing_grace_period_days: int = Field(default=3, ge=0, le=14)
    # Dedicated Fernet key for reusable payment authorizations; never reuse OAuth token key.
    billing_authorization_encryption_key: str = ""
    # Automatic renewal processing is opt-in and remains disabled until explicitly enabled.
    billing_renewals_enabled: bool = False
    # Transactional billing notices are separately opt-in; enable only after SMTP delivery is verified.
    billing_renewal_notifications_enabled: bool = False
    billing_renewal_reminder_days: int = Field(default=3, ge=1, le=14)
    # Comma-separated platform-owner email allowlist for global billing price administration.
    platform_admin_emails: str = ""
    # AI content generation. Leave OPENAI_API_KEY empty to disable it (the API then answers 503).
    openai_api_key: str = ""
    # Check the provider's current model list before deploying; the default may be retired.
    openai_model: str = "gpt-4o-mini"
    ai_request_timeout_seconds: float = 30.0
    # USD per 1M tokens for the configured OPENAI_MODEL. Zero disables cost estimation; token counts still record.
    openai_input_usd_per_million_tokens: float = Field(default=0.0, ge=0)
    openai_output_usd_per_million_tokens: float = Field(default=0.0, ge=0)
    # Caption generations allowed per user per hour (cost guard; in-memory like the login limiter).
    ai_generations_per_hour: int = 20
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    # Meta Instagram Login (professional accounts only). Keep credentials server-side.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_redirect_uri: str = "http://localhost:8000/api/v1/social-oauth/meta/instagram/callback"
    meta_frontend_return_url: str = "http://localhost:3000/social-accounts/callback"
    facebook_redirect_uri: str = "http://localhost:8000/api/v1/social-oauth/facebook/callback"
    facebook_frontend_return_url: str = "http://localhost:3000/social-accounts/callback"
    social_token_encryption_key: str = ""
    social_oauth_state_ttl_seconds: int = 600
    # Private media storage. MEDIA_PUBLIC_BASE_URL must be the public HTTPS API origin in production.
    media_storage_dir: str = "./var/media"
    media_public_base_url: str = ""
    media_max_upload_bytes: int = 1073741824
    media_signed_url_ttl_seconds: int = 86400
    # Enable the database-backed dispatcher loop in the API service. Keep one Render instance
    # while using local persistent media storage; move to shared object storage before scaling.
    scheduler_worker_enabled: bool = False
    scheduler_poll_interval_seconds: int = 15
    # TikTok Login Kit / Content Posting API. App credentials remain server-side.
    tiktok_client_key: str = ""
    tiktok_client_secret: str = ""
    tiktok_redirect_uri: str = "http://localhost:8000/api/v1/social-oauth/tiktok/callback"
    tiktok_frontend_return_url: str = "http://localhost:3000/social-accounts/callback"
    # Set true only after TikTok completes the Content Posting API audit for this client.
    tiktok_content_posting_audited: bool = False
    # Google OAuth / YouTube Data API. Use a Web application OAuth client.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_login_client_id: str = ""
    google_login_client_secret: str = ""
    google_login_redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"
    google_login_frontend_return_url: str = "http://localhost:3000/auth/callback"
    # WhatsApp one-time-code sign-in (WhatsApp Business Platform / Cloud API). WhatsApp is not an OAuth identity
    # provider, so the API sends a 6-digit code through an approved AUTHENTICATION message template and the
    # person types it back, which proves they control that WhatsApp number. Leave the token empty to disable.
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_otp_template_name: str = ""
    whatsapp_template_language: str = "en_US"
    # Meta retires old Graph API versions; check the current one before deploying.
    whatsapp_graph_api_version: str = "v23.0"
    whatsapp_login_code_ttl_minutes: int = 10
    whatsapp_login_resend_seconds: int = 60
    # Minimum gap between re-sends of the same workspace invitation.
    invitation_resend_cooldown_seconds: int = 60
    whatsapp_login_max_codes_per_hour: int = 5
    whatsapp_login_max_verify_attempts: int = 5
    youtube_redirect_uri: str = "http://localhost:8000/api/v1/social-oauth/youtube/callback"
    youtube_frontend_return_url: str = "http://localhost:3000/social-accounts/callback"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _reject_default_secret_in_production(self) -> "Settings":
        if self.demo_mode and self.app_env.lower() == "production":
            raise ValueError("DEMO_MODE must never be enabled when APP_ENV=production")
        if self.demo_mode and not urlsplit(self.database_url).scheme.startswith("sqlite"):
            raise ValueError("DEMO_MODE requires an isolated SQLite database; never point a demo deployment at shared customer data")
        if self.demo_mode and self.demo_email.strip().casefold() == self.demo_admin_email.strip().casefold():
            raise ValueError("DEMO_EMAIL and DEMO_ADMIN_EMAIL must be different identities")
        if self.demo_mode and self.secret_key == _DEFAULT_SECRET_KEY:
            # No SECRET_KEY to configure in demo mode: use a random one (sessions simply end on restart).
            self.secret_key = secrets.token_urlsafe(48)
        if self.billing_renewals_enabled and (not self.paystack_secret_key or not self.billing_authorization_encryption_key):
            raise ValueError("BILLING_RENEWALS_ENABLED requires PAYSTACK_SECRET_KEY and BILLING_AUTHORIZATION_ENCRYPTION_KEY")
        if self.billing_renewals_enabled and (not self.billing_renewal_notifications_enabled or not self.smtp_host):
            raise ValueError("BILLING_RENEWALS_ENABLED requires BILLING_RENEWAL_NOTIFICATIONS_ENABLED and SMTP_HOST")
        if self.app_env.lower() == "production" and (
            self.secret_key == _DEFAULT_SECRET_KEY or len(self.secret_key) < 32
        ):
            raise ValueError("SECRET_KEY must be set to a unique value of at least 32 characters in production")
        if self.email_campaign_provider.lower() not in {"smtp", "resend"}:
            raise ValueError("EMAIL_CAMPAIGN_PROVIDER must be smtp or resend")
        if self.email_campaign_provider.lower() == "resend" and not self.resend_api_key:
            raise ValueError("RESEND_API_KEY is required when EMAIL_CAMPAIGN_PROVIDER=resend")
        if self.app_env.lower() == "production" and self.email_campaign_provider.lower() == "resend" and not self.resend_webhook_secret:
            raise ValueError("RESEND_WEBHOOK_SECRET is required in production when EMAIL_CAMPAIGN_PROVIDER=resend")
        if self.app_env.lower() == "production":
            database_parts = urlsplit(self.database_url)
            if database_parts.scheme not in {"postgresql", "postgresql+psycopg"} or not database_parts.hostname:
                raise ValueError("DATABASE_URL must point to a PostgreSQL database in production")
            if not self.redis_url:
                raise ValueError("REDIS_URL must be configured in production; in-memory rate limits are not safe across workers or restarts")
            redis_parts = urlsplit(self.redis_url)
            if redis_parts.scheme not in {"redis", "rediss"} or not redis_parts.hostname:
                raise ValueError("REDIS_URL must be a valid redis:// or rediss:// URL")
            origins = [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]
            if not origins or any(urlsplit(origin).scheme != "https" or not urlsplit(origin).hostname for origin in origins):
                raise ValueError("CORS_ORIGINS must contain explicit HTTPS frontend origin(s) in production")
            frontend_parts = urlsplit(self.frontend_base_url)
            if frontend_parts.scheme != "https" or not frontend_parts.hostname:
                raise ValueError("FRONTEND_BASE_URL must be the public HTTPS frontend origin in production")
            media_parts = urlsplit(self.media_public_base_url)
            if media_parts.scheme != "https" or not media_parts.hostname:
                raise ValueError("MEDIA_PUBLIC_BASE_URL must be configured with the public HTTPS API origin in production")
            if not self.smtp_host:
                raise ValueError("SMTP_HOST must be configured in production for password recovery and account email delivery")
            if "@localhost" in self.email_from.lower() or "@example.com" in self.email_from.lower():
                raise ValueError("EMAIL_FROM must use a verified sender address for the production domain")
        if self.app_env.lower() == "production" and self.google_login_client_id and (
            not self.google_login_client_secret
            or not self.google_login_redirect_uri.startswith("https://")
            or not self.google_login_frontend_return_url.startswith("https://")
        ):
            raise ValueError("Google sign-in requires its client secret and HTTPS redirect URLs in production")
        if self.whatsapp_access_token and (not self.whatsapp_phone_number_id or not self.whatsapp_otp_template_name):
            raise ValueError("WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_OTP_TEMPLATE_NAME are required when WHATSAPP_ACCESS_TOKEN is set")
        if self.app_env.lower() == "production" and self.tiktok_client_key and (
            not self.tiktok_client_secret or not self.social_token_encryption_key
        ):
            raise ValueError("TIKTOK_CLIENT_SECRET and SOCIAL_TOKEN_ENCRYPTION_KEY are required when TikTok OAuth is configured")
        if self.app_env.lower() == "production" and self.google_client_id and (
            not self.google_client_secret or not self.social_token_encryption_key
        ):
            raise ValueError("GOOGLE_CLIENT_SECRET and SOCIAL_TOKEN_ENCRYPTION_KEY are required when YouTube OAuth is configured")
        if self.app_env.lower() == "production" and self.meta_app_id and (
            not self.meta_app_secret or not self.social_token_encryption_key
        ):
            raise ValueError("META_APP_SECRET and SOCIAL_TOKEN_ENCRYPTION_KEY are required when Meta OAuth is configured")
        return self


    @property
    def whatsapp_login_configured(self) -> bool:
        return bool(self.whatsapp_access_token and self.whatsapp_phone_number_id and self.whatsapp_otp_template_name)

    @property
    def google_login_configured(self) -> bool:
        return bool(self.google_login_client_id and self.google_login_client_secret)


@lru_cache
def get_settings() -> Settings:
    """Return one cached settings instance for consistent application configuration."""
    return Settings()
