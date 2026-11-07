"""Server-side Meta Instagram Login OAuth flow.

Only Instagram professional accounts are supported by this first Meta path. Facebook Page
OAuth is a separate permission flow and is deliberately not represented as connected here.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.database import get_db
from app.api.v1.organizations import require_roles
from app.models import Membership, SocialAccount, SocialCredential, SocialOAuthState
from app.integrations.social_crypto import encrypt_token
from app.modules.audit.activity import record_activity

router = APIRouter(prefix="/organizations/{organization_id}/social-accounts", tags=["social accounts oauth"])
callback_router = APIRouter(prefix="/social-oauth/meta/instagram", tags=["social accounts oauth"])
tiktok_callback_router = APIRouter(prefix="/social-oauth/tiktok", tags=["social accounts oauth"])
youtube_callback_router = APIRouter(prefix="/social-oauth/youtube", tags=["social accounts oauth"])


def _record_connected_account(db: Session, state_row: SocialOAuthState, account: SocialAccount) -> None:
    """Audit a provider connection in the same transaction as its credentials."""
    membership = db.scalar(select(Membership).where(
        Membership.organization_id == state_row.organization_id,
        Membership.user_id == state_row.user_id,
    ))
    if membership is None:
        raise ValueError("The user is no longer a member of this workspace")
    record_activity(
        db, membership, "social_account.connected", "social_account", account.id,
        f'Connected {account.provider} account "{account.account_name[:60]}"',
    )


def _configured() -> bool:
    s = get_settings()
    return bool(s.meta_app_id and s.meta_app_secret and s.social_token_encryption_key and s.meta_redirect_uri)


@router.post("/instagram/connect")
def start_instagram_login(
    organization_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not _configured():
        raise HTTPException(status_code=503, detail="Instagram authorization is not configured yet")
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(SocialOAuthState(
        state_hash=hashlib.sha256(state.encode()).hexdigest(), provider="instagram",
        organization_id=membership.organization_id, user_id=membership.user_id,
        expires_at=now + timedelta(seconds=settings.social_oauth_state_ttl_seconds),
    ))
    db.commit()
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.meta_redirect_uri,
        "response_type": "code",
        "scope": "instagram_business_basic,instagram_business_content_publish",
        "state": state,
    }
    return {"authorization_url": "https://www.instagram.com/oauth/authorize?" + urlencode(params)}


@callback_router.get("/callback")
def instagram_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    def finish(result: str) -> RedirectResponse:
        separator = "&" if "?" in settings.meta_frontend_return_url else "?"
        return RedirectResponse(settings.meta_frontend_return_url + separator + urlencode({"provider": "instagram", "result": result}), status_code=303)

    if error or not code or not state or not _configured():
        return finish("cancelled" if error else "failed")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    state_row = db.scalar(select(SocialOAuthState).where(SocialOAuthState.state_hash == state_hash, SocialOAuthState.provider == "instagram"))
    now = datetime.now(timezone.utc)
    if state_row is None or state_row.consumed_at is not None or state_row.expires_at.replace(tzinfo=timezone.utc) <= now:
        return finish("invalid_state")
    state_row.consumed_at = now
    db.commit()

    try:
        with httpx.Client(timeout=15.0, follow_redirects=False) as client:
            token_response = client.post("https://api.instagram.com/oauth/access_token", data={
                "client_id": settings.meta_app_id,
                "client_secret": settings.meta_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": settings.meta_redirect_uri,
                "code": code,
            })
            token_response.raise_for_status()
            short_data = token_response.json()
            short_token = short_data.get("access_token")
            if not isinstance(short_token, str) or not short_token:
                raise ValueError("Meta did not return an access token")
            long_response = client.get("https://graph.instagram.com/access_token", params={
                "grant_type": "ig_exchange_token", "client_secret": settings.meta_app_secret,
                "access_token": short_token,
            })
            long_response.raise_for_status()
            long_data = long_response.json()
            access_token = long_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Meta did not return a long-lived access token")
            profile_response = client.get("https://graph.instagram.com/me", params={
                "fields": "user_id,username,account_type", "access_token": access_token,
            })
            profile_response.raise_for_status()
            profile = profile_response.json()
            account_id = str(profile.get("user_id") or profile.get("id") or "")
            username = str(profile.get("username") or "")
            if not account_id or not username:
                raise ValueError("Meta did not return the Instagram account identity")
            expires_in = int(long_data.get("expires_in") or 5_184_000)
            expires_at = now + timedelta(seconds=max(0, expires_in))
            account = db.scalar(select(SocialAccount).where(
                SocialAccount.organization_id == state_row.organization_id,
                SocialAccount.provider == "instagram", SocialAccount.provider_account_id == account_id,
            ))
            if account is None:
                account = SocialAccount(
                    organization_id=state_row.organization_id, provider="instagram",
                    provider_account_id=account_id, account_name="@" + username,
                    account_type=str(profile.get("account_type") or "professional"),
                    status="connected", granted_scopes=["instagram_business_basic", "instagram_business_content_publish"], token_expires_at=expires_at,
                )
                db.add(account)
                db.flush()
            else:
                account.account_name = "@" + username
                account.account_type = str(profile.get("account_type") or "professional")
                account.status = "connected"
                account.granted_scopes = ["instagram_business_basic", "instagram_business_content_publish"]
                account.token_expires_at = expires_at
            credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
            if credential is None:
                credential = SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token(access_token))
                db.add(credential)
            else:
                credential.access_token_encrypted = encrypt_token(access_token)
            _record_connected_account(db, state_row, account)
            db.commit()
        return finish("connected")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError):
        db.rollback()
        return finish("failed")


# TikTok Login Kit uses OAuth 2.0 and exchanges authorization codes server-side.
# The web flow relies on a one-time state value; client secrets and tokens never reach the browser.
@router.post("/tiktok/connect")
def start_tiktok_login(
    organization_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not (settings.tiktok_client_key and settings.tiktok_client_secret and settings.social_token_encryption_key and settings.tiktok_redirect_uri):
        raise HTTPException(status_code=503, detail="TikTok authorization is not configured yet")
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(SocialOAuthState(
        state_hash=hashlib.sha256(state.encode()).hexdigest(), provider="tiktok",
        organization_id=membership.organization_id, user_id=membership.user_id,
        expires_at=now + timedelta(seconds=settings.social_oauth_state_ttl_seconds),
    ))
    db.commit()
    params = {
        "client_key": settings.tiktok_client_key,
        "response_type": "code",
        "scope": "user.info.basic,video.list,video.publish",
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
    }
    return {"authorization_url": "https://www.tiktok.com/v2/auth/authorize/?" + urlencode(params)}


@tiktok_callback_router.get("/callback")
def tiktok_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    def finish(result: str) -> RedirectResponse:
        separator = "&" if "?" in settings.tiktok_frontend_return_url else "?"
        return RedirectResponse(settings.tiktok_frontend_return_url + separator + urlencode({"provider": "tiktok", "result": result}), status_code=303)

    configured = bool(settings.tiktok_client_key and settings.tiktok_client_secret and settings.social_token_encryption_key and settings.tiktok_redirect_uri)
    if error or not code or not state or not configured:
        return finish("cancelled" if error else "failed")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    state_row = db.scalar(select(SocialOAuthState).where(
        SocialOAuthState.state_hash == state_hash, SocialOAuthState.provider == "tiktok"
    ))
    now = datetime.now(timezone.utc)
    if state_row is None or state_row.consumed_at is not None or state_row.expires_at.replace(tzinfo=timezone.utc) <= now:
        return finish("invalid_state")
    state_row.consumed_at = now
    db.commit()

    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            token_response = client.post("https://open.tiktokapis.com/v2/oauth/token/", data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.tiktok_redirect_uri,
            })
            token_response.raise_for_status()
            token_data = token_response.json()
            token_data = token_data.get("data", token_data)
            access_token = token_data.get("access_token")
            open_id = token_data.get("open_id")
            if not isinstance(access_token, str) or not access_token or not open_id:
                raise ValueError("TikTok did not return the required account token and identity")
            info_response = client.get(
                "https://open.tiktokapis.com/v2/user/info/",
                params={"fields": "open_id,display_name,avatar_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            info_response.raise_for_status()
            info_data = info_response.json().get("data", {}).get("user", {})
            if str(info_data.get("open_id") or open_id) != str(open_id):
                raise ValueError("TikTok account identity did not match the authorized user")
            display_name = str(info_data.get("display_name") or "TikTok creator")
            expires_in = int(token_data.get("expires_in") or 86400)
            expires_at = now + timedelta(seconds=max(0, expires_in))
            scopes = token_data.get("scope") or "user.info.basic,video.list,video.publish"
            granted_scopes = scopes.split(",") if isinstance(scopes, str) else list(scopes)
            account = db.scalar(select(SocialAccount).where(
                SocialAccount.organization_id == state_row.organization_id,
                SocialAccount.provider == "tiktok", SocialAccount.provider_account_id == str(open_id),
            ))
            if account is None:
                account = SocialAccount(
                    organization_id=state_row.organization_id, provider="tiktok",
                    provider_account_id=str(open_id), account_name=display_name,
                    account_type="creator", status="connected", granted_scopes=granted_scopes,
                    token_expires_at=expires_at,
                )
                db.add(account)
                db.flush()
            else:
                account.account_name = display_name
                account.status = "connected"
                account.granted_scopes = granted_scopes
                account.token_expires_at = expires_at
            credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
            if credential is None:
                credential = SocialCredential(
                    social_account_id=account.id,
                    access_token_encrypted=encrypt_token(access_token),
                    refresh_token_encrypted=encrypt_token(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
                )
                db.add(credential)
            else:
                credential.access_token_encrypted = encrypt_token(access_token)
                if token_data.get("refresh_token"):
                    credential.refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
            _record_connected_account(db, state_row, account)
            db.commit()
        return finish("connected")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError):
        db.rollback()
        return finish("failed")


# YouTube uses Google's server-side OAuth authorization-code flow. Request
# upload and read-only scopes explicitly; read access powers Brand Intelligence.
@router.post("/youtube/connect")
def start_youtube_login(
    organization_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    if not (settings.google_client_id and settings.google_client_secret and settings.social_token_encryption_key and settings.youtube_redirect_uri):
        raise HTTPException(status_code=503, detail="YouTube authorization is not configured yet")
    state = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db.add(SocialOAuthState(
        state_hash=hashlib.sha256(state.encode()).hexdigest(), provider="youtube",
        organization_id=membership.organization_id, user_id=membership.user_id,
        expires_at=now + timedelta(seconds=settings.social_oauth_state_ttl_seconds),
    ))
    db.commit()
    scopes = "openid email profile https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.youtube_redirect_uri,
        "response_type": "code",
        "scope": scopes,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return {"authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@youtube_callback_router.get("/callback")
def youtube_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    def finish(result: str) -> RedirectResponse:
        separator = "&" if "?" in settings.youtube_frontend_return_url else "?"
        return RedirectResponse(settings.youtube_frontend_return_url + separator + urlencode({"provider": "youtube", "result": result}), status_code=303)

    configured = bool(settings.google_client_id and settings.google_client_secret and settings.social_token_encryption_key and settings.youtube_redirect_uri)
    if error or not code or not state or not configured:
        return finish("cancelled" if error else "failed")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    state_row = db.scalar(select(SocialOAuthState).where(
        SocialOAuthState.state_hash == state_hash, SocialOAuthState.provider == "youtube"
    ))
    now = datetime.now(timezone.utc)
    if state_row is None or state_row.consumed_at is not None or state_row.expires_at.replace(tzinfo=timezone.utc) <= now:
        return finish("invalid_state")
    state_row.consumed_at = now
    db.commit()

    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            token_response = client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.youtube_redirect_uri,
                "grant_type": "authorization_code",
            })
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Google did not return an access token")
            identity_response = client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            identity_response.raise_for_status()
            identity = identity_response.json()
            subject = str(identity.get("sub") or "")
            display_name = str(identity.get("name") or identity.get("email") or "YouTube channel owner")
            if not subject:
                raise ValueError("Google did not return an account identity")
            expires_in = int(token_data.get("expires_in") or 3600)
            expires_at = now + timedelta(seconds=max(0, expires_in))
            scopes = token_data.get("scope") or "openid email profile https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
            granted_scopes = scopes.split(" ") if isinstance(scopes, str) else list(scopes)
            account = db.scalar(select(SocialAccount).where(
                SocialAccount.organization_id == state_row.organization_id,
                SocialAccount.provider == "youtube", SocialAccount.provider_account_id == subject,
            ))
            if account is None:
                account = SocialAccount(
                    organization_id=state_row.organization_id, provider="youtube",
                    provider_account_id=subject, account_name=display_name,
                    account_type="channel_owner", status="connected", granted_scopes=granted_scopes,
                    token_expires_at=expires_at,
                )
                db.add(account)
                db.flush()
            else:
                account.account_name = display_name
                account.status = "connected"
                account.granted_scopes = granted_scopes
                account.token_expires_at = expires_at
            credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
            if credential is None:
                credential = SocialCredential(
                    social_account_id=account.id,
                    access_token_encrypted=encrypt_token(access_token),
                    refresh_token_encrypted=encrypt_token(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
                )
                db.add(credential)
            else:
                credential.access_token_encrypted = encrypt_token(access_token)
                if token_data.get("refresh_token"):
                    credential.refresh_token_encrypted = encrypt_token(token_data["refresh_token"])
            _record_connected_account(db, state_row, account)
            db.commit()
        return finish("connected")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError):
        db.rollback()
        return finish("failed")
