from datetime import datetime, timedelta, timezone
from uuid import UUID
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.config import get_settings
from app.integrations.social_crypto import encrypt_token
from app.models import CalendarEntry, SocialAccount, SocialCredential, TikTokPublishJob, YouTubePublishJob


def test_facebook_publish_persists_calendar_entry(client: TestClient, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    registered=client.post("/api/v1/auth/register",json={"email":"fb-pub@example.com","password":"StrongPass123!","full_name":"FB Owner","organization_name":"FB Studio"})
    assert registered.status_code==201
    body=registered.json(); headers={"Authorization":f"Bearer {body['access_token']}"}; org_id=UUID(body["organization"]["id"])
    with session_factory() as db:
        account=SocialAccount(organization_id=org_id,provider="facebook",provider_account_id="page-abc",account_name="BizPilot Page",account_type="page",granted_scopes=["pages_manage_posts"])
        db.add(account); db.flush(); db.add(SocialCredential(social_account_id=account.id,access_token_encrypted=encrypt_token("page-access-token"))); db.commit(); account_id=str(account.id)

    class FakeResponse:
        def raise_for_status(self): return None
        def json(self): return {"id":"page-abc_post-xyz"}
    class FakeClient:
        def __init__(self,*args,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): return False
        def post(self,url,data):
            assert url.endswith("/page-abc/feed")
            assert data["access_token"]=="page-access-token"
            assert data["message"]=="Hello from BizPilot"
            return FakeResponse()
    import app.api.v1.facebook_publishing as module
    monkeypatch.setattr(module.httpx,"Client",FakeClient)
    response=client.post(f"/api/v1/organizations/{org_id}/facebook/publish",headers=headers,json={"social_account_id":account_id,"message":"Hello from BizPilot"})
    assert response.status_code==200,response.text
    assert response.json()["status"]=="published"
    calendar=client.get(f"/api/v1/organizations/{org_id}/calendar",headers=headers)
    assert calendar.status_code==200
    assert any(item["platform"]=="facebook" and item["status"]=="published" for item in calendar.json())
    # Date-scoped calendar requests must include immediately published posts,
    # whose scheduled_at is null and whose calendar timestamp is created_at.
    now = datetime.now(timezone.utc)
    scoped = client.get(
        f"/api/v1/organizations/{org_id}/calendar",
        headers=headers,
        params={"start": (now-timedelta(days=1)).isoformat(), "end": (now+timedelta(days=1)).isoformat()},
    )
    assert scoped.status_code == 200, scoped.text
    assert any(item["platform"] == "facebook" and item["status"] == "published" for item in scoped.json())
    activity = client.get(f"/api/v1/organizations/{org_id}/activity", headers=headers)
    assert activity.status_code == 200
    assert "facebook_post.published" in [item["action"] for item in activity.json()]
    with session_factory() as db:
        assert db.query(CalendarEntry).filter_by(organization_id=org_id,external_post_id="page-abc_post-xyz").count()==1
    get_settings.cache_clear()


def test_facebook_schedule_requires_timezone_and_valid_window(client: TestClient, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode()); get_settings.cache_clear()
    registered=client.post("/api/v1/auth/register",json={"email":"fb-time@example.com","password":"StrongPass123!","full_name":"FB Owner","organization_name":"FB Studio"})
    body=registered.json(); headers={"Authorization":f"Bearer {body['access_token']}"}; org_id=UUID(body["organization"]["id"])
    with session_factory() as db:
        account=SocialAccount(organization_id=org_id,provider="facebook",provider_account_id="page-time",account_name="Time Page",account_type="page",granted_scopes=["pages_manage_posts"])
        db.add(account); db.flush(); db.add(SocialCredential(social_account_id=account.id,access_token_encrypted=encrypt_token("page-token"))); db.commit(); account_id=str(account.id)
    response=client.post(f"/api/v1/organizations/{org_id}/facebook/publish",headers=headers,json={"social_account_id":account_id,"message":"Test","scheduled_at":(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat()})
    assert response.status_code==422
    get_settings.cache_clear()


def test_calendar_includes_tiktok_and_youtube_publish_jobs(client: TestClient, session_factory):
    registered = client.post("/api/v1/auth/register", json={
        "email": "calendar-multi@example.com", "password": "StrongPass123!",
        "full_name": "Calendar Owner", "organization_name": "Calendar Studio",
    })
    assert registered.status_code == 201, registered.text
    body = registered.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    org_id = UUID(body["organization"]["id"])
    with session_factory() as db:
        tiktok = SocialAccount(organization_id=org_id, provider="tiktok", provider_account_id="tt-calendar", account_name="TikTok", account_type="creator")
        youtube = SocialAccount(organization_id=org_id, provider="youtube", provider_account_id="yt-calendar", account_name="YouTube", account_type="channel")
        db.add_all([tiktok, youtube]); db.flush()
        db.add(TikTokPublishJob(organization_id=org_id, social_account_id=tiktok.id, publish_id="tt-publish-1", caption="TikTok launch", privacy_level="SELF_ONLY", status="published"))
        db.add(YouTubePublishJob(organization_id=org_id, social_account_id=youtube.id, video_id="yt-video-1", upload_session_encrypted=b"encrypted-session", title="YouTube launch", description="Video description", privacy_status="private", status="published"))
        db.commit()

    response = client.get(f"/api/v1/organizations/{org_id}/calendar", headers=headers)
    assert response.status_code == 200, response.text
    by_platform = {item["platform"]: item for item in response.json() if item["kind"] == "publish_job"}
    assert by_platform["tiktok"]["title"] == "TikTok launch"
    assert by_platform["tiktok"]["external_post_id"] == "tt-publish-1"
    assert by_platform["youtube"]["title"] == "YouTube launch"
    assert by_platform["youtube"]["external_post_id"] == "yt-video-1"

    now = datetime.now(timezone.utc)
    scoped = client.get(f"/api/v1/organizations/{org_id}/calendar", headers=headers,
        params={"start": (now-timedelta(days=1)).isoformat(), "end": (now+timedelta(days=1)).isoformat()})
    assert scoped.status_code == 200, scoped.text
    assert {item["platform"] for item in scoped.json() if item["kind"] == "publish_job"} == {"tiktok", "youtube"}
