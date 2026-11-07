"""Facebook Pages OAuth. Page tokens are exchanged and encrypted server-side."""
from datetime import datetime, timedelta, timezone
import hashlib, secrets
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
from app.modules.audit.activity import record_activity
from app.integrations.social_crypto import encrypt_token

router = APIRouter(prefix="/organizations/{organization_id}/social-accounts", tags=["Facebook Pages OAuth"])
callback_router = APIRouter(prefix="/social-oauth/facebook", tags=["Facebook Pages OAuth"])
SCOPES = "pages_show_list,pages_read_engagement,pages_manage_posts"
GRAPH = "https://graph.facebook.com/v26.0"

def configured():
    s=get_settings(); return bool(s.meta_app_id and s.meta_app_secret and s.social_token_encryption_key and s.facebook_redirect_uri)

@router.post("/facebook/connect")
def start_facebook_login(organization_id: UUID, membership: Membership=Depends(require_roles("owner","admin")), db: Session=Depends(get_db)):
    s=get_settings()
    if not configured(): raise HTTPException(503,"Facebook Pages authorization is not configured")
    state=secrets.token_urlsafe(32); now=datetime.now(timezone.utc)
    db.add(SocialOAuthState(state_hash=hashlib.sha256(state.encode()).hexdigest(),provider="facebook",organization_id=membership.organization_id,user_id=membership.user_id,expires_at=now+timedelta(seconds=s.social_oauth_state_ttl_seconds)))
    db.commit()
    params={"client_id":s.meta_app_id,"redirect_uri":s.facebook_redirect_uri,"response_type":"code","scope":SCOPES,"state":state}
    return {"authorization_url":"https://www.facebook.com/v26.0/dialog/oauth?"+urlencode(params)}

@callback_router.get("/callback")
def facebook_callback(code:str|None=Query(None),state:str|None=Query(None),error:str|None=Query(None),db:Session=Depends(get_db)):
    s=get_settings()
    def finish(result):
        sep="&" if "?" in s.facebook_frontend_return_url else "?"
        return RedirectResponse(s.facebook_frontend_return_url+sep+urlencode({"provider":"facebook","result":result}),status_code=303)
    if error or not code or not state or not configured(): return finish("cancelled" if error else "failed")
    row=db.scalar(select(SocialOAuthState).where(SocialOAuthState.state_hash==hashlib.sha256(state.encode()).hexdigest(),SocialOAuthState.provider=="facebook"))
    now=datetime.now(timezone.utc)
    if row is None or row.consumed_at is not None or row.expires_at.replace(tzinfo=timezone.utc)<=now: return finish("invalid_state")
    row.consumed_at=now; db.commit()
    try:
        with httpx.Client(timeout=20,follow_redirects=False) as c:
            r=c.get(f"{GRAPH}/oauth/access_token",params={"client_id":s.meta_app_id,"client_secret":s.meta_app_secret,"redirect_uri":s.facebook_redirect_uri,"code":code}); r.raise_for_status(); short=r.json()["access_token"]
            r=c.get(f"{GRAPH}/oauth/access_token",params={"grant_type":"fb_exchange_token","client_id":s.meta_app_id,"client_secret":s.meta_app_secret,"fb_exchange_token":short}); r.raise_for_status(); token=r.json()["access_token"]
            params={"fields":"id,name,access_token,tasks","limit":100,"access_token":token}
            pages=[]
            seen_cursors=set()
            for _ in range(100):
                r=c.get(f"{GRAPH}/me/accounts",params=params); r.raise_for_status()
                body=r.json()
                pages.extend(body.get("data",[]))
                paging=body.get("paging") or {}
                next_cursor=(paging.get("cursors") or {}).get("after")
                if not paging.get("next"):
                    break
                if not next_cursor or next_cursor in seen_cursors:
                    raise ValueError("Facebook Page discovery returned an invalid pagination cursor")
                seen_cursors.add(next_cursor)
                params={**params,"after":next_cursor}
            else:
                raise ValueError("Facebook Page discovery exceeded the safe pagination limit")
        if not pages: return finish("no_pages")
        connected_count=0
        for page in pages:
            page_id=str(page.get("id") or ""); page_name=str(page.get("name") or "Facebook Page"); page_token=page.get("access_token")
            tasks=page.get("tasks") or []
            if not page_id or not page_token or "CREATE_CONTENT" not in tasks: continue
            account=db.scalar(select(SocialAccount).where(SocialAccount.organization_id==row.organization_id,SocialAccount.provider=="facebook",SocialAccount.provider_account_id==page_id))
            if account is None:
                account=SocialAccount(organization_id=row.organization_id,provider="facebook",provider_account_id=page_id,account_name=page_name,account_type="page",status="connected",granted_scopes=SCOPES.split(",")); db.add(account); db.flush()
            else:
                account.account_name=page_name; account.status="connected"; account.granted_scopes=SCOPES.split(",")
            cred=db.scalar(select(SocialCredential).where(SocialCredential.social_account_id==account.id))
            if cred is None: db.add(SocialCredential(social_account_id=account.id,access_token_encrypted=encrypt_token(page_token)))
            else: cred.access_token_encrypted=encrypt_token(page_token)
            membership=db.scalar(select(Membership).where(Membership.organization_id==row.organization_id,Membership.user_id==row.user_id))
            if membership is None: raise ValueError("The user is no longer a member of this workspace")
            record_activity(db,membership,"social_account.connected","social_account",account.id,f'Connected Facebook Page "{page_name[:60]}"')
            connected_count += 1
        if connected_count == 0:
            db.rollback()
            return finish("no_eligible_pages")
        db.commit()
        return finish("connected")
    except (httpx.HTTPError,KeyError,ValueError,TypeError,RuntimeError):
        db.rollback(); return finish("failed")
