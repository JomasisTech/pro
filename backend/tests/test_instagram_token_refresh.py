from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.integrations import instagram_tokens


class FakeDB:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_instagram_token_is_not_refreshed_when_expiry_is_outside_window(monkeypatch):
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    account = SimpleNamespace(provider="instagram", token_expires_at=now + timedelta(days=30))
    credential = SimpleNamespace(access_token_encrypted=b"encrypted-old")
    db = FakeDB()
    monkeypatch.setattr(instagram_tokens, "decrypt_token", lambda value: "old-token")
    monkeypatch.setattr(instagram_tokens.httpx, "get", lambda *args, **kwargs: pytest.fail("unexpected refresh"))

    result = instagram_tokens.get_instagram_access_token(db, account, credential, now=now)

    assert result == "old-token"
    assert db.commits == 0


def test_instagram_token_refreshes_before_expiry_and_persists(monkeypatch):
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    account = SimpleNamespace(provider="instagram", token_expires_at=now + timedelta(days=2))
    credential = SimpleNamespace(access_token_encrypted=b"encrypted-old")
    db = FakeDB()
    calls = []
    monkeypatch.setattr(instagram_tokens, "decrypt_token", lambda value: "old-token")
    monkeypatch.setattr(instagram_tokens, "encrypt_token", lambda value: f"encrypted:{value}".encode())

    def fake_get(url, *, params, timeout, follow_redirects):
        calls.append((url, params, timeout, follow_redirects))
        return FakeResponse({"access_token": "new-token", "expires_in": 5_184_000})

    monkeypatch.setattr(instagram_tokens.httpx, "get", fake_get)
    result = instagram_tokens.get_instagram_access_token(db, account, credential, now=now)

    assert result == "new-token"
    assert credential.access_token_encrypted == b"encrypted:new-token"
    assert account.token_expires_at == now + timedelta(seconds=5_184_000)
    assert db.commits == 1
    assert calls[0][1] == {"grant_type": "ig_refresh_token", "access_token": "old-token"}


def test_expired_instagram_token_requires_reconnection(monkeypatch):
    now = datetime(2026, 11, 4, tzinfo=timezone.utc)
    account = SimpleNamespace(provider="instagram", token_expires_at=now - timedelta(seconds=1))
    credential = SimpleNamespace(access_token_encrypted=b"encrypted-old")
    monkeypatch.setattr(instagram_tokens, "decrypt_token", lambda value: "old-token")
    monkeypatch.setattr(instagram_tokens.httpx, "get", lambda *args, **kwargs: pytest.fail("expired token must not refresh"))

    with pytest.raises(RuntimeError, match="expired; reconnect"):
        instagram_tokens.get_instagram_access_token(FakeDB(), account, credential, now=now)


def test_instagram_refresh_rejects_invalid_provider():
    account = SimpleNamespace(provider="facebook", token_expires_at=None)
    credential = SimpleNamespace(access_token_encrypted=b"encrypted")
    with pytest.raises(ValueError, match="non-Instagram"):
        instagram_tokens.get_instagram_access_token(FakeDB(), account, credential)


def test_ambiguous_publish_errors_are_not_automatically_retried():
    import httpx
    from app.modules.posting.dispatcher import _publish_outcome_is_ambiguous

    assert _publish_outcome_is_ambiguous(httpx.ReadTimeout("request timed out"))
    assert _publish_outcome_is_ambiguous(httpx.ConnectError("connection lost"))


def test_provider_client_errors_are_not_classified_as_ambiguous():
    import httpx
    from app.modules.posting.dispatcher import _publish_outcome_is_ambiguous

    request = httpx.Request("POST", "https://provider.example/publish")
    response = httpx.Response(400, request=request)
    assert not _publish_outcome_is_ambiguous(httpx.HTTPStatusError("bad request", request=request, response=response))


def test_provider_server_errors_are_classified_as_ambiguous():
    import httpx
    from app.modules.posting.dispatcher import _publish_outcome_is_ambiguous

    request = httpx.Request("POST", "https://provider.example/publish")
    response = httpx.Response(503, request=request)
    assert _publish_outcome_is_ambiguous(httpx.HTTPStatusError("server error", request=request, response=response))


def test_post_request_processing_errors_are_classified_as_ambiguous():
    from sqlalchemy.exc import OperationalError
    from app.modules.posting.dispatcher import AmbiguousPublishResponseError, _publish_outcome_is_ambiguous

    # A malformed success body, missing post ID, or local DB failure can happen after
    # the provider has accepted the post; none should trigger an automatic duplicate.
    assert _publish_outcome_is_ambiguous(AmbiguousPublishResponseError("provider response omitted post ID"))
    assert _publish_outcome_is_ambiguous(ValueError("malformed provider JSON"))
    assert _publish_outcome_is_ambiguous(OperationalError("commit", {}, Exception("database unavailable")))
