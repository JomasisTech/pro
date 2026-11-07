from urllib.parse import parse_qs, urlparse
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.config import get_settings
from app.integrations.social_crypto import decrypt_token
from app.models import SocialAccount, SocialCredential


def _register(client: TestClient) -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": "oauth-owner@example.com", "password": "StrongPass123!",
        "full_name": "OAuth Owner", "organization_name": "OAuth Studio",
    })
    assert response.status_code == 201
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def _configure_meta(monkeypatch) -> None:
    monkeypatch.setenv("META_APP_ID", "test-app-id")
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("META_REDIRECT_URI", "http://testserver/api/v1/social-oauth/meta/instagram/callback")
    monkeypatch.setenv("META_FRONTEND_RETURN_URL", "http://localhost:3000/social-accounts/callback")
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()


def test_instagram_oauth_start_requires_configuration_and_admin(client: TestClient, monkeypatch) -> None:
    owner = _register(client)
    url = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/instagram/connect"
    assert client.post(url, headers=owner["headers"]).status_code == 503
    _configure_meta(monkeypatch)
    response = client.post(url, headers=owner["headers"])
    assert response.status_code == 200
    authorization_url = response.json()["authorization_url"]
    parsed = urlparse(authorization_url)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "www.instagram.com"
    assert params["scope"] == ["instagram_business_basic,instagram_business_content_publish"]
    assert params["state"][0]
    get_settings.cache_clear()


def test_instagram_oauth_callback_saves_encrypted_credential(client: TestClient, session_factory, monkeypatch) -> None:
    _configure_meta(monkeypatch)
    owner = _register(client)
    org_id = owner["organization"]["id"]
    start_url = f"/api/v1/organizations/{org_id}/social-accounts/instagram/connect"
    start = client.post(start_url, headers=owner["headers"])
    assert start.status_code == 200
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    class FakeResponse:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class FakeClient:
        def __init__(self, *args, **kwargs): self.calls = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data):
            assert url == "https://api.instagram.com/oauth/access_token"
            return FakeResponse({"access_token": "short-token"})
        def get(self, url, params):
            if url.endswith("/access_token"):
                return FakeResponse({"access_token": "long-lived-secret-token", "expires_in": 5184000})
            assert url == "https://graph.instagram.com/me"
            return FakeResponse({"user_id": "ig-987", "username": "bizpilot_demo", "account_type": "BUSINESS"})

    import app.api.v1.social_oauth as oauth_module
    monkeypatch.setattr(oauth_module.httpx, "Client", FakeClient)
    callback = client.get("/api/v1/social-oauth/meta/instagram/callback", params={"code": "one-time-code", "state": state}, follow_redirects=False)
    assert callback.status_code == 303
    assert "result=connected" in callback.headers["location"]

    with session_factory() as db:
        account = db.query(SocialAccount).filter_by(organization_id=UUID(org_id), provider="instagram").one()
        credential = db.query(SocialCredential).filter_by(social_account_id=account.id).one()
        assert account.account_name == "@bizpilot_demo"
        assert credential.access_token_encrypted != b"long-lived-secret-token"
        assert decrypt_token(credential.access_token_encrypted) == "long-lived-secret-token"
    get_settings.cache_clear()


def _configure_tiktok(monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "test-tiktok-key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "test-tiktok-secret")
    monkeypatch.setenv("TIKTOK_REDIRECT_URI", "http://testserver/api/v1/social-oauth/tiktok/callback")
    monkeypatch.setenv("TIKTOK_FRONTEND_RETURN_URL", "http://localhost:3000/social-accounts/callback")
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()


def test_tiktok_oauth_start_requires_configuration_and_admin(client: TestClient, monkeypatch) -> None:
    owner = _register(client)
    url = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/tiktok/connect"
    assert client.post(url, headers=owner["headers"]).status_code == 503
    _configure_tiktok(monkeypatch)
    response = client.post(url, headers=owner["headers"])
    assert response.status_code == 200
    parsed = urlparse(response.json()["authorization_url"])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "www.tiktok.com"
    assert params["client_key"] == ["test-tiktok-key"]
    assert "video.publish" in params["scope"][0]
    assert "video.list" in params["scope"][0]
    assert params["state"][0]
    get_settings.cache_clear()


def test_tiktok_oauth_callback_encrypts_tokens_and_is_one_time(client: TestClient, session_factory, monkeypatch) -> None:
    _configure_tiktok(monkeypatch)
    owner = _register(client)
    org_id = owner["organization"]["id"]
    start = client.post(f"/api/v1/organizations/{org_id}/social-accounts/tiktok/connect", headers=owner["headers"])
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    class FakeResponse:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data):
            assert url == "https://open.tiktokapis.com/v2/oauth/token/"
            return FakeResponse({"data": {
                "access_token": "tiktok-access-secret", "refresh_token": "tiktok-refresh-secret",
                "open_id": "tt-open-123", "expires_in": 86400,
                "refresh_expires_in": 31536000, "scope": "user.info.basic,video.list,video.publish",
            }})
        def get(self, url, params, headers):
            assert url == "https://open.tiktokapis.com/v2/user/info/"
            assert headers["Authorization"] == "Bearer tiktok-access-secret"
            return FakeResponse({"data": {"user": {"open_id": "tt-open-123", "display_name": "BizPilot Creator"}}})

    import app.api.v1.social_oauth as oauth_module
    monkeypatch.setattr(oauth_module.httpx, "Client", FakeClient)
    callback_url = "/api/v1/social-oauth/tiktok/callback"
    callback = client.get(callback_url, params={"code": "one-time-code", "state": state}, follow_redirects=False)
    assert callback.status_code == 303
    assert "provider=tiktok" in callback.headers["location"]
    assert "result=connected" in callback.headers["location"]
    replay = client.get(callback_url, params={"code": "one-time-code", "state": state}, follow_redirects=False)
    assert "result=invalid_state" in replay.headers["location"]

    with session_factory() as db:
        account = db.query(SocialAccount).filter_by(organization_id=UUID(org_id), provider="tiktok").one()
        credential = db.query(SocialCredential).filter_by(social_account_id=account.id).one()
        assert account.account_name == "BizPilot Creator"
        assert credential.access_token_encrypted != b"tiktok-access-secret"
        assert credential.refresh_token_encrypted != b"tiktok-refresh-secret"
        assert decrypt_token(credential.access_token_encrypted) == "tiktok-access-secret"
        assert decrypt_token(credential.refresh_token_encrypted) == "tiktok-refresh-secret"
    get_settings.cache_clear()


def _configure_youtube(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
    monkeypatch.setenv("YOUTUBE_REDIRECT_URI", "http://testserver/api/v1/social-oauth/youtube/callback")
    monkeypatch.setenv("YOUTUBE_FRONTEND_RETURN_URL", "http://localhost:3000/social-accounts/callback")
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()


def test_youtube_oauth_start_requests_upload_and_read_scopes_with_offline_access(client: TestClient, monkeypatch) -> None:
    owner = _register(client)
    url = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/youtube/connect"
    assert client.post(url, headers=owner["headers"]).status_code == 503
    _configure_youtube(monkeypatch)
    response = client.post(url, headers=owner["headers"])
    assert response.status_code == 200
    parsed = urlparse(response.json()["authorization_url"])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert "https://www.googleapis.com/auth/youtube.upload" in params["scope"][0]
    assert "https://www.googleapis.com/auth/youtube.readonly" in params["scope"][0]
    assert params["access_type"] == ["offline"]
    assert params["state"][0]
    get_settings.cache_clear()


def test_youtube_oauth_callback_saves_encrypted_tokens(client: TestClient, session_factory, monkeypatch) -> None:
    _configure_youtube(monkeypatch)
    owner = _register(client)
    org_id = owner["organization"]["id"]
    start = client.post(f"/api/v1/organizations/{org_id}/social-accounts/youtube/connect", headers=owner["headers"])
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    class FakeResponse:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data):
            assert url == "https://oauth2.googleapis.com/token"
            return FakeResponse({"access_token": "google-access-secret", "refresh_token": "google-refresh-secret", "expires_in": 3600, "scope": "openid email profile https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"})
        def get(self, url, headers):
            assert url == "https://openidconnect.googleapis.com/v1/userinfo"
            assert headers["Authorization"] == "Bearer google-access-secret"
            return FakeResponse({"sub": "google-sub-123", "name": "BizPilot Channel Owner", "email": "owner@example.com"})

    import app.api.v1.social_oauth as oauth_module
    monkeypatch.setattr(oauth_module.httpx, "Client", FakeClient)
    callback = client.get("/api/v1/social-oauth/youtube/callback", params={"code": "one-time-code", "state": state}, follow_redirects=False)
    assert callback.status_code == 303
    assert "provider=youtube" in callback.headers["location"]
    assert "result=connected" in callback.headers["location"]
    with session_factory() as db:
        account = db.query(SocialAccount).filter_by(organization_id=UUID(org_id), provider="youtube").one()
        credential = db.query(SocialCredential).filter_by(social_account_id=account.id).one()
        assert account.account_name == "BizPilot Channel Owner"
        assert "https://www.googleapis.com/auth/youtube.readonly" in account.granted_scopes
        assert "https://www.googleapis.com/auth/youtube.upload" in account.granted_scopes
        assert decrypt_token(credential.access_token_encrypted) == "google-access-secret"
        assert decrypt_token(credential.refresh_token_encrypted) == "google-refresh-secret"
    get_settings.cache_clear()


def _configure_facebook(monkeypatch) -> None:
    monkeypatch.setenv("META_APP_ID", "test-meta-app-id")
    monkeypatch.setenv("META_APP_SECRET", "test-meta-app-secret")
    monkeypatch.setenv("FACEBOOK_REDIRECT_URI", "http://testserver/api/v1/social-oauth/facebook/callback")
    monkeypatch.setenv("FACEBOOK_FRONTEND_RETURN_URL", "http://localhost:3000/social-accounts/callback")
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()


def test_facebook_oauth_start_requests_page_permissions(client: TestClient, monkeypatch) -> None:
    owner = _register(client)
    url = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/facebook/connect"
    assert client.post(url, headers=owner["headers"]).status_code == 503
    _configure_facebook(monkeypatch)
    response = client.post(url, headers=owner["headers"])
    assert response.status_code == 200
    params = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert urlparse(response.json()["authorization_url"]).netloc == "www.facebook.com"
    assert set(params["scope"][0].split(",")) == {"pages_show_list", "pages_read_engagement", "pages_manage_posts"}
    assert params["state"][0]
    get_settings.cache_clear()


def test_facebook_oauth_callback_discovers_pages_and_encrypts_page_tokens(client: TestClient, session_factory, monkeypatch) -> None:
    _configure_facebook(monkeypatch)
    owner = _register(client)
    start = client.post(f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/facebook/connect", headers=owner["headers"])
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    class FakeResponse:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class FakeClient:
        def __init__(self, *args, **kwargs): self.exchange = 0; self.page_calls = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url, params):
            if url.endswith("/oauth/access_token"):
                self.exchange += 1
                return FakeResponse({"access_token": "short-user-token"} if self.exchange == 1 else {"access_token": "long-user-token"})
            assert url.endswith("/me/accounts")
            assert params["access_token"] == "long-user-token"
            self.page_calls += 1
            if self.page_calls == 1:
                return FakeResponse({
                    "data": [{"id": "page-555", "name": "BizPilot Page", "access_token": "page-secret-token", "tasks": ["CREATE_CONTENT", "ANALYZE"]}],
                    "paging": {"next": "https://graph.facebook.com/next", "cursors": {"after": "cursor-2"}},
                })
            assert params["after"] == "cursor-2"
            return FakeResponse({"data": [{"id": "page-556", "name": "Second Page", "access_token": "second-page-token", "tasks": ["CREATE_CONTENT"]}]})

    import app.api.v1.facebook_oauth as facebook_module
    monkeypatch.setattr(facebook_module.httpx, "Client", FakeClient)
    callback = client.get("/api/v1/social-oauth/facebook/callback", params={"code": "oauth-code", "state": state}, follow_redirects=False)
    assert callback.status_code == 303
    assert "provider=facebook" in callback.headers["location"]
    assert "result=connected" in callback.headers["location"]
    with session_factory() as db:
        accounts = db.query(SocialAccount).filter_by(organization_id=UUID(owner["organization"]["id"]), provider="facebook").all()
        assert {account.account_name for account in accounts} == {"BizPilot Page", "Second Page"}
        account = next(account for account in accounts if account.account_name == "BizPilot Page")
        credential = db.query(SocialCredential).filter_by(social_account_id=account.id).one()
        assert decrypt_token(credential.access_token_encrypted) == "page-secret-token"
    activity = client.get(f"/api/v1/organizations/{owner['organization']['id']}/activity", headers=owner["headers"])
    assert activity.status_code == 200
    assert "social_account.connected" in [entry["action"] for entry in activity.json()]
    get_settings.cache_clear()


def test_facebook_oauth_does_not_report_connected_without_publishable_page(client: TestClient, monkeypatch) -> None:
    _configure_facebook(monkeypatch)
    owner = _register(client)
    start = client.post(f"/api/v1/organizations/{owner['organization']['id']}/social-accounts/facebook/connect", headers=owner["headers"])
    state = parse_qs(urlparse(start.json()["authorization_url"]).query)["state"][0]

    class FakeResponse:
        def __init__(self, body): self.body = body
        def raise_for_status(self): return None
        def json(self): return self.body

    class FakeClient:
        def __init__(self, *args, **kwargs): self.exchange = 0
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url, params):
            if url.endswith("/oauth/access_token"):
                self.exchange += 1
                return FakeResponse({"access_token": "short-token"} if self.exchange == 1 else {"access_token": "long-token"})
            return FakeResponse({"data": [{"id": "page-read-only", "name": "Read Only", "access_token": "page-token", "tasks": ["ANALYZE"]}]})

    import app.api.v1.facebook_oauth as facebook_module
    monkeypatch.setattr(facebook_module.httpx, "Client", FakeClient)
    callback = client.get("/api/v1/social-oauth/facebook/callback", params={"code": "oauth-code", "state": state}, follow_redirects=False)
    assert "result=no_eligible_pages" in callback.headers["location"]
    accounts = client.get(f"/api/v1/organizations/{owner['organization']['id']}/social-accounts", headers=owner["headers"])
    assert accounts.status_code == 200 and accounts.json() == []
    get_settings.cache_clear()
