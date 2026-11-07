from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import create_access_token, hash_password
from app.models import Membership, Organization, User

URL = "/api/v1/auth/set-credentials"


def social_user(session_factory: sessionmaker, *, email: str | None = None, has_password: bool = False) -> dict:
    """A user who signed in with WhatsApp (no email) or Google (email, no password)."""
    with session_factory() as db:
        user = User(
            email=email, full_name="Ada Social", password_hash=hash_password("unused-random-value-123"),
            has_password=has_password,
        )
        db.add(Membership(user=user, organization=Organization(name="Ada Shop", slug=f"ada-shop-{email or 'wa'}"), role="owner"))
        db.commit()
        token = create_access_token(user.id, user.token_version)
    return {"Authorization": f"Bearer {token}"}


def test_whatsapp_account_can_add_email_and_password(client: TestClient, session_factory: sessionmaker) -> None:
    headers = social_user(session_factory)
    response = client.post(URL, headers=headers, json={"email": "Ada@Example.com", "password": "StrongPass123!"})
    assert response.status_code == 200, response.text
    user = response.json()["user"]
    assert user["email"] == "ada@example.com" and user["has_password"] is True and user["email_verified_at"] is None
    # The new session works, and the new credentials can sign in.
    new_headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=new_headers).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "StrongPass123!"}).status_code == 200
    # The old token no longer works (all other sessions end).
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_google_account_can_add_a_password_without_an_email(client: TestClient, session_factory: sessionmaker) -> None:
    headers = social_user(session_factory, email="grace@example.com")
    response = client.post(URL, headers=headers, json={"password": "StrongPass123!"})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["has_password"] is True


def test_email_is_required_when_the_account_has_none(client: TestClient, session_factory: sessionmaker) -> None:
    headers = social_user(session_factory)
    assert client.post(URL, headers=headers, json={"password": "StrongPass123!"}).status_code == 400


def test_existing_email_is_refused_without_saying_whose_it_is(client: TestClient, session_factory: sessionmaker) -> None:
    client.post("/api/v1/auth/register", json={
        "email": "taken@example.com", "password": "StrongPass123!", "full_name": "Taken", "organization_name": "Taken Co",
    })
    headers = social_user(session_factory)
    response = client.post(URL, headers=headers, json={"email": "taken@example.com", "password": "StrongPass123!"})
    assert response.status_code == 409 and "taken@example.com" not in response.text


def test_accounts_with_a_password_must_use_change_password(client: TestClient, session_factory: sessionmaker) -> None:
    headers = social_user(session_factory, email="has@example.com", has_password=True)
    assert client.post(URL, headers=headers, json={"password": "StrongPass123!"}).status_code == 400


def test_a_different_email_cannot_replace_the_existing_one(client: TestClient, session_factory: sessionmaker) -> None:
    headers = social_user(session_factory, email="grace2@example.com")
    response = client.post(URL, headers=headers, json={"email": "other@example.com", "password": "StrongPass123!"})
    assert response.status_code == 400


def test_requires_authentication(client: TestClient) -> None:
    assert client.post(URL, json={"password": "StrongPass123!"}).status_code == 401
