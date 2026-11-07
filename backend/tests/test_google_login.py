"""Google sign-in: callback validation, account creation, and refusal to link unverified password accounts."""

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.api.v1 import auth as auth_module
from app.models import AuthIdentity, User

PASSWORD = "StrongPass123!"


@pytest.fixture(autouse=True)
def google_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module._settings, "google_login_client_id", "test-client-id")
    monkeypatch.setattr(auth_module._settings, "google_login_client_secret", "test-client-secret")
    monkeypatch.setattr(auth_module._settings, "google_login_frontend_return_url", "http://localhost:3000/auth/callback")


def fake_google(monkeypatch: pytest.MonkeyPatch, *, sub: str = "google-sub-1", email: str = "new@example.com", name: str = "New Person"):
    claims = {"sub": sub, "email": email, "name": name, "email_verified": True}
    monkeypatch.setattr(auth_module, "_fetch_google_claims", lambda _code, _nonce: claims)


def start_and_callback(client: TestClient, **query: str):
    """Run /google (which sets the state cookies), then call the callback the way Google's redirect would."""
    start = client.get("/api/v1/auth/google", follow_redirects=False)
    assert start.status_code == 302
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    params = {"code": "auth-code", "state": state, **query}
    return client.get("/api/v1/auth/google/callback", params=params, follow_redirects=False)


def token_from(response) -> str:
    location = response.headers["location"]
    assert location.startswith("http://localhost:3000/auth/callback#"), location
    return parse_qs(urlsplit(location).fragment)["access_token"][0]


def test_start_redirects_to_google_with_state_and_nonce(client: TestClient) -> None:
    response = client.get("/api/v1/auth/google", follow_redirects=False)
    assert response.status_code == 302
    parsed = urlsplit(response.headers["location"])
    params = parse_qs(parsed.query)
    assert parsed.netloc == "accounts.google.com"
    assert params["scope"] == ["openid email profile"]
    assert params["state"] and params["nonce"]


def test_start_without_configuration_returns_to_login_instead_of_raw_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(auth_module._settings, "google_login_client_id", "")
    response = client.get("/api/v1/auth/google", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:3000/login?social_error=google_unavailable"


def test_first_google_sign_in_creates_account_and_workspace(
    client: TestClient, session_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_google(monkeypatch)
    response = start_and_callback(client)
    assert response.status_code == 302
    token = token_from(response)
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "new@example.com" and me["has_password"] is False
    orgs = client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"}).json()
    assert len(orgs) == 1 and orgs[0]["role"] == "owner"
    with session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None and user.email_verified_at is not None
        identity = db.scalar(select(AuthIdentity))
        assert identity is not None and identity.provider == "google" and identity.provider_subject == "google-sub-1"


def test_second_sign_in_reuses_the_account(client: TestClient, session_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_google(monkeypatch)
    first = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_from(start_and_callback(client))}"}).json()
    second = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_from(start_and_callback(client))}"}).json()
    assert first["id"] == second["id"]
    with session_factory() as db:
        assert len(db.scalars(select(User)).all()) == 1


def test_unverified_password_account_is_not_linked_to_google(
    client: TestClient, session_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Someone registered this email with a password; nobody has proven they own the address.
    client.post("/api/v1/auth/register", json={
        "email": "new@example.com", "password": PASSWORD, "full_name": "Registrant", "organization_name": "Their Studio",
    })
    fake_google(monkeypatch, email="new@example.com")
    response = start_and_callback(client)
    assert response.headers["location"] == "http://localhost:3000/login?social_error=email_exists"
    with session_factory() as db:
        assert db.scalar(select(AuthIdentity)) is None
    # The password account is untouched.
    login = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": PASSWORD})
    assert login.status_code == 200


def test_state_mismatch_and_provider_error_are_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_google(monkeypatch)
    bad_state = start_and_callback(client, state="not-the-real-state")
    assert bad_state.headers["location"] == "http://localhost:3000/login?social_error=google"
    denied = start_and_callback(client, error="access_denied")
    assert denied.headers["location"] == "http://localhost:3000/login?social_error=google"


def test_non_ascii_state_does_not_crash(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_google(monkeypatch)
    response = start_and_callback(client, state="état-€")
    assert response.status_code == 302
    assert response.headers["location"].endswith("social_error=google")


def test_token_verification_failure_returns_to_login(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module, "_fetch_google_claims", lambda _code, _nonce: None)
    assert start_and_callback(client).headers["location"].endswith("social_error=google")


def test_disabled_account_cannot_sign_in_with_google(client: TestClient, session_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_google(monkeypatch)
    token_from(start_and_callback(client))
    with session_factory() as db:
        user = db.scalar(select(User))
        user.is_active = False
        db.commit()
    assert start_and_callback(client).headers["location"].endswith("social_error=google")
