import json
from types import SimpleNamespace

from app.integrations import resend_email


def test_resend_campaign_send_uses_stable_idempotency_key(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"id":"resend-message-123"}'

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(resend_email, "urlopen", fake_urlopen)
    settings = SimpleNamespace(resend_api_key="re_test", email_from="AutoBizPro <mail@example.test>", email_provider_timeout_seconds=9)
    result = resend_email.send_campaign_email(
        settings, to_address="person@example.test", subject="Hello", body="Text", idempotency_key="campaign/1/recipient/2"
    )

    assert result.accepted is True
    assert result.provider_message_id == "resend-message-123"
    assert captured["request"].get_header("Idempotency-key") == "campaign/1/recipient/2"
    assert json.loads(captured["request"].data)["to"] == ["person@example.test"]
    assert captured["timeout"] == 9


def test_resend_permanent_http_error_is_not_retried(monkeypatch):
    from urllib.error import HTTPError
    import io

    def fake_urlopen(*args, **kwargs):
        raise HTTPError("https://api.resend.com/emails", 401, "Unauthorized", {}, io.BytesIO(b'{"message":"Invalid API key"}'))

    monkeypatch.setattr(resend_email, "urlopen", fake_urlopen)
    settings = SimpleNamespace(resend_api_key="bad", email_from="Sender <a@example.test>", email_provider_timeout_seconds=9)
    result = resend_email.send_campaign_email(settings, to_address="p@example.test", subject="S", body="B", idempotency_key="k")
    assert result.accepted is False
    assert result.retryable is False
    assert "Invalid API key" in result.error
