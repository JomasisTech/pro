from datetime import timezone

import pytest
import httpx

from app.integrations.facebook_media import (
    FacebookMediaError,
    fetch_recent_facebook_page_posts,
)


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


def test_fetch_recent_facebook_posts_normalizes_fields_and_caps_limit(monkeypatch):
    calls = {}

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, url, **kwargs):
            calls["url"] = url
            calls.update(kwargs)
            return FakeResponse({"data": [
                {"id": "page_1", "message": "Hello", "permalink_url": "https://facebook.com/p/1", "created_time": "2026-11-04T10:30:00+0000"},
                {"id": "page_2", "message": 12, "created_time": "not-a-date"},
            ]})

    monkeypatch.setattr("app.integrations.facebook_media.httpx.Client", FakeClient)
    posts = fetch_recent_facebook_page_posts("page-1", "secret-token", limit=200)
    assert calls["url"].endswith("/page-1/posts")
    assert calls["params"]["limit"] == 20
    assert calls["headers"]["Authorization"] == "Bearer secret-token"
    assert posts[0]["source_post_id"] == "page_1"
    assert posts[0]["post_text"] == "Hello"
    assert posts[0]["published_at"].tzinfo is not None
    assert posts[0]["published_at"].utcoffset() == timezone.utc.utcoffset(None)
    assert posts[1]["post_text"] == ""
    assert posts[1]["published_at"] is None


def test_fetch_recent_facebook_posts_rejects_missing_identity():
    with pytest.raises(FacebookMediaError):
        fetch_recent_facebook_page_posts("", "token")


def test_fetch_recent_facebook_posts_hides_provider_errors(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def get(self, *args, **kwargs):
            request = httpx.Request("GET", "https://graph.facebook.com")
            response = httpx.Response(403, request=request, text="secret-token invalid")
            raise httpx.HTTPStatusError("secret-token invalid", request=request, response=response)

    monkeypatch.setattr("app.integrations.facebook_media.httpx.Client", FakeClient)
    with pytest.raises(FacebookMediaError) as exc:
        fetch_recent_facebook_page_posts("page-1", "secret-token")
    assert "secret-token" not in str(exc.value)
