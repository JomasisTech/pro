"""Social account inventory, provider readiness, and disconnect controls.

Provider OAuth callbacks live in their provider-specific routers. This API never
fabricates a connected account or accepts access tokens from the browser.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.organizations import get_membership, require_roles
from app.core.database import get_db
from app.models import Membership, SocialAccount, SocialCredential
from app.modules.audit.activity import record_activity
from app.config import get_settings

router = APIRouter(prefix="/organizations/{organization_id}/social-accounts", tags=["social accounts"])

PROVIDERS = [
    {"key": "instagram", "name": "Instagram", "description": "Professional Instagram accounts", "connection_available": False},
    {"key": "facebook", "name": "Facebook", "description": "Facebook Pages", "connection_available": False},
    {"key": "tiktok", "name": "TikTok", "description": "TikTok accounts and short-form video publishing", "connection_available": False},
    {"key": "youtube", "name": "YouTube", "description": "YouTube channels, Shorts and long-form video publishing", "connection_available": False},
    {"key": "linkedin", "name": "LinkedIn", "description": "LinkedIn Pages and profiles where approved", "connection_available": False},
]


@router.get("/providers")
def list_providers(membership: Membership = Depends(get_membership)) -> list[dict]:
    """List supported providers and whether their OAuth integration is enabled."""
    settings = get_settings()
    rows = [dict(item) for item in PROVIDERS]
    rows[0]["connection_available"] = bool(settings.meta_app_id and settings.meta_app_secret and settings.social_token_encryption_key and settings.meta_redirect_uri)
    rows[1]["connection_available"] = bool(settings.meta_app_id and settings.meta_app_secret and settings.social_token_encryption_key and settings.facebook_redirect_uri)
    rows[2]["connection_available"] = bool(settings.tiktok_client_key and settings.tiktok_client_secret and settings.social_token_encryption_key and settings.tiktok_redirect_uri)
    rows[3]["connection_available"] = bool(settings.google_client_id and settings.google_client_secret and settings.social_token_encryption_key and settings.youtube_redirect_uri)
    return rows


@router.get("")
def list_social_accounts(membership: Membership = Depends(get_membership), db: Session = Depends(get_db)) -> list[dict]:
    accounts = db.scalars(select(SocialAccount).where(
        SocialAccount.organization_id == membership.organization_id
    ).order_by(SocialAccount.connected_at.desc())).all()
    return [{"id": str(a.id), "provider": a.provider, "provider_account_id": a.provider_account_id,
             "account_name": a.account_name, "account_type": a.account_type, "status": a.status,
             "granted_scopes": a.granted_scopes, "connected_at": a.connected_at,
             "last_synced_at": a.last_synced_at, "token_expires_at": a.token_expires_at} for a in accounts]


@router.delete("/{account_id}", status_code=204)
def disconnect_social_account(
    account_id: UUID,
    membership: Membership = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> Response:
    account = db.scalar(select(SocialAccount).where(
        SocialAccount.id == account_id,
        SocialAccount.organization_id == membership.organization_id,
    ))
    if account is None:
        raise HTTPException(status_code=404, detail="Social account not found")
    credential = db.scalar(select(SocialCredential).where(SocialCredential.social_account_id == account.id))
    record_activity(
        db, membership, "social_account.disconnected", "social_account", account.id,
        f'Disconnected {account.provider} account "{account.account_name[:60]}"',
    )
    if credential is not None:
        db.delete(credential)
    db.delete(account)
    db.commit()
    return Response(status_code=204)
