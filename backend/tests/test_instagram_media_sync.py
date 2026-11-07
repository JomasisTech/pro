from datetime import datetime, timezone
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.integrations.social_crypto import encrypt_token
from app.models import SocialAccount, SocialCredential, SocialPostObservation


def _register(client: TestClient, email: str) -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": "Sync Owner",
        "organization_name": "Sync Workspace",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def test_instagram_media_adapter_caps_results_and_normalizes_fields(monkeypatch):
    import app.integrations.instagram_media as adapter

    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [
                {"id": "post-1", "caption": "Hello #brand", "media_type": "IMAGE",
                 "permalink": "https://instagram.com/p/one", "timestamp": "2026-10-01T10:00:00+0000"},
                {"id": "post-2", "caption": None, "timestamp": "invalid"},
            ]}

    def fake_get(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(adapter.httpx, "get", fake_get)
    posts = adapter.fetch_recent_instagram_media("secret-token", limit=500)
    assert len(posts) == 2
    assert captured["params"]["limit"] == 20
    assert captured["headers"]["Authorization"] == "Bearer secret-token"
    assert posts[0]["post_text"] == "Hello #brand"
    assert posts[0]["published_at"].tzinfo is not None
    assert posts[1]["post_text"] == ""
    assert posts[1]["published_at"] is None


def test_instagram_sync_upserts_posts_and_is_tenant_scoped(client, session_factory, monkeypatch):
    import app.api.v1.brand_intelligence as brand_api
    from app.config import get_settings

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    owner = _register(client, "sync-owner@example.com")
    outsider = _register(client, "sync-outsider@example.com")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="instagram", provider_account_id="ig-123",
            account_name="@sync", status="connected", granted_scopes=["instagram_business_basic"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("test-token")))
        db.commit()
        account_id = str(account.id)

    monkeypatch.setattr(brand_api, "get_instagram_access_token", lambda db, account, credential: "test-token")
    monkeypatch.setattr(brand_api, "fetch_recent_instagram_media", lambda token, limit: [{
        "source_post_id": "ig-post-1", "post_text": "A real post", "permalink": "https://instagram.com/p/1",
        "published_at": datetime(2026, 10, 1, tzinfo=timezone.utc), "media_type": "IMAGE",
    }])
    endpoint = f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}"
    first = client.post(endpoint, headers=owner["headers"])
    assert first.status_code == 200, first.text
    assert first.json()["inserted"] == 1
    second = client.post(endpoint, headers=owner["headers"])
    assert second.status_code == 200, second.text
    assert second.json()["inserted"] == 0
    assert second.json()["updated"] == 1
    assert client.post(endpoint, headers=outsider["headers"]).status_code == 404
    with session_factory() as db:
        rows = db.query(SocialPostObservation).filter_by(social_account_id=UUID(account_id)).all()
        assert len(rows) == 1
        assert rows[0].provenance["method"] == "provider_api"


def test_tiktok_sync_requires_video_list_scope(client, session_factory):
    owner = _register(client, "sync-tiktok-owner@example.com")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(organization_id), provider="tiktok",
                                provider_account_id="tt-1", account_name="TikTok", status="connected",
                                granted_scopes=["user.info.basic", "video.publish"])
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=b"encrypted-token"))
        db.commit()
        account_id = str(account.id)
    response = client.post(
        f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}",
        headers=owner["headers"],
    )
    assert response.status_code == 409
    assert "video.list" in response.json()["detail"]
