from uuid import UUID
from cryptography.fernet import Fernet
from app.models import SocialAccount, SocialCredential, YouTubePublishJob
from app.integrations.social_crypto import encrypt_token


def register(client, email):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!", "full_name": "Owner", "organization_name": "YouTube Studio"})
    assert r.status_code == 201, r.text
    data = r.json(); data["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
    return data


def add_youtube_account(session_factory, org_id):
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(org_id), provider="youtube", provider_account_id="channel-123", account_name="Demo Channel", account_type="channel_owner", status="connected", granted_scopes=["openid", "https://www.googleapis.com/auth/youtube.upload"])
        db.add(account); db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("youtube-access")))
        db.commit(); return str(account.id)


def test_youtube_upload_initializes_secure_resumable_session(client, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings
    get_settings.cache_clear()
    owner = register(client, "youtube-upload@example.com")
    account_id = add_youtube_account(session_factory, owner["organization"]["id"])
    calls = []
    class Response:
        headers = {"Location": "https://www.googleapis.com/upload/youtube/v3/videos?upload_id=secret-session"}
        def raise_for_status(self): pass
    def fake_post(url, **kwargs):
        calls.append(kwargs)
        return Response()
    monkeypatch.setattr("app.api.v1.youtube_publishing.httpx.post", fake_post)
    url = f"/api/v1/organizations/{owner['organization']['id']}/youtube/accounts/{account_id}/upload"
    body = {"video_size": 1024, "mime_type": "video/mp4", "title": "Demo video", "description": "Description", "tags": ["demo"], "privacy_status": "private", "made_for_kids": False, "consent_to_upload": False}
    assert client.post(url, json=body, headers=owner["headers"]).status_code == 400
    body["consent_to_upload"] = True
    result = client.post(url, json=body, headers=owner["headers"])
    assert result.status_code == 201, result.text
    assert result.json()["chunk_size"] == 8 * 1024 * 1024
    assert calls[0]["headers"]["X-Upload-Content-Length"] == "1024"
    assert calls[0]["json"]["status"]["privacyStatus"] == "private"
    activity = client.get(f"/api/v1/organizations/{owner['organization']['id']}/activity", headers=owner["headers"])
    assert activity.status_code == 200
    assert "youtube_publish_job.created" in [entry["action"] for entry in activity.json()]
    with session_factory() as db:
        job = db.query(YouTubePublishJob).one()
        assert job.status == "upload_pending"
        assert b"secret-session" not in job.upload_session_encrypted
    get_settings.cache_clear()


def test_youtube_status_only_marks_complete_after_provider_processing_succeeds(client, session_factory, monkeypatch):
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings
    get_settings.cache_clear()
    owner = register(client, "youtube-status@example.com")
    account_id = add_youtube_account(session_factory, owner["organization"]["id"])
    with session_factory() as db:
        job = YouTubePublishJob(organization_id=UUID(owner["organization"]["id"]), social_account_id=UUID(account_id), video_id="video123", upload_session_encrypted=encrypt_token("https://www.googleapis.com/upload/youtube/v3/videos?upload_id=x"), title="Test", description="", privacy_status="private", status="uploaded")
        db.add(job); db.commit(); job_id = str(job.id)
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"items": [{"id": "video123", "status": {"uploadStatus": "processed", "privacyStatus": "private"}, "processingDetails": {"processingStatus": "succeeded"}}]}
    monkeypatch.setattr("app.api.v1.youtube_publishing.httpx.get", lambda *a, **k: Response())
    url = f"/api/v1/organizations/{owner['organization']['id']}/youtube/publish-jobs/{job_id}"
    result = client.get(url, headers=owner["headers"])
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "published"
    assert result.json()["video_url"] == "https://www.youtube.com/watch?v=video123"
    activity = client.get(f"/api/v1/organizations/{owner['organization']['id']}/activity", headers=owner["headers"])
    assert activity.status_code == 200
    assert "youtube_publish_job.status_changed" in [entry["action"] for entry in activity.json()]
    get_settings.cache_clear()
