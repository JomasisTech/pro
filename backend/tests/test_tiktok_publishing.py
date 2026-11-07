from uuid import UUID
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
from app.models import SocialAccount, SocialCredential, TikTokPublishJob
from app.integrations.social_crypto import encrypt_token


def register(client, email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!", "full_name": "Owner", "organization_name": "TikTok Studio"})
    assert r.status_code == 201, r.text
    data = r.json(); data["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
    return data


def add_tiktok_account(session_factory, organization_id):
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(organization_id), provider="tiktok", provider_account_id="open-123", account_name="Creator", account_type="creator", status="connected", granted_scopes=["user.info.basic", "video.publish"])
        db.add(account); db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("test-access-token")))
        db.commit(); return str(account.id)


def test_creator_info_returns_live_creator_options(client, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings
    get_settings.cache_clear()
    owner = register(client, "tiktok-info@example.com")
    account_id = add_tiktok_account(session_factory, owner["organization"]["id"])
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"data": {"creator_username": "demo", "creator_nickname": "Demo Creator", "privacy_level_options": ["SELF_ONLY"], "comment_disabled": True, "duet_disabled": False, "stitch_disabled": False, "max_video_post_duration_sec": 60}, "error": {"code": "ok"}}
    monkeypatch.setattr("app.api.v1.tiktok_publishing.httpx.post", lambda *a, **k: Response())
    url = f"/api/v1/organizations/{owner['organization']['id']}/tiktok/accounts/{account_id}/creator-info"
    result = client.get(url, headers=owner["headers"])
    assert result.status_code == 200, result.text
    assert result.json()["creator_nickname"] == "Demo Creator"
    assert result.json()["comment_disabled"] is True
    get_settings.cache_clear()


def test_direct_post_requires_consent_and_uses_private_visibility_until_audited(client, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings
    get_settings.cache_clear()
    owner = register(client, "tiktok-post@example.com")
    account_id = add_tiktok_account(session_factory, owner["organization"]["id"])
    calls = []
    class Response:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return {"data": self.data, "error": {"code": "ok"}}
    def fake_post(url, **kwargs):
        calls.append((url, kwargs.get("json")))
        if url.endswith("creator_info/query/"):
            return Response({"privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"], "max_video_post_duration_sec": 180, "comment_disabled": False, "duet_disabled": False, "stitch_disabled": False})
        if url.endswith("video/init/"):
            return Response({"publish_id": "pub-123", "upload_url": "https://open-upload.tiktokapis.com/video/?token=secret"})
        return Response({"status": "PUBLISH_COMPLETE", "publicly_available_post_id": "post-789"})
    monkeypatch.setattr("app.api.v1.tiktok_publishing.httpx.post", fake_post)
    base = f"/api/v1/organizations/{owner['organization']['id']}/tiktok/accounts/{account_id}/direct-post"
    body = {"video_size": 1000000, "duration_seconds": 30, "caption": "Hello", "privacy_level": "SELF_ONLY", "allow_comment": False, "allow_duet": False, "allow_stitch": False, "consent_to_upload": False}
    assert client.post(base, json=body, headers=owner["headers"]).status_code == 400
    body["consent_to_upload"] = True
    result = client.post(base, json=body, headers=owner["headers"])
    assert result.status_code == 201, result.text
    assert result.json()["publish_id"] == "pub-123"
    assert result.json()["total_chunk_count"] == 1
    assert calls[1][1]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert calls[1][1]["post_info"]["disable_comment"] is True
    with session_factory() as db:
        job = db.query(TikTokPublishJob).one()
        assert job.status == "upload_pending"
        job_id = str(job.id)
    status_url = f"/api/v1/organizations/{owner['organization']['id']}/tiktok/publish-jobs/{job_id}"
    status = client.get(status_url, headers=owner["headers"])
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "published"
    assert status.json()["published"] is True
    activity = client.get(f"/api/v1/organizations/{owner['organization']['id']}/activity", headers=owner["headers"])
    assert activity.status_code == 200
    actions = [entry["action"] for entry in activity.json()]
    assert "tiktok_publish_job.created" in actions
    assert "tiktok_publish_job.status_changed" in actions
    get_settings.cache_clear()


def test_expiring_tiktok_token_is_refreshed_and_rotated(client, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "test-key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "test-secret")
    from app.config import get_settings
    from app.integrations.social_crypto import decrypt_token
    get_settings.cache_clear()
    owner = register(client, "tiktok-refresh@example.com")
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(owner["organization"]["id"]), provider="tiktok",
            provider_account_id="open-refresh", account_name="Refresh Creator", account_type="creator",
            status="connected", granted_scopes=["user.info.basic", "video.publish"],
            token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        db.add(account); db.flush()
        credential = SocialCredential(
            social_account_id=account.id, access_token_encrypted=encrypt_token("old-access"),
            refresh_token_encrypted=encrypt_token("old-refresh"),
        )
        db.add(credential); db.commit(); account_id = str(account.id)

    class RefreshResponse:
        def raise_for_status(self): pass
        def json(self): return {"data": {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 86400}, "error": {"code": "ok"}}
    class ApiResponse:
        def raise_for_status(self): pass
        def json(self): return {"data": {"creator_nickname": "Refreshed", "privacy_level_options": ["SELF_ONLY"], "max_video_post_duration_sec": 60}, "error": {"code": "ok"}}
    def fake_post(url, **kwargs):
        if url.endswith("/oauth/token/"):
            assert kwargs["data"]["grant_type"] == "refresh_token"
            assert kwargs["data"]["refresh_token"] == "old-refresh"
            return RefreshResponse()
        assert kwargs["headers"]["Authorization"] == "Bearer new-access"
        return ApiResponse()
    monkeypatch.setattr("app.api.v1.tiktok_publishing.httpx.post", fake_post)
    url = f"/api/v1/organizations/{owner['organization']['id']}/tiktok/accounts/{account_id}/creator-info"
    result = client.get(url, headers=owner["headers"])
    assert result.status_code == 200, result.text
    with session_factory() as db:
        saved = db.query(SocialCredential).filter_by(social_account_id=UUID(account_id)).one()
        assert decrypt_token(saved.access_token_encrypted) == "new-access"
        assert decrypt_token(saved.refresh_token_encrypted) == "new-refresh"
    get_settings.cache_clear()
