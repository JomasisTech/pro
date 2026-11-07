from datetime import datetime, timezone

import httpx
import pytest

from app.integrations.tiktok_media import TikTokMediaError, fetch_recent_tiktok_videos


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_fetch_recent_tiktok_videos_normalizes_and_caps(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            captured.update(url=url, **kwargs)
            return FakeResponse({"error": {"code": "ok"}, "data": {"videos": [
                {"id": "video-1", "video_description": "A TikTok video", "title": "Title",
                 "create_time": 1791115200, "share_url": "https://www.tiktok.com/@creator/video/1"},
                {"id": "video-2", "title": "Second video", "create_time": "invalid"},
            ]}})

    monkeypatch.setattr("app.integrations.tiktok_media.httpx.Client", FakeClient)
    videos = fetch_recent_tiktok_videos("secret-token", limit=200)
    assert captured["url"].endswith("/v2/video/list/")
    assert captured["json"] == {"max_count": 20}
    assert captured["params"]["fields"]
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert videos[0]["source_post_id"] == "video-1"
    assert videos[0]["post_text"] == "A TikTok video"
    assert videos[0]["permalink"].startswith("https://www.tiktok.com/")
    assert videos[0]["published_at"].tzinfo == timezone.utc
    assert videos[1]["post_text"] == "Second video"
    assert videos[1]["published_at"] is None


def test_fetch_recent_tiktok_videos_hides_provider_error(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs):
            return FakeResponse({"error": {"code": "scope_not_authorized", "message": "secret-token"}})

    monkeypatch.setattr("app.integrations.tiktok_media.httpx.Client", FakeClient)
    with pytest.raises(TikTokMediaError) as exc:
        fetch_recent_tiktok_videos("secret-token")
    assert "secret-token" not in str(exc.value)


def test_fetch_recent_tiktok_videos_rejects_missing_token():
    with pytest.raises(TikTokMediaError):
        fetch_recent_tiktok_videos("")


def test_tiktok_brand_sync_requires_read_scope_and_upserts(client, session_factory, monkeypatch):
    from uuid import UUID
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.models import SocialAccount, SocialCredential, SocialPostObservation
    import app.api.v1.brand_intelligence as brand_api

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    registered = client.post("/api/v1/auth/register", json={
        "email": "tiktok-sync@example.com", "password": "StrongPass123!",
        "full_name": "TikTok Owner", "organization_name": "TikTok Workspace",
    })
    assert registered.status_code == 201, registered.text
    auth = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    organization_id = registered.json()["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="tiktok", provider_account_id="tt-user",
            account_name="TikTok Creator", status="connected", granted_scopes=["user.info.basic", "video.list"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("tiktok-token")))
        db.commit()
        account_id = str(account.id)

    calls = []
    def fake_fetch(token, limit):
        calls.append((token, limit))
        return [{"source_post_id": "tt-video-1", "post_text": "A creator video", "permalink": "https://tiktok.com/video/1",
                 "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc), "media_type": "video"}]

    monkeypatch.setattr(brand_api, "fetch_recent_tiktok_videos", fake_fetch)
    endpoint = f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}"
    first = client.post(endpoint, headers=auth)
    assert first.status_code == 200, first.text
    assert first.json()["provider"] == "tiktok"
    assert first.json()["inserted"] == 1
    second = client.post(endpoint, headers=auth)
    assert second.status_code == 200, second.text
    assert second.json()["inserted"] == 0
    assert second.json()["updated"] == 1
    assert calls == [("tiktok-token", 20), ("tiktok-token", 20)]
    with session_factory() as db:
        rows = db.query(SocialPostObservation).filter_by(social_account_id=UUID(account_id)).all()
        assert len(rows) == 1
        assert rows[0].provider == "tiktok"
        assert rows[0].provenance["method"] == "provider_api"


def test_tiktok_brand_sync_requires_video_list_scope(client, session_factory, monkeypatch):
    from uuid import UUID
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.models import SocialAccount, SocialCredential

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    registered = client.post("/api/v1/auth/register", json={
        "email": "tiktok-scope@example.com", "password": "StrongPass123!",
        "full_name": "TikTok Owner", "organization_name": "TikTok Workspace",
    })
    assert registered.status_code == 201, registered.text
    auth = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    organization_id = registered.json()["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="tiktok", provider_account_id="tt-user",
            account_name="TikTok Creator", status="connected", granted_scopes=["user.info.basic", "video.publish"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("tiktok-token")))
        db.commit()
        account_id = str(account.id)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}", headers=auth,
    )
    assert response.status_code == 409
    assert "video.list" in response.json()["detail"]


def test_tiktok_token_helper_refreshes_and_rotates_credentials(monkeypatch):
    from datetime import timedelta
    from types import SimpleNamespace
    from app.integrations import tiktok_tokens
    from app.config import get_settings

    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "client-key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "client-secret")
    get_settings.cache_clear()
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    account = SimpleNamespace(provider="tiktok", token_expires_at=now + timedelta(minutes=2))
    credential = SimpleNamespace(access_token_encrypted=b"old", refresh_token_encrypted=b"refresh")
    class FakeDB:
        committed = False
        def commit(self): self.committed = True
    db = FakeDB()
    monkeypatch.setattr(tiktok_tokens, "decrypt_token", lambda value: "refresh-secret" if value == b"refresh" else "old-token")
    monkeypatch.setattr(tiktok_tokens, "encrypt_token", lambda value: f"encrypted:{value}".encode())

    class Response:
        def raise_for_status(self): return None
        def json(self): return {"data": {"access_token": "new-token", "refresh_token": "rotated-refresh", "expires_in": 86400}}

    def fake_post(url, **kwargs):
        assert url == "https://open.tiktokapis.com/v2/oauth/token/"
        assert kwargs["data"]["refresh_token"] == "refresh-secret"
        return Response()

    monkeypatch.setattr(tiktok_tokens.httpx, "post", fake_post)
    token = tiktok_tokens.get_tiktok_access_token(db, account, credential, now=now)
    assert token == "new-token"
    assert credential.access_token_encrypted == b"encrypted:new-token"
    assert credential.refresh_token_encrypted == b"encrypted:rotated-refresh"
    assert account.token_expires_at == now + timedelta(seconds=86400)
    assert db.committed is True
    get_settings.cache_clear()


def test_tiktok_token_helper_requires_reconnect_when_expired_without_refresh():
    from datetime import timedelta
    from types import SimpleNamespace
    from app.integrations.tiktok_tokens import get_tiktok_access_token
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    account = SimpleNamespace(provider="tiktok", token_expires_at=now - timedelta(seconds=1))
    credential = SimpleNamespace(access_token_encrypted=b"old", refresh_token_encrypted=None)
    with pytest.raises(RuntimeError, match="reconnect"):
        get_tiktok_access_token(None, account, credential, now=now)
