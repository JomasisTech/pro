from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi.testclient import TestClient
import pytest
from app.models import ScheduledPost, SocialAccount


def register(client: TestClient):
    response = client.post("/api/v1/auth/register", json={
        "email": "schedule-owner@example.com", "password": "StrongPass123!",
        "full_name": "Schedule Owner", "organization_name": "Schedule Studio",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    return body, {"Authorization": f"Bearer {body['access_token']}"}, UUID(body["organization"]["id"])


def approved_draft(client: TestClient, headers: dict, org_id: UUID, content: str) -> str:
    drafts_url = f"/api/v1/organizations/{org_id}/drafts"
    created = client.post(drafts_url, headers=headers, json={"content": content, "topic": "Scheduled content"})
    assert created.status_code == 201, created.text
    approved = client.patch(f"{drafts_url}/{created.json()['id']}", headers=headers, json={"status": "approved"})
    assert approved.status_code == 200, approved.text
    return created.json()["id"]


def test_schedule_create_list_cancel_and_calendar(client: TestClient, session_factory):
    body, headers, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-1",
            account_name="Page", account_type="page", granted_scopes=["pages_manage_posts"])
        db.add(account); db.commit(); account_id = str(account.id)
    url = f"/api/v1/organizations/{org_id}/scheduled-posts"
    draft_id = approved_draft(client, headers, org_id, "Our launch")
    payload = {"draft_id": draft_id, "social_account_id": account_id, "provider": "facebook", "title": "Launch",
        "content": "Our launch", "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    created = client.post(url, headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "queued"
    assert client.get(url, headers=headers).json()[0]["id"] == created.json()["id"]
    calendar = client.get(f"/api/v1/organizations/{org_id}/calendar", headers=headers)
    assert any(item["kind"] == "scheduled_post" and item["title"] == "Launch" for item in calendar.json())
    cancelled = client.delete(f"{url}/{created.json()['id']}", headers=headers)
    assert cancelled.status_code == 204
    with session_factory() as db:
        saved = db.get(ScheduledPost, UUID(created.json()["id"]))
        assert saved.status == "cancelled"


def test_schedule_rejects_unsupported_provider_and_timezone(client: TestClient, session_factory):
    body, headers, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-2", account_name="Page", account_type="page")
        db.add(account); db.commit(); account_id = str(account.id)
    url = f"/api/v1/organizations/{org_id}/scheduled-posts"
    base = {"social_account_id": account_id, "title": "Launch", "content": "Text",
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
    assert client.post(url, headers=headers, json={**base, "provider": "tiktok"}).status_code == 422
    assert client.post(url, headers=headers, json={**base, "provider": "facebook", "scheduled_at": "2027-01-01T12:00:00"}).status_code == 422


def test_dispatcher_publishes_due_facebook_job(client: TestClient, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.modules.posting.dispatcher import dispatch_due
    from app.models import SocialCredential, CalendarEntry
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, headers, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-worker",
            account_name="Worker Page", account_type="page", granted_scopes=["pages_manage_posts"])
        db.add(account); db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("worker-token")))
        job = ScheduledPost(organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Worker test", content="Dispatch me", scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        db.add(job); db.commit(); job_id = job.id

    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"id": "page-worker_post-1"}
    class FakeClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data):
            assert url.endswith("/page-worker/feed")
            assert data["access_token"] == "worker-token"
            assert data["message"] == "Dispatch me"
            return FakeResponse()
    import app.modules.posting.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher.httpx, "Client", FakeClient)
    with session_factory() as db:
        assert dispatch_due(db) == {"published": 1, "retrying": 0, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "published" and saved.external_post_id == "page-worker_post-1"
        assert db.query(CalendarEntry).filter_by(external_post_id="page-worker_post-1").count() == 1
    get_settings.cache_clear()


def test_instagram_schedule_requires_publish_scope_and_public_image(client: TestClient, session_factory):
    _, headers, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="instagram", provider_account_id="ig-1",
            account_name="@studio", account_type="professional", granted_scopes=["instagram_business_basic"])
        db.add(account); db.commit(); account_id = str(account.id)
    url = f"/api/v1/organizations/{org_id}/scheduled-posts"
    draft_id = approved_draft(client, headers, org_id, "A new product")
    base = {"draft_id": draft_id, "social_account_id": account_id, "provider": "instagram", "title": "Product photo",
        "content": "A new product", "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    assert client.post(url, headers=headers, json=base).status_code == 422
    assert client.post(url, headers=headers, json={**base, "media_url": "https://cdn.example.com/product.jpg"}).status_code == 409
    with session_factory() as db:
        account = db.query(SocialAccount).filter_by(id=UUID(account_id)).one()
        account.granted_scopes = ["instagram_business_basic", "instagram_business_content_publish"]
        db.commit()
    created = client.post(url, headers=headers, json={**base, "media_url": "https://cdn.example.com/product.jpg"})
    assert created.status_code == 201, created.text
    assert created.json()["provider"] == "instagram"
    assert created.json()["media_url"] == "https://cdn.example.com/product.jpg"


def test_dispatcher_publishes_due_instagram_photo(client: TestClient, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.modules.posting.dispatcher import dispatch_due
    from app.models import SocialCredential, CalendarEntry
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, _, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="instagram", provider_account_id="ig-worker",
            account_name="@worker", account_type="professional",
            granted_scopes=["instagram_business_basic", "instagram_business_content_publish"])
        db.add(account); db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("ig-token")))
        job = ScheduledPost(organization_id=org_id, social_account_id=account.id, provider="instagram",
            title="Photo", content="Caption", media_url="https://cdn.example.com/photo.jpg",
            scheduled_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        db.add(job); db.commit(); job_id = job.id

    class FakeResponse:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data
    class FakeClient:
        def __init__(self, *args, **kwargs): self.calls = []
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, url, data):
            self.calls.append((url, data))
            if url.endswith("/media"): return FakeResponse({"id": "container-1"})
            if url.endswith("/media_publish"):
                assert data["creation_id"] == "container-1"
                return FakeResponse({"id": "ig-post-1"})
            raise AssertionError(url)
    import app.modules.posting.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher.httpx, "Client", FakeClient)
    with session_factory() as db:
        assert dispatch_due(db) == {"published": 1, "retrying": 0, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "published" and saved.external_post_id == "ig-post-1"
        entry = db.query(CalendarEntry).filter_by(external_post_id="ig-post-1").one()
        assert entry.provider == "instagram"
    get_settings.cache_clear()


def test_dispatcher_retries_with_backoff_and_does_not_retry_early(client: TestClient, session_factory, monkeypatch):
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.modules.posting.dispatcher import dispatch_due
    from app.models import SocialCredential
    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-retry",
            account_name="Retry Page", account_type="page", granted_scopes=["pages_manage_posts"])
        db.add(account); db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("token")))
        job = ScheduledPost(organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Retry", content="Try again", scheduled_at=now - timedelta(minutes=2))
        db.add(job); db.commit(); job_id = job.id

    class FailedResponse:
        def raise_for_status(self): raise RuntimeError("temporary provider outage")
    class FailedClient:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def post(self, *args, **kwargs): return FailedResponse()
    import app.modules.posting.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher.httpx, "Client", FailedClient)
    with session_factory() as db:
        assert dispatch_due(db, now=now) == {"published": 0, "retrying": 1, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "queued" and saved.attempts == 1
        assert saved.next_attempt_at is not None
        assert saved.next_attempt_at.replace(tzinfo=timezone.utc) == now + timedelta(seconds=60)
        assert dispatch_due(db, now=now + timedelta(seconds=30)) == {"published": 0, "retrying": 0, "failed": 0}
        assert saved.attempts == 1
    get_settings.cache_clear()


def test_dispatcher_recovers_expired_processing_lease(client: TestClient, session_factory, monkeypatch):
    from app.modules.posting.dispatcher import dispatch_due
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-stale",
            account_name="Stale Page", account_type="page")
        db.add(account); db.flush()
        job = ScheduledPost(organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Stale", content="Recover", scheduled_at=now - timedelta(hours=1), status="processing",
            attempts=0, processing_started_at=now - timedelta(minutes=70))
        db.add(job); db.commit(); job_id = job.id
    with session_factory() as db:
        result = dispatch_due(db, now=now)
        assert result == {"published": 0, "retrying": 1, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "queued" and saved.processing_started_at is None
        assert saved.next_attempt_at.replace(tzinfo=timezone.utc) == now + timedelta(seconds=60)


def test_dispatcher_fails_stale_job_after_final_attempt(client: TestClient, session_factory):
    from app.modules.posting.dispatcher import dispatch_due
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-final",
            account_name="Final Page", account_type="page")
        db.add(account); db.flush()
        job = ScheduledPost(organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Final", content="Do not duplicate", scheduled_at=now - timedelta(hours=1), status="processing",
            attempts=3, processing_started_at=now - timedelta(minutes=70))
        db.add(job); db.commit(); job_id = job.id
    with session_factory() as db:
        assert dispatch_due(db, now=now) == {"published": 0, "retrying": 0, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "failed"
        assert saved.next_attempt_at is None
        assert "final allowed attempt" in saved.last_error


def test_tiktok_schedule_requires_org_owned_video_and_publish_scope(client: TestClient, session_factory):
    from app.models import MediaAsset
    from sqlalchemy import select
    _, headers, org_id = register(client)
    with session_factory() as db:
        account = SocialAccount(organization_id=org_id, provider="tiktok", provider_account_id="tt-1",
            account_name="TikTok Studio", account_type="creator", granted_scopes=["user.info.basic"])
        db.add(account)
        # Use the authenticated organization's owner for the media uploader FK.
        from app.models import User
        owner = db.scalar(select(User).where(User.email == "schedule-owner@example.com"))
        asset = MediaAsset(organization_id=org_id, uploaded_by_user_id=owner.id,
            storage_key="asset-1", original_filename="clip.mp4", content_type="video/mp4",
            size_bytes=8 * 1024 * 1024, sha256_hex="a" * 64)
        db.add(asset); db.commit(); account_id, asset_id = str(account.id), str(asset.id)
    url = f"/api/v1/organizations/{org_id}/scheduled-posts"
    draft_id = approved_draft(client, headers, org_id, "Caption")
    payload = {"draft_id": draft_id, "social_account_id": account_id, "provider": "tiktok", "title": "Clip", "content": "Caption",
        "media_asset_id": asset_id, "video_duration_seconds": 20, "privacy_level": "SELF_ONLY", "consent_to_upload": True,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    assert client.post(url, headers=headers, json=payload).status_code == 409
    assert client.post(url, headers=headers, json={**payload, "consent_to_upload": False}).status_code == 400
    with session_factory() as db:
        account = db.get(SocialAccount, UUID(account_id)); account.granted_scopes = ["video.publish"]; db.commit()
    created = client.post(url, headers=headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["provider"] == "tiktok"
    assert created.json()["media_asset_id"] == asset_id
    with session_factory() as db:
        saved = db.get(ScheduledPost, UUID(created.json()["id"]))
        assert saved.consent_to_upload is True and saved.consented_at is not None
        assert saved.consent_version == "tiktok-scheduled-upload-v1"


def test_regular_member_cannot_schedule_without_approver_authority(client: TestClient, session_factory):
    from app.models import Membership, User

    _, owner_headers, org_id = register(client)
    member_body = client.post("/api/v1/auth/register", json={
        "email": "schedule-member@example.com", "password": "StrongPass123!",
        "full_name": "Schedule Member", "organization_name": "Member's own workspace",
    }).json()
    with session_factory() as db:
        member = db.query(User).filter_by(email="schedule-member@example.com").one()
        db.add(Membership(user_id=member.id, organization_id=org_id, role="member"))
        account = SocialAccount(organization_id=org_id, provider="facebook", provider_account_id="page-member-test",
            account_name="Page", account_type="page", granted_scopes=["pages_manage_posts"])
        db.add(account)
        db.commit()
        account_id = str(account.id)
    member_headers = {"Authorization": f"Bearer {member_body['access_token']}"}
    payload = {"social_account_id": account_id, "provider": "facebook", "title": "Unapproved",
        "content": "A member must not publish directly", "scheduled_at":
        (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()}
    response = client.post(f"/api/v1/organizations/{org_id}/scheduled-posts", headers=member_headers, json=payload)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("failure_kind", ["timeout", "server_error"])
def test_dispatcher_does_not_retry_ambiguous_facebook_publish_failure(client: TestClient, session_factory, monkeypatch, failure_kind):
    """A timeout or 5xx after POST may mean Facebook accepted the post; do not blindly retry."""
    import httpx
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.integrations.social_crypto import encrypt_token
    from app.modules.posting.dispatcher import dispatch_due
    from app.models import SocialCredential

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        account = SocialAccount(
            organization_id=org_id, provider="facebook", provider_account_id="page-timeout",
            account_name="Timeout Page", account_type="page", granted_scopes=["pages_manage_posts"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(
            social_account_id=account.id,
            access_token_encrypted=encrypt_token("timeout-token"),
        ))
        job = ScheduledPost(
            organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Uncertain publish", content="May already be live",
            scheduled_at=now - timedelta(minutes=1),
        )
        db.add(job)
        db.commit()
        job_id = job.id

    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, data):
            assert url.endswith("/page-timeout/feed")
            request = httpx.Request("POST", url)
            if failure_kind == "timeout":
                raise httpx.ReadTimeout(
                    "Provider response timed out after request submission", request=request,
                )
            response = httpx.Response(503, request=request, text="temporarily unavailable")
            raise httpx.HTTPStatusError("provider returned 503", request=request, response=response)

    import app.modules.posting.dispatcher as dispatcher
    monkeypatch.setattr(dispatcher.httpx, "Client", TimeoutClient)

    with session_factory() as db:
        result = dispatch_due(db, now=now)
        assert result == {"published": 0, "retrying": 0, "failed": 1}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "failed"
        assert saved.next_attempt_at is None
        assert "outcome is uncertain" in saved.last_error.lower()
        assert saved.external_post_id is None

    get_settings.cache_clear()


def _seed_due_instagram_job(session_factory, org_id, now, account_id_suffix):
    """Create a connected Instagram account with credentials and one job that is already due."""
    from app.integrations.social_crypto import encrypt_token
    from app.models import SocialCredential

    with session_factory() as db:
        account = SocialAccount(
            organization_id=org_id, provider="instagram", provider_account_id=f"ig-{account_id_suffix}",
            account_name="@ambiguity", account_type="professional",
            granted_scopes=["instagram_business_basic", "instagram_business_content_publish"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=encrypt_token("ig-token")))
        job = ScheduledPost(
            organization_id=org_id, social_account_id=account.id, provider="instagram",
            title="Photo", content="Caption", media_url="https://cdn.example.com/photo.jpg",
            scheduled_at=now - timedelta(minutes=1),
        )
        db.add(job)
        db.commit()
        return job.id


def _install_failing_instagram_client(monkeypatch, *, failing_step: str, failure_kind: str):
    """Fake httpx.Client: container creation succeeds unless `failing_step` is "media".

    Returns the list of Instagram endpoint suffixes ("media", "media_publish") that were called.
    """
    import httpx
    import app.modules.posting.dispatcher as dispatcher

    calls: list[str] = []

    class FakeResponse:
        def __init__(self, data):
            self.data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self.data

    def fail(url):
        request = httpx.Request("POST", url)
        if failure_kind == "timeout":
            raise httpx.ReadTimeout("Provider response timed out after request submission", request=request)
        status = {"server_error": 503, "client_error": 400}[failure_kind]
        response = httpx.Response(status, request=request, text="provider error")
        raise httpx.HTTPStatusError(f"provider returned {status}", request=request, response=response)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def post(self, url, data):
            step = url.rstrip("/").rsplit("/", 1)[-1]
            calls.append(step)
            if step == failing_step:
                fail(url)
            if step == "media":
                return FakeResponse({"id": "container-1"})
            if step == "media_publish":
                return FakeResponse({"id": "ig-post-1"})
            raise AssertionError(url)

    monkeypatch.setattr(dispatcher.httpx, "Client", FakeClient)
    return calls


@pytest.mark.parametrize("failure_kind", ["timeout", "server_error"])
def test_dispatcher_does_not_retry_ambiguous_instagram_media_publish_failure(
    client: TestClient, session_factory, monkeypatch, failure_kind
):
    """The container exists, then media_publish times out or returns 5xx: the photo may be live."""
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.modules.posting.dispatcher import dispatch_due

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    job_id = _seed_due_instagram_job(session_factory, org_id, now, f"ambiguous-{failure_kind}")
    calls = _install_failing_instagram_client(monkeypatch, failing_step="media_publish", failure_kind=failure_kind)

    with session_factory() as db:
        assert dispatch_due(db, now=now) == {"published": 0, "retrying": 0, "failed": 1}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "failed"
        assert saved.next_attempt_at is None
        assert "outcome is uncertain" in saved.last_error.lower()
        assert saved.external_post_id is None
        # No automatic second attempt, even when the retry delay would have long passed.
        assert dispatch_due(db, now=now + timedelta(hours=2)) == {"published": 0, "retrying": 0, "failed": 0}
    assert calls == ["media", "media_publish"]
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("failing_step", "failure_kind"),
    [("media", "timeout"), ("media", "server_error"), ("media_publish", "client_error")],
)
def test_dispatcher_retries_instagram_failures_that_cannot_have_published(
    client: TestClient, session_factory, monkeypatch, failing_step, failure_kind
):
    """Failing before media_publish starts, or being rejected outright (4xx), is safe to retry."""
    from cryptography.fernet import Fernet
    from app.config import get_settings
    from app.modules.posting.dispatcher import dispatch_due

    monkeypatch.setenv("SOCIAL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    _, _, org_id = register(client)
    now = datetime.now(timezone.utc)
    job_id = _seed_due_instagram_job(session_factory, org_id, now, f"safe-{failing_step}-{failure_kind}")
    calls = _install_failing_instagram_client(monkeypatch, failing_step=failing_step, failure_kind=failure_kind)

    with session_factory() as db:
        assert dispatch_due(db, now=now) == {"published": 0, "retrying": 1, "failed": 0}
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "queued"
        assert saved.attempts == 1
        assert saved.next_attempt_at is not None
        assert saved.next_attempt_at.replace(tzinfo=timezone.utc) == now + timedelta(seconds=60)
        assert "uncertain" not in (saved.last_error or "").lower()
        assert saved.external_post_id is None
    if failing_step == "media":
        assert calls == ["media"]  # media_publish must never be attempted without a container
    else:
        assert calls == ["media", "media_publish"]
    get_settings.cache_clear()


def _queued_facebook_post(session_factory, org_id, provider_account_id="page-api"):
    with session_factory() as db:
        account = SocialAccount(
            organization_id=org_id, provider="facebook", provider_account_id=provider_account_id,
            account_name="Page", account_type="page", granted_scopes=["pages_manage_posts"],
        )
        db.add(account)
        db.flush()
        job = ScheduledPost(
            organization_id=org_id, social_account_id=account.id, provider="facebook",
            title="Queued", content="Body", scheduled_at=datetime.now(timezone.utc) + timedelta(hours=3),
            lease_token=UUID("12345678-1234-5678-1234-567812345678"), provider_publish_id="internal-session",
        )
        db.add(job)
        db.commit()
        return job.id


def test_schedule_responses_do_not_expose_worker_internals(client: TestClient, session_factory):
    _, headers, org_id = register(client)
    _queued_facebook_post(session_factory, org_id)
    listed = client.get(f"/api/v1/organizations/{org_id}/scheduled-posts", headers=headers)
    assert listed.status_code == 200, listed.text
    row = listed.json()[0]
    assert row["status"] == "queued" and row["title"] == "Queued"
    for internal in ("lease_token", "lease_expires_at", "processing_started_at", "provider_publish_id"):
        assert internal not in row


@pytest.mark.parametrize("action", ["cancel", "reschedule"])
def test_cancel_and_reschedule_do_not_override_a_post_claimed_meanwhile(
    client: TestClient, session_factory, monkeypatch, action
):
    """A worker can claim the post between loading it and updating it; the API must lose that race."""
    from sqlalchemy import update
    import app.api.v1.scheduling as scheduling_module

    _, headers, org_id = register(client)
    job_id = _queued_facebook_post(session_factory, org_id, f"page-race-{action}")
    original_owned = scheduling_module._owned

    def owned_then_claimed_by_worker(db, membership, schedule_id):
        item = original_owned(db, membership, schedule_id)  # still "queued" in this request
        with session_factory() as worker_db:
            worker_db.execute(update(ScheduledPost).where(ScheduledPost.id == schedule_id).values(status="processing"))
            worker_db.commit()
        return item

    monkeypatch.setattr(scheduling_module, "_owned", owned_then_claimed_by_worker)
    base = f"/api/v1/organizations/{org_id}/scheduled-posts/{job_id}"
    if action == "cancel":
        response = client.delete(base, headers=headers)
    else:
        new_time = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        response = client.patch(f"{base}/reschedule", headers=headers, json={"scheduled_at": new_time})
    assert response.status_code == 409, response.text
    with session_factory() as db:
        saved = db.get(ScheduledPost, job_id)
        assert saved.status == "processing"
