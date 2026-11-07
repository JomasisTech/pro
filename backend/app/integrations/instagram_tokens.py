"""Instagram long-lived access-token refresh helpers.

Instagram Login long-lived tokens can be refreshed while still valid. Facebook Page
tokens are intentionally handled separately because they do not use this refresh flow.
"""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.integrations.social_crypto import decrypt_token, encrypt_token
from app.models import SocialAccount, SocialCredential

INSTAGRAM_REFRESH_URL = "https://graph.instagram.com/refresh_access_token"
REFRESH_WINDOW = timedelta(days=7)


def get_instagram_access_token(
    db: Session,
    account: SocialAccount,
    credential: SocialCredential,
    *,
    now: datetime | None = None,
    refresh_window: timedelta = REFRESH_WINDOW,
) -> str:
    """Return a usable token, refreshing it before expiry when possible.

    Expired tokens cannot be refreshed by this endpoint and require reconnection. A
    successful refresh is committed immediately so a later publishing failure does not
    discard the renewed credential.
    """
    if account.provider != "instagram":
        raise ValueError("Instagram token refresh was requested for a non-Instagram account")

    current = now or datetime.now(timezone.utc)
    expiry = account.token_expires_at
    if expiry is None:
        return decrypt_token(credential.access_token_encrypted)
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    token = decrypt_token(credential.access_token_encrypted)
    if expiry > current + refresh_window:
        return token
    if expiry <= current:
        raise RuntimeError("Instagram authorization has expired; reconnect the account")

    try:
        response = httpx.get(
            INSTAGRAM_REFRESH_URL,
            params={"grant_type": "ig_refresh_token", "access_token": token},
            timeout=20,
            follow_redirects=False,
        )
        response.raise_for_status()
        body = response.json()
        refreshed = body.get("access_token")
        expires_in = int(body.get("expires_in") or 0)
        if not isinstance(refreshed, str) or not refreshed or expires_in <= 0:
            raise ValueError("Instagram returned an invalid token refresh response")
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        raise RuntimeError("Instagram authorization could not be refreshed; reconnect the account") from exc

    credential.access_token_encrypted = encrypt_token(refreshed)
    account.token_expires_at = current + timedelta(seconds=expires_in)
    db.commit()
    return refreshed
