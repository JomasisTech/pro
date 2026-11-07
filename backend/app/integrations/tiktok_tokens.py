"""TikTok access-token retrieval and refresh shared by read integrations."""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.social_crypto import decrypt_token, encrypt_token
from app.models import SocialAccount, SocialCredential


REFRESH_WINDOW = timedelta(minutes=5)


def get_tiktok_access_token(
    db: Session,
    account: SocialAccount,
    credential: SocialCredential,
    *,
    now: datetime | None = None,
) -> str:
    """Return a usable TikTok token, refreshing it before expiry when possible."""
    if account.provider != "tiktok":
        raise ValueError("TikTok token refresh was requested for a non-TikTok account")
    current = now or datetime.now(timezone.utc)
    expiry = account.token_expires_at
    if expiry is None:
        return decrypt_token(credential.access_token_encrypted)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if expiry > current + REFRESH_WINDOW:
        return decrypt_token(credential.access_token_encrypted)
    if expiry <= current:
        if not credential.refresh_token_encrypted:
            raise RuntimeError("TikTok authorization has expired; reconnect the account")
    if not credential.refresh_token_encrypted:
        raise RuntimeError("TikTok authorization cannot be refreshed; reconnect the account")

    settings = get_settings()
    if not (settings.tiktok_client_key and settings.tiktok_client_secret):
        raise RuntimeError("TikTok refresh configuration is unavailable")
    refresh_token = decrypt_token(credential.refresh_token_encrypted)
    try:
        response = httpx.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            timeout=20.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        body = response.json()
        body = body.get("data", body) if isinstance(body, dict) else {}
        refreshed = body.get("access_token")
        expires_in = int(body.get("expires_in") or 0)
        if not isinstance(refreshed, str) or not refreshed or expires_in <= 0:
            raise ValueError("TikTok returned an invalid refresh response")
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise RuntimeError("TikTok authorization could not be refreshed; reconnect the account") from None

    credential.access_token_encrypted = encrypt_token(refreshed)
    rotated_refresh = body.get("refresh_token")
    if isinstance(rotated_refresh, str) and rotated_refresh:
        credential.refresh_token_encrypted = encrypt_token(rotated_refresh)
    account.token_expires_at = current + timedelta(seconds=expires_in)
    db.commit()
    return refreshed
