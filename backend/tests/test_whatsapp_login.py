"""WhatsApp one-time-code sign-in and the /auth/providers capability endpoint."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.api.v1 import auth as auth_module
from app.models import AuthIdentity, PhoneLoginCode, User

PHONE = "+2348012345678"


@pytest.fixture()
def sent(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, str]]:
    """Capture WhatsApp messages instead of calling Meta."""
    messages: list[dict[str, str]] = []

    def fake_send(_settings: object, phone: str, code: str) -> bool:
        messages.append({"phone": phone, "code": code})
        return True

    monkeypatch.setattr(auth_module, "send_login_code", fake_send)
    return messages


def request_code(client: TestClient, phone: str = PHONE):
    return client.post("/api/v1/auth/whatsapp/request-code", json={"phone": phone})


def verify(client: TestClient, code: str, phone: str = PHONE, full_name: str | None = None):
    body = {"phone": phone, "code": code}
    if full_name is not None:
        body["full_name"] = full_name
    return client.post("/api/v1/auth/whatsapp/verify", json=body)


def expire_resend_cooldown(session_factory: sessionmaker) -> None:
    """Make existing codes look old enough that another one may be requested."""
    with session_factory() as db:
        db.execute(update(PhoneLoginCode).values(created_at=datetime.now(timezone.utc) - timedelta(minutes=5)))
        db.commit()


def test_providers_reflect_configuration(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_module._settings, "google_login_client_id", "")
    monkeypatch.setattr(auth_module._settings, "whatsapp_access_token", "")
    monkeypatch.setattr(auth_module._settings, "app_env", "production")
    assert client.get("/api/v1/auth/providers").json() == {"google": False, "whatsapp": False}

    monkeypatch.setattr(auth_module._settings, "google_login_client_id", "id")
    monkeypatch.setattr(auth_module._settings, "google_login_client_secret", "secret")
    monkeypatch.setattr(auth_module._settings, "whatsapp_access_token", "token")
    monkeypatch.setattr(auth_module._settings, "whatsapp_phone_number_id", "123")
    monkeypatch.setattr(auth_module._settings, "whatsapp_otp_template_name", "login_code")
    assert client.get("/api/v1/auth/providers").json() == {"google": True, "whatsapp": True}


def test_request_code_is_refused_when_whatsapp_is_not_configured_in_production(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, sent: list[dict[str, str]]
) -> None:
    monkeypatch.setattr(auth_module._settings, "whatsapp_access_token", "")
    monkeypatch.setattr(auth_module._settings, "app_env", "production")
    assert request_code(client).status_code == 503
    assert sent == []


def test_code_is_sent_normalised_and_stored_only_as_a_hash(
    client: TestClient, session_factory: sessionmaker, sent: list[dict[str, str]]
) -> None:
    response = request_code(client, "+234 (801) 234-5678")
    assert response.status_code == 202
    assert len(sent) == 1 and sent[0]["phone"] == PHONE
    code = sent[0]["code"]
    assert len(code) == 6 and code.isdigit()
    with session_factory() as db:
        record = db.scalar(select(PhoneLoginCode))
        assert record is not None and record.phone_e164 == PHONE
        assert code not in record.code_hash and record.code_hash != code


@pytest.mark.parametrize("phone", ["08012345678", "+0123456789", "+12", "+234abc12345", "not a number", "+1234567890123456"])
def test_invalid_phone_numbers_are_rejected(client: TestClient, sent: list[dict[str, str]], phone: str) -> None:
    assert request_code(client, phone).status_code == 422
    assert sent == []


def test_new_number_creates_an_account_with_a_workspace(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    response = verify(client, sent[0]["code"], full_name="Ada Okafor")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] is None
    assert body["user"]["has_password"] is False
    assert body["user"]["full_name"] == "Ada Okafor"
    assert body["organization"]["role"] == "owner"
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] is None


def test_new_number_without_a_name_gets_a_placeholder(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    body = verify(client, sent[0]["code"]).json()
    assert body["user"]["full_name"] == "WhatsApp user"


def test_same_number_signs_in_to_the_same_account(
    client: TestClient, session_factory: sessionmaker, sent: list[dict[str, str]]
) -> None:
    request_code(client)
    first = verify(client, sent[0]["code"], full_name="Ada").json()
    expire_resend_cooldown(session_factory)
    request_code(client)
    second = verify(client, sent[1]["code"], full_name="Someone Else").json()
    assert second["user"]["id"] == first["user"]["id"]
    assert second["user"]["full_name"] == "Ada"  # an existing account keeps its name
    with session_factory() as db:
        assert len(db.scalars(select(User)).all()) == 1
        assert len(db.scalars(select(AuthIdentity).where(AuthIdentity.provider == "whatsapp")).all()) == 1


def test_a_code_works_only_once(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    code = sent[0]["code"]
    assert verify(client, code).status_code == 200
    assert verify(client, code).status_code == 400


def test_wrong_code_is_rejected_and_attempts_are_limited(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    real = sent[0]["code"]
    wrong = "000000" if real != "000000" else "111111"
    for _ in range(auth_module._settings.whatsapp_login_max_verify_attempts):
        assert verify(client, wrong).status_code == 400
    # After too many wrong guesses even the right code is refused; a new code must be requested.
    assert verify(client, real).status_code == 400


def test_expired_code_is_rejected(client: TestClient, session_factory: sessionmaker, sent: list[dict[str, str]]) -> None:
    request_code(client)
    with session_factory() as db:
        db.execute(update(PhoneLoginCode).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert verify(client, sent[0]["code"]).status_code == 400


def test_code_for_a_different_number_is_rejected(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    assert verify(client, sent[0]["code"], phone="+2348099999999").status_code == 400


def test_a_new_request_replaces_the_previous_code(
    client: TestClient, session_factory: sessionmaker, sent: list[dict[str, str]]
) -> None:
    request_code(client)
    expire_resend_cooldown(session_factory)
    request_code(client)
    old, new = sent[0]["code"], sent[1]["code"]
    if old != new:
        assert verify(client, old).status_code == 400
    # (the failed guess above used one attempt of the new code, which still has plenty left)
    assert verify(client, new).status_code == 200


def test_resend_cooldown_and_hourly_limit(
    client: TestClient, session_factory: sessionmaker, sent: list[dict[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert request_code(client).status_code == 202
    again = request_code(client)
    assert again.status_code == 429 and "Retry-After" in again.headers
    assert len(sent) == 1

    monkeypatch.setattr(auth_module._settings, "whatsapp_login_max_codes_per_hour", 2)
    expire_resend_cooldown(session_factory)
    assert request_code(client).status_code == 202
    expire_resend_cooldown(session_factory)
    assert request_code(client).status_code == 429


def test_whatsapp_account_cannot_change_a_password_it_does_not_have(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    token = verify(client, sent[0]["code"]).json()["access_token"]
    response = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "anything-at-all", "new_password": "BrandNewPass456!"},
    )
    assert response.status_code == 400 and "no password" in response.json()["detail"]


def test_account_without_email_can_be_listed_as_a_member(client: TestClient, sent: list[dict[str, str]]) -> None:
    request_code(client)
    body = verify(client, sent[0]["code"], full_name="Ada").json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    members = client.get(f"/api/v1/organizations/{body['organization']['id']}/members", headers=headers)
    assert members.status_code == 200
    assert members.json()[0]["email"] is None
