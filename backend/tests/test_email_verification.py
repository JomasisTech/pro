from sqlalchemy import select

from app.api.v1 import auth as auth_module
from app.models import EmailVerificationToken


def _register(client, email="verify@example.com"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPassword123!", "full_name": "Verify User",
        "organization_name": "Verify Workspace",
    })


def test_registration_sends_hashed_one_time_verification_link(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_module, "send_email", lambda settings, to, subject, body: sent.append((to, subject, body)) or True)
    response = _register(client)
    assert response.status_code == 201
    assert len(sent) == 1
    assert "/verify-email#token=" in sent[0][2]
    token = sent[0][2].split("#token=", 1)[1].split()[0]
    from app.core.security import hash_reset_token
    from app.core.database import get_db
    # The route's database is isolated by the fixture; inspect it through the dependency override.
    db_gen = client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        record = db.scalar(select(EmailVerificationToken).where(EmailVerificationToken.token_hash == hash_reset_token(token)))
        assert record is not None
        assert record.token_hash != token
    finally:
        db_gen.close()


def test_verification_marks_email_and_replay_is_rejected(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_module, "send_email", lambda settings, to, subject, body: sent.append(body) or True)
    assert _register(client).status_code == 201
    token = sent[0].split("#token=", 1)[1].split()[0]
    result = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert result.status_code == 200
    assert "verified" in result.json()["message"].lower()
    replay = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert replay.status_code == 400


def test_resend_verification_is_non_enumerating(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_module, "send_email", lambda *args: sent.append(args) or True)
    missing = client.post("/api/v1/auth/resend-verification", json={"email": "missing@example.com"})
    assert missing.status_code == 202
    assert sent == []
    assert _register(client).status_code == 201
    # Use a fresh address/IP limiter key for this request.
    response = client.post("/api/v1/auth/resend-verification", json={"email": "verify@example.com"})
    assert response.status_code == 202
    assert response.json()["message"] == missing.json()["message"]
    assert len(sent) == 2  # registration link plus the requested replacement


def test_required_mode_blocks_provisional_session_until_verified(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_module, "send_email", lambda settings, to, subject, body: sent.append(body) or True)
    monkeypatch.setattr(auth_module._settings, "email_verification_required", True)
    registration = _register(client)
    assert registration.status_code == 201
    access_token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    blocked = client.get("/api/v1/auth/me", headers=headers)
    assert blocked.status_code == 403
    token = sent[0].split("#token=", 1)[1].split()[0]
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    allowed = client.get("/api/v1/auth/me", headers=headers)
    assert allowed.status_code == 200
