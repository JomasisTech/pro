"""Facebook Page text/link publishing and organization calendar."""
from datetime import datetime, timezone
from uuid import UUID
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.v1.organizations import get_membership, require_roles
from app.core.database import get_db
from app.integrations.social_crypto import decrypt_token
from app.models import Membership, SocialAccount, SocialCredential, ContentDraft, CalendarEntry, TikTokPublishJob, YouTubePublishJob, ScheduledPost
from app.modules.audit.activity import record_activity

router=APIRouter(prefix="/organizations/{organization_id}",tags=["Facebook publishing and calendar"])
GRAPH="https://graph.facebook.com/v26.0"
class FacebookPostRequest(BaseModel):
    social_account_id: UUID
    message: str=Field(min_length=1,max_length=63206)
    link: HttpUrl|None=None
    scheduled_at: datetime|None=None


def _page_token(db,org_id,account_id):
    account=db.scalar(select(SocialAccount).where(SocialAccount.id==account_id,SocialAccount.organization_id==org_id,SocialAccount.provider=="facebook",SocialAccount.status=="connected"))
    if not account: raise HTTPException(404,"Connected Facebook Page not found")
    cred=db.scalar(select(SocialCredential).where(SocialCredential.social_account_id==account.id))
    if not cred: raise HTTPException(409,"Facebook Page credentials are missing; reconnect the Page")
    try: return account,decrypt_token(cred.access_token_encrypted)
    except RuntimeError: raise HTTPException(503,"Facebook credentials cannot be decrypted; reconnect the Page") from None

@router.post("/facebook/publish")
def publish_facebook_post(payload:FacebookPostRequest,membership:Membership=Depends(require_roles("owner","admin")),db:Session=Depends(get_db)):
    account,token=_page_token(db,membership.organization_id,payload.social_account_id)
    data={"message":payload.message,"access_token":token}
    if payload.link: data["link"]=str(payload.link)
    if payload.scheduled_at:
        dt=payload.scheduled_at
        if dt.tzinfo is None: raise HTTPException(422,"scheduled_at must include a timezone")
        when=int(dt.timestamp()); now=int(datetime.now(timezone.utc).timestamp())
        if when < now+600 or when > now+30*24*3600: raise HTTPException(422,"Facebook scheduled posts must be at least 10 minutes and no more than 30 days ahead")
        data.update({"published":"false","scheduled_publish_time":str(when)})
    try:
        with httpx.Client(timeout=30,follow_redirects=False) as client:
            response=client.post(f"{GRAPH}/{account.provider_account_id}/feed",data=data); response.raise_for_status(); result=response.json()
    except httpx.HTTPStatusError as exc:
        detail="Facebook rejected the post. Check Page permissions, content and app review status."
        try: detail=exc.response.json().get("error",{}).get("message") or detail
        except ValueError: pass
        raise HTTPException(502,detail) from None
    except httpx.HTTPError: raise HTTPException(502,"Facebook could not be reached. No successful post was confirmed.") from None
    post_id=result.get("id")
    if not post_id: raise HTTPException(502,"Facebook did not confirm a post identifier")
    entry=CalendarEntry(organization_id=membership.organization_id,social_account_id=account.id,provider="facebook",title=payload.message[:300],content=payload.message,external_post_id=str(post_id),status="scheduled" if payload.scheduled_at else "published",scheduled_at=payload.scheduled_at)
    db.add(entry)
    db.flush()
    record_activity(
        db, membership, "facebook_post.scheduled" if payload.scheduled_at else "facebook_post.published",
        "calendar_entry", entry.id,
        f'{"Scheduled" if payload.scheduled_at else "Published"} Facebook post "{payload.message[:60]}"',
    )
    db.commit()
    return {"provider":"facebook","account_name":account.account_name,"post_id":post_id,"status":"scheduled" if payload.scheduled_at else "published","scheduled_at":payload.scheduled_at,"calendar_entry_id":str(entry.id)}

@router.get("/calendar")
def get_calendar(start:datetime|None=None,end:datetime|None=None,membership:Membership=Depends(get_membership),db:Session=Depends(get_db)):
    """Unified calendar feed: saved drafts plus Facebook scheduled/published activity placeholders."""
    query=select(ContentDraft).where(ContentDraft.organization_id==membership.organization_id)
    if start: query=query.where(ContentDraft.created_at>=start)
    if end: query=query.where(ContentDraft.created_at<=end)
    drafts=db.scalars(query.order_by(ContentDraft.created_at.desc()).limit(100)).all()
    entry_query=select(CalendarEntry).where(CalendarEntry.organization_id==membership.organization_id)
    # Immediate posts have no scheduled_at. Use their creation time as the
    # calendar timestamp so date-scoped views do not silently hide them.
    calendar_timestamp = func.coalesce(CalendarEntry.scheduled_at, CalendarEntry.created_at)
    if start:
        entry_query = entry_query.where(calendar_timestamp >= start)
    if end:
        entry_query = entry_query.where(calendar_timestamp <= end)
    entries=db.scalars(entry_query.order_by(CalendarEntry.scheduled_at.asc().nullslast(),CalendarEntry.created_at.desc()).limit(200)).all()
    result=[{"id":str(d.id),"kind":"draft","platform":"all","title":d.topic or d.content[:72],"content":d.content,"status":d.status,"created_at":d.created_at,"scheduled_at":None} for d in drafts]
    result.extend({"id":str(e.id),"kind":"post","platform":e.provider,"title":e.title,"content":e.content,"status":e.status,"created_at":e.created_at,"scheduled_at":e.scheduled_at,"external_post_id":e.external_post_id} for e in entries)

    # TikTok and YouTube currently publish immediately after browser-driven uploads.
    # Surface their durable provider jobs as history/activity, not as scheduled posts.
    tiktok_query = select(TikTokPublishJob).where(
        TikTokPublishJob.organization_id == membership.organization_id
    )
    youtube_query = select(YouTubePublishJob).where(
        YouTubePublishJob.organization_id == membership.organization_id
    )
    if start:
        tiktok_query = tiktok_query.where(TikTokPublishJob.created_at >= start)
        youtube_query = youtube_query.where(YouTubePublishJob.created_at >= start)
    if end:
        tiktok_query = tiktok_query.where(TikTokPublishJob.created_at <= end)
        youtube_query = youtube_query.where(YouTubePublishJob.created_at <= end)
    tiktok_jobs = db.scalars(tiktok_query.order_by(TikTokPublishJob.created_at.desc()).limit(200)).all()
    youtube_jobs = db.scalars(youtube_query.order_by(YouTubePublishJob.created_at.desc()).limit(200)).all()
    scheduled_query = select(ScheduledPost).where(ScheduledPost.organization_id == membership.organization_id)
    if start:
        scheduled_query = scheduled_query.where(ScheduledPost.scheduled_at >= start)
    if end:
        scheduled_query = scheduled_query.where(ScheduledPost.scheduled_at <= end)
    scheduled_items = db.scalars(scheduled_query.order_by(ScheduledPost.scheduled_at.asc()).limit(200)).all()
    result.extend({
        "id": str(item.id), "kind": "scheduled_post", "platform": item.provider,
        "title": item.title, "content": item.content, "status": item.status,
        "created_at": item.created_at, "scheduled_at": item.scheduled_at,
        "external_post_id": item.external_post_id,
    } for item in scheduled_items)

    result.extend({
        "id": str(job.id), "kind": "publish_job", "platform": "tiktok",
        "title": job.caption[:300] or "TikTok video", "content": job.caption,
        "status": job.status, "created_at": job.created_at, "scheduled_at": None,
        "external_post_id": job.publish_id,
    } for job in tiktok_jobs)
    result.extend({
        "id": str(job.id), "kind": "publish_job", "platform": "youtube",
        "title": job.title, "content": job.description, "status": job.status,
        "created_at": job.created_at, "scheduled_at": None,
        "external_post_id": job.video_id,
    } for job in youtube_jobs)
    return sorted(result,key=lambda item:item.get("scheduled_at") or item["created_at"])
