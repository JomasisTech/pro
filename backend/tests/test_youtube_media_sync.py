from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.integrations.youtube_media import YouTubeMediaError, fetch_recent_youtube_videos


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_youtube_adapter_reads_uploads_playlist_and_caps_at_twenty(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/channels"):
                return FakeResponse({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "uploads-1"}}}]})
            return FakeResponse({"items": [
                {"snippet": {"resourceId": {"videoId": "video-1"}, "title": "A useful title",
                              "description": "A video description", "publishedAt": "2026-10-01T10:00:00Z"}},
                {"contentDetails": {"videoId": "video-2"}, "snippet": {"title": "Second", "publishedAt": "invalid"}},
            ]})

    monkeypatch.setattr("app.integrations.youtube_media.httpx.Client", FakeClient)
    videos = fetch_recent_youtube_videos("google-access-token", limit=500)
    assert len(videos) == 2
    assert calls[0][1]["params"] == {"part": "contentDetails", "mine": "true"}
    assert calls[1][1]["params"]["playlistId"] == "uploads-1"
    assert calls[1][1]["params"]["maxResults"] == 20
    assert calls[0][1]["headers"]["Authorization"] == "Bearer google-access-token"
    assert videos[0]["source_post_id"] == "video-1"
    assert videos[0]["post_text"] == "A useful title\n\nA video description"
    assert videos[0]["permalink"] == "https://www.youtube.com/watch?v=video-1"
    assert videos[0]["published_at"].tzinfo == timezone.utc
    assert videos[1]["published_at"] is None


def test_youtube_adapter_rejects_missing_channel_and_hides_provider_errors(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs): return FakeResponse({"items": []})

    monkeypatch.setattr("app.integrations.youtube_media.httpx.Client", FakeClient)
    with pytest.raises(YouTubeMediaError, match="No YouTube channel"):
        fetch_recent_youtube_videos("token")
    with pytest.raises(YouTubeMediaError):
        fetch_recent_youtube_videos("")


def test_youtube_brand_sync_requires_read_scope_and_upserts(client, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.models import SocialAccount, SocialCredential, SocialPostObservation
    import app.api.v1.brand_intelligence as brand_api
    from app.api.v1.youtube_publishing import _account_token

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    registered = client.post("/api/v1/auth/register", json={
        "email": "youtube-sync@example.com", "password": "StrongPass123!",
        "full_name": "YouTube Owner", "organization_name": "YouTube Workspace",
    })
    assert registered.status_code == 201, registered.text
    auth = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    organization_id = registered.json()["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="youtube", provider_account_id="google-subject",
            account_name="YouTube Channel", status="connected",
            granted_scopes=["openid", "https://www.googleapis.com/auth/youtube.upload",
                            "https://www.googleapis.com/auth/youtube.readonly"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("youtube-token")))
        db.commit()
        account_id = str(account.id)

    calls = []
    monkeypatch.setattr(brand_api, "fetch_recent_youtube_videos", lambda token, limit: calls.append((token, limit)) or [{
        "source_post_id": "yt-video-1", "post_text": "A YouTube video", "permalink": "https://www.youtube.com/watch?v=yt-video-1",
        "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc), "media_type": "video",
    }])
    monkeypatch.setattr("app.api.v1.youtube_publishing._account_token", lambda db, org_id, acc_id: (object(), "fresh-youtube-token"))
    endpoint = f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}"
    first = client.post(endpoint, headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 1
    second = client.post(endpoint, headers=auth)
    assert second.status_code == 200, second.text
    assert second.json()["inserted"] == 0
    assert second.json()["updated"] == 1
    assert calls == [("fresh-youtube-token", 20), ("fresh-youtube-token", 20)]
    with session_factory() as db:
        rows = db.query(SocialPostObservation).filter_by(social_account_id=UUID(account_id)).all()
        assert len(rows) == 1
        assert rows[0].provider == "youtube"
        assert rows[0].provenance["method"] == "provider_api"


def test_youtube_brand_sync_requires_readonly_scope(client, session_factory):
    from uuid import UUID
    from app.models import SocialAccount, SocialCredential

    registered = client.post("/api/v1/auth/register", json={
        "email": "youtube-scope@example.com", "password": "StrongPass123!",
        "full_name": "YouTube Owner", "organization_name": "YouTube Workspace",
    })
    assert registered.status_code == 201, registered.text
    auth = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    organization_id = registered.json()["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="youtube", provider_account_id="google-subject",
            account_name="YouTube Channel", status="connected", granted_scopes=["youtube.upload"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=b"encrypted"))
        db.commit()
        account_id = str(account.id)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}", headers=auth,
    )
    assert response.status_code == 409
    assert "youtube.readonly" in response.json()["detail"]
