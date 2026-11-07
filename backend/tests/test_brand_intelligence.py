from uuid import UUID

from fastapi.testclient import TestClient

from app.models import BusinessProfile, SocialAccount


def register(client: TestClient, email: str, organization_name: str) -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": email.split("@")[0],
        "organization_name": organization_name,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


class FakeAI:
    def generate_text(self, system_prompt: str, user_prompt: str):
        from app.integrations.ai_provider import GeneratedText
        return GeneratedText(text='{"topics":["education"],"content_categories":["tips"],"tone":["friendly"],"writing_patterns":["short sentences"],"recurring_themes":["learning"],"hashtags":["#learn"],"emoji_patterns":[],"proposed_voice":"Friendly educator","confidence":"medium","conflicts":[]}', model="test-model")


def test_brand_observations_analysis_and_review_are_tenant_scoped(client: TestClient, session_factory, monkeypatch) -> None:
    import app.api.v1.brand_intelligence as module
    monkeypatch.setattr(module, "build_ai_provider", lambda *args, **kwargs: FakeAI())
    owner = register(client, "brand-owner@example.com", "Brand Studio")
    outsider = register(client, "brand-outsider@example.com", "Other Studio")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(organization_id), provider="instagram",
                                provider_account_id="ig-1", account_name="@brand", granted_scopes=[])
        db.add(account)
        db.add(BusinessProfile(organization_id=UUID(organization_id), business_name="Brand Studio",
                               niche="Education", description="Learning resources", target_audience="Students"))
        db.commit()
        account_id = str(account.id)
    base = f"/api/v1/organizations/{organization_id}/brand-intelligence"
    created = client.post(f"{base}/observations/manual", headers=owner["headers"], json={
        "social_account_id": account_id, "source_post_id": "post-1", "post_text": "Five study tips for exams #learn",
    })
    assert created.status_code == 201, created.text
    assert created.json()["provenance"]["confidence"] == "unverified"
    assert client.get(f"{base}/observations", headers=outsider["headers"]).status_code == 404
    analysis = client.post(f"{base}/analyze", headers=owner["headers"])
    assert analysis.status_code == 201, analysis.text
    assert analysis.json()["status"] == "pending"
    analysis_id = analysis.json()["id"]
    assert client.post(f"{base}/analyses/{analysis_id}/review", headers=outsider["headers"], json={"decision": "approved"}).status_code == 404
    reviewed = client.post(f"{base}/analyses/{analysis_id}/review", headers=owner["headers"], json={"decision": "approved"})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "approved"
    assert client.post(f"{base}/analyses/{analysis_id}/review", headers=owner["headers"], json={"decision": "rejected"}).status_code == 409


def test_facebook_page_sync_imports_and_updates_without_duplicates(client: TestClient, session_factory, monkeypatch) -> None:
    import app.api.v1.brand_intelligence as module
    from app.models import SocialCredential

    owner = register(client, "facebook-brand@example.com", "Facebook Brand")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(organization_id), provider="facebook", provider_account_id="page-123",
            account_name="Facebook Brand Page", granted_scopes=["pages_show_list", "pages_read_engagement"],
        )
        db.add(account)
        db.flush()
        db.add(SocialCredential(social_account_id=account.id, access_token_encrypted=b"encrypted-test-token"))
        db.commit()
        account_id = str(account.id)

    monkeypatch.setattr(module, "decrypt_token", lambda value: "page-access-token")
    monkeypatch.setattr(module, "fetch_recent_facebook_page_posts", lambda page_id, token, limit: [{
        "source_post_id": "page-123_456", "post_text": "A new Facebook update", "permalink": "https://facebook.com/post/456",
        "published_at": None, "media_type": "post",
    }])
    endpoint = f"/api/v1/organizations/{organization_id}/brand-intelligence/sync/{account_id}"
    first = client.post(endpoint, headers=owner["headers"])
    assert first.status_code == 200, first.text
    assert first.json()["provider"] == "facebook"
    assert first.json()["inserted"] == 1
    second = client.post(endpoint, headers=owner["headers"])
    assert second.status_code == 200, second.text
    assert second.json()["inserted"] == 0
    assert second.json()["updated"] == 1
    observations = client.get(f"/api/v1/organizations/{organization_id}/brand-intelligence/observations", headers=owner["headers"])
    assert observations.status_code == 200
    assert len(observations.json()) == 1
    assert observations.json()[0]["provider"] == "facebook"
    assert observations.json()[0]["provenance"]["provider"] == "facebook"


def test_facebook_page_post_adapter_caps_results_and_normalizes_fields(monkeypatch) -> None:
    from app.integrations import facebook_media

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [
                {"id": "page_1", "message": "Page update", "created_time": "2026-11-04T12:00:00+0000",
                 "permalink_url": "https://www.facebook.com/page/posts/1"},
                {"id": "page_2", "message": "Another update", "created_time": "2026-11-03T12:00:00+0000"},
            ]}

    class FakeClient:
        def __init__(self, **kwargs):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None, headers=None):
            self.calls.append((url, params, headers))
            return FakeResponse()

    monkeypatch.setattr(facebook_media.httpx, "Client", FakeClient)
    posts = facebook_media.fetch_recent_facebook_page_posts("page-1", "secret-token", limit=200)
    assert len(posts) == 2
    assert posts[0]["source_post_id"] == "page_1"
    assert posts[0]["post_text"] == "Page update"
    assert posts[0]["published_at"].tzinfo is not None
    assert posts[1]["permalink"] is None


def test_facebook_page_post_adapter_rejects_missing_credentials() -> None:
    from app.integrations.facebook_media import FacebookMediaError, fetch_recent_facebook_page_posts
    import pytest

    with pytest.raises(FacebookMediaError):
        fetch_recent_facebook_page_posts("", "token")


def test_brand_sync_jobs_are_queued_deduplicated_and_tenant_scoped(client: TestClient, session_factory) -> None:
    from app.models import BrandSyncJob

    owner = register(client, "sync-job-owner@example.com", "Sync Job Studio")
    outsider = register(client, "sync-job-outsider@example.com", "Other Sync Studio")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(organization_id), provider="instagram",
                                provider_account_id="ig-sync-job", account_name="@syncjob")
        db.add(account)
        db.commit()
        account_id = str(account.id)

    base = f"/api/v1/organizations/{organization_id}/brand-intelligence"
    queued = client.post(f"{base}/sync-jobs/{account_id}", headers=owner["headers"])
    assert queued.status_code == 202, queued.text
    assert queued.json()["status"] == "queued"
    duplicate = client.post(f"{base}/sync-jobs/{account_id}", headers=owner["headers"])
    assert duplicate.status_code == 202
    assert duplicate.json()["id"] == queued.json()["id"]

    listed = client.get(f"{base}/sync-jobs", headers=owner["headers"])
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.get(f"{base}/sync-jobs", headers=outsider["headers"]).status_code == 404
    with session_factory() as db:
        jobs = db.query(BrandSyncJob).all()
        assert len(jobs) == 1
        assert jobs[0].status == "queued"


def _seed_observations(client: TestClient, session_factory, email: str, texts: list[str], profile_kwargs: dict | None = None) -> tuple[dict, str]:
    owner = register(client, email, "Rules Studio")
    organization_id = owner["organization"]["id"]
    with session_factory() as db:
        account = SocialAccount(organization_id=UUID(organization_id), provider="instagram",
                                provider_account_id="ig-r", account_name="@rules", granted_scopes=[])
        db.add(account)
        db.add(BusinessProfile(organization_id=UUID(organization_id), business_name="Rules Studio", niche="Bakery",
                               description="Bread and cakes", **(profile_kwargs or {})))
        db.commit()
        account_id = str(account.id)
    base = f"/api/v1/organizations/{organization_id}/brand-intelligence"
    for index, text in enumerate(texts):
        created = client.post(f"{base}/observations/manual", headers=owner["headers"],
                              json={"social_account_id": account_id, "source_post_id": f"p{index}", "post_text": text})
        assert created.status_code == 201, created.text
    return owner, base


def test_rule_based_analysis_works_without_an_ai_provider(client: TestClient, session_factory, monkeypatch) -> None:
    import app.api.v1.brand_intelligence as module
    called: list = []
    monkeypatch.setattr(module, "build_ai_provider", lambda *a, **k: called.append(1))
    owner, base = _seed_observations(client, session_factory, "rules1@example.com",
                                     [f"Fresh bread number {i} #bakery order now" for i in range(6)])
    # Default (AI) mode is still unavailable without a provider, exactly as before.
    assert client.post(f"{base}/analyze", headers=owner["headers"]).status_code == 503
    response = client.post(f"{base}/analyze?method=rules", headers=owner["headers"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["model"] == "rule-based" and body["status"] == "pending"
    assert body["proposal"]["method"] == "rules" and body["proposal"]["posts_analyzed"] == 6
    assert "#bakery" in body["proposal"]["hashtags"] and body["proposal"]["proposed_voice"] == ""
    assert len(called) == 1  # only the default-mode call above consulted the provider
    reviewed = client.post(f"{base}/analyses/{body['id']}/review", headers=owner["headers"], json={"decision": "approved"})
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "approved"


def test_rule_based_analysis_reports_profile_conflicts_and_low_evidence(client: TestClient, session_factory) -> None:
    owner, base = _seed_observations(client, session_factory, "rules2@example.com",
                                     ["Cheap deals on bread", "Cheap cakes today"], {"avoided_words": "cheap"})
    body = client.post(f"{base}/analyze?method=rules", headers=owner["headers"]).json()
    assert body["proposal"]["evidence_level"] == "initial" and body["proposal"]["confidence"] == "low"
    assert any(item["field"] == "avoided_words" for item in body["conflicts"])


def test_invalid_analysis_method_is_rejected(client: TestClient, session_factory) -> None:
    owner, base = _seed_observations(client, session_factory, "rules3@example.com", ["One post"])
    assert client.post(f"{base}/analyze?method=magic", headers=owner["headers"]).status_code == 422
