"""Logout, sign-out-everywhere, change password, and password reset."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import PasswordResetToken, User

PASSWORD = "StrongPass123!"
NEW_PASSWORD = "BrandNewPass456!"


@pytest.fixture()
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Capture outgoing email instead of sending it."""
    sent: list[dict[str, str]] = []

    def fake_send(_settings: object, to_address: str, subject: str, body: str) -> bool:
        sent.append({"to": to_address, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("app.api.v1.auth.send_email", fake_send)
    return sent


def register(client: TestClient, email: str = "owner@example.com") -> str:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Test Owner", "organization_name": "Example Studio"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def login(client: TestClient, password: str = PASSWORD, email: str = "owner@example.com"):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def reset_token_from(outbox: list[dict[str, str]]) -> str:
    body = outbox[-1]["body"]
    assert "/reset-password#token=" in body
    return body.split("#token=", 1)[1].split()[0]


# ---- logout -----------------------------------------------------------------------------------


def test_logout_revokes_only_the_presented_token(client: TestClient) -> None:
    first = register(client)
    second = login(client).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth(first)).status_code == 200

    response = client.post("/api/v1/auth/logout", headers=auth(first))
    assert response.status_code == 200

    assert client.get("/api/v1/auth/me", headers=auth(first)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth(second)).status_code == 200


def test_logout_requires_authentication_and_cannot_repeat(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout").status_code == 401
    token = register(client)
    assert client.post("/api/v1/auth/logout", headers=auth(token)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth(token)).status_code == 401


def test_logout_all_ends_every_session(client: TestClient) -> None:
    first = register(client)
    second = login(client).json()["access_token"]
    assert client.post("/api/v1/auth/logout-all", headers=auth(first)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(first)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth(second)).status_code == 401
    # A fresh sign-in works again.
    fresh = login(client).json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth(fresh)).status_code == 200


def test_token_without_jti_or_version_still_works_and_logout_ends_it(client: TestClient) -> None:
    register(client)
    me_id = client.get("/api/v1/auth/me", headers=auth(login(client).json()["access_token"])).json()["id"]
    settings = get_settings()
    now = datetime.now(timezone.utc)
    legacy = jwt.encode(
        {"sub": me_id, "iat": now, "exp": now + timedelta(minutes=5), "type": "access"},
        settings.secret_key,
        algorithm="HS256",
    )
    assert client.get("/api/v1/auth/me", headers=auth(legacy)).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth(legacy)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(legacy)).status_code == 401


# ---- change password --------------------------------------------------------------------------


def test_change_password_switches_password_and_ends_other_sessions(client: TestClient, outbox: list[dict[str, str]]) -> None:
    old_token = register(client)
    other = login(client).json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth(old_token),
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 200, response.text
    new_token = response.json()["access_token"]

    assert client.get("/api/v1/auth/me", headers=auth(new_token)).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth(other)).status_code == 401
    assert login(client, PASSWORD).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200
    assert outbox and outbox[-1]["to"] == "owner@example.com"


def test_change_password_rejects_wrong_current_and_unchanged_password(client: TestClient) -> None:
    token = register(client)
    wrong = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": "not-my-password", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 400
    same = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": PASSWORD},
    )
    assert same.status_code == 400
    short = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert short.status_code == 422
    assert login(client, PASSWORD).status_code == 200


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/change-password", json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 401


def test_change_password_locks_out_repeated_wrong_guesses(client: TestClient) -> None:
    token = register(client)
    payload = {"current_password": "wrong-guess-1", "new_password": NEW_PASSWORD}
    for _ in range(get_settings().login_max_failed_attempts):
        assert client.post("/api/v1/auth/change-password", headers=auth(token), json=payload).status_code == 400
    blocked = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


# ---- forgot / reset password -----------------------------------------------------------------


def test_forgot_password_answers_identically_for_known_and_unknown_emails(
    client: TestClient, outbox: list[dict[str, str]]
) -> None:
    register(client)
    # Registration emits a separate email-verification message; isolate reset-mail assertions.
    outbox.clear()
    known = client.post("/api/v1/auth/forgot-password", json={"email": "Owner@Example.com"})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert [mail["to"] for mail in outbox] == ["owner@example.com"]


def test_reset_password_full_flow(client: TestClient, outbox: list[dict[str, str]]) -> None:
    old_token = register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    token = reset_token_from(outbox)

    response = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 200, response.text

    assert login(client, PASSWORD).status_code == 401
    assert login(client, NEW_PASSWORD).status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(old_token)).status_code == 401
    # The confirmation email goes out after the reset link email.
    assert "password was changed" in outbox[-1]["subject"]


def test_reset_token_is_single_use(client: TestClient, outbox: list[dict[str, str]]) -> None:
    register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    token = reset_token_from(outbox)
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200
    again = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "AnotherPass789!"})
    assert again.status_code == 400
    assert login(client, NEW_PASSWORD).status_code == 200


def test_newer_reset_link_replaces_older_one(client: TestClient, outbox: list[dict[str, str]]) -> None:
    register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    first = reset_token_from(outbox)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    second = reset_token_from(outbox)
    assert first != second
    assert client.post("/api/v1/auth/reset-password", json={"token": first, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/api/v1/auth/reset-password", json={"token": second, "new_password": NEW_PASSWORD}).status_code == 200


def test_expired_reset_token_is_rejected(
    client: TestClient, outbox: list[dict[str, str]], session_factory: sessionmaker
) -> None:
    register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    token = reset_token_from(outbox)
    with session_factory() as db:
        db.execute(update(PasswordResetToken).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    response = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert response.status_code == 400
    assert login(client, PASSWORD).status_code == 200


def test_reset_token_is_stored_only_as_a_hash(
    client: TestClient, outbox: list[dict[str, str]], session_factory: sessionmaker
) -> None:
    register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    token = reset_token_from(outbox)
    with session_factory() as db:
        stored = db.scalars(select(PasswordResetToken.token_hash)).all()
    assert len(stored) == 1 and stored[0] != token and token not in stored[0]


def test_reset_password_rejects_garbage_and_weak_input(client: TestClient, outbox: list[dict[str, str]]) -> None:
    register(client)
    bad = client.post("/api/v1/auth/reset-password", json={"token": "x" * 43, "new_password": NEW_PASSWORD})
    assert bad.status_code == 400
    too_short_token = client.post("/api/v1/auth/reset-password", json={"token": "abc", "new_password": NEW_PASSWORD})
    assert too_short_token.status_code == 422
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    token = reset_token_from(outbox)
    weak = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422
    # A rejected weak password must not consume the token.
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 200


def test_disabled_account_gets_no_reset_email_and_same_response(
    client: TestClient, outbox: list[dict[str, str]], session_factory: sessionmaker
) -> None:
    register(client)
    outbox.clear()
    with session_factory() as db:
        db.execute(update(User).values(is_active=False))
        db.commit()
    response = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    assert response.status_code == 202
    assert outbox == []


def test_password_change_invalidates_outstanding_reset_link(client: TestClient, outbox: list[dict[str, str]]) -> None:
    token = register(client)
    client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    reset = reset_token_from(outbox)
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={"token": reset, "new_password": "AnotherPass789!"}).status_code == 400


def test_forgot_password_is_rate_limited_per_email(client: TestClient, outbox: list[dict[str, str]]) -> None:
    register(client)
    outbox.clear()
    limit = get_settings().password_reset_max_requests
    for _ in range(limit):
        assert client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"}).status_code == 202
    blocked = client.post("/api/v1/auth/forgot-password", json={"email": "owner@example.com"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert len(outbox) == limit
