from fastapi.testclient import TestClient


def registration_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "email": "owner@example.com",
        "password": "StrongPass123!",
        "full_name": "Test Owner",
        "organization_name": "Example Studio",
    }
    payload.update(overrides)
    return payload


def test_register_creates_user_organization_and_owner_membership(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=registration_payload())
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "owner@example.com"
    assert body["organization"]["name"] == "Example Studio"
    assert body["organization"]["role"] == "owner"
    assert body["access_token"]
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_register_normalizes_email_and_rejects_duplicate_account(client: TestClient) -> None:
    first = client.post("/api/v1/auth/register", json=registration_payload(email="Owner@Example.com"))
    second = client.post("/api/v1/auth/register", json=registration_payload())
    assert first.status_code == 201
    assert first.json()["user"]["email"] == "owner@example.com"
    assert second.status_code == 409


def test_register_rejects_short_password(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=registration_payload(password="short"))
    assert response.status_code == 422


def test_login_and_protected_me_endpoint(client: TestClient) -> None:
    registered = client.post("/api/v1/auth/register", json=registration_payload())
    assert registered.status_code == 201

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@example.com", "password": "StrongPass123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"


def test_login_rejects_invalid_password(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=registration_payload())
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_requires_a_valid_bearer_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
    ).status_code == 401


def test_login_is_temporarily_blocked_after_repeated_failures(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=registration_payload())
    bad = {"email": "owner@example.com", "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=bad).status_code == 401

    blocked = client.post("/api/v1/auth/login", json=bad)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0

    # Even the correct password is refused while the lockout is active.
    correct = {"email": "owner@example.com", "password": "StrongPass123!"}
    assert client.post("/api/v1/auth/login", json=correct).status_code == 429


def test_lockout_does_not_affect_other_accounts_and_success_resets_counter(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=registration_payload())
    client.post("/api/v1/auth/register", json=registration_payload(email="other@example.com"))
    bad = {"email": "owner@example.com", "password": "wrong-password"}
    for _ in range(4):
        client.post("/api/v1/auth/login", json=bad)

    correct = {"email": "owner@example.com", "password": "StrongPass123!"}
    assert client.post("/api/v1/auth/login", json=correct).status_code == 200  # counter reset
    for _ in range(4):
        client.post("/api/v1/auth/login", json=bad)
    assert client.post("/api/v1/auth/login", json=correct).status_code == 200

    other = {"email": "other@example.com", "password": "StrongPass123!"}
    for _ in range(5):
        client.post("/api/v1/auth/login", json={**other, "password": "nope-nope"})
    assert client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "StrongPass123!"}).status_code == 200


def test_unknown_email_still_spends_password_check_time(client: TestClient, monkeypatch) -> None:
    from app.api.v1 import auth as auth_module

    calls: list[str] = []
    monkeypatch.setattr(auth_module, "spend_password_check_time", lambda password: calls.append(password))
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
    assert calls == ["whatever-123"]


def test_per_address_limit_blocks_password_spraying_across_emails(client: TestClient, monkeypatch) -> None:
    from app.api.v1 import auth as auth_module
    from app.core.rate_limit import FailedAttemptLimiter

    monkeypatch.setattr(auth_module, "login_ip_limiter", FailedAttemptLimiter(3, 900))
    client.post("/api/v1/auth/register", json=registration_payload())
    for index in range(3):
        bad = {"email": f"user{index}@example.com", "password": "guess-guess"}
        assert client.post("/api/v1/auth/login", json=bad).status_code == 401

    # A fresh email from the same address is now refused, and a valid login does not clear the counter.
    sprayed = client.post("/api/v1/auth/login", json={"email": "user9@example.com", "password": "guess-guess"})
    assert sprayed.status_code == 429
    valid = client.post("/api/v1/auth/login", json={"email": "owner@example.com", "password": "StrongPass123!"})
    assert valid.status_code == 429
