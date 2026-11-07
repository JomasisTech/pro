import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.api.v1 import content
from app.api.v1.content import generation_limiter, get_ai_provider
from app.config import Settings
from app.integrations.ai_provider import AIProviderError, GeneratedText
from app.main import app
from uuid import UUID
from datetime import datetime, timezone

from app.models import BrandIntelligenceAnalysis, BusinessProfile, IndustryCategory, Organization
from app.modules.content.prompts import build_caption_prompt


def register(client: TestClient, email: str, organization_name: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123!",
            "full_name": email.split("@")[0].title(),
            "organization_name": organization_name,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


class FakeProvider:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def generate_text(self, system_prompt: str, user_prompt: str) -> GeneratedText:
        self.calls.append((system_prompt, user_prompt))
        if self.error:
            raise self.error
        return GeneratedText(text="Fresh bread daily! #bakery", model="fake-model")


@pytest.fixture()
def provider() -> FakeProvider:
    fake = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: fake
    return fake  # `client` fixture clears dependency_overrides at teardown


def url(organization_id: str) -> str:
    return f"/api/v1/organizations/{organization_id}/content/generate-caption"


def save_profile(client: TestClient, user: dict) -> None:
    response = client.put(
        f"/api/v1/organizations/{user['organization']['id']}/profile",
        headers=user["headers"],
        json={"business_name": "Alice Bakery", "description": "Sourdough bakery", "niche": "Artisan sourdough", "unique_selling_points": "Long-fermented loaves", "brand_voice": "Warm", "language": "en"},
    )
    assert response.status_code == 200, response.text


def test_generation_requires_authentication(client: TestClient, provider: FakeProvider) -> None:
    response = client.post(url("00000000-0000-0000-0000-000000000000"), json={"topic": "New loaves"})
    assert response.status_code == 401


def test_member_generates_caption_from_profile(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    save_profile(client, alice)
    response = client.post(
        url(alice["organization"]["id"]), headers=alice["headers"], json={"topic": "New sourdough loaves", "content_type": "promotion"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"caption": "Fresh bread daily! #bakery", "model": "fake-model"}
    system_prompt, user_prompt = provider.calls[0]
    assert "Alice Bakery" in user_prompt and "Sourdough bakery" in user_prompt and "New sourdough loaves" in user_prompt
    assert "promotional" in user_prompt
    assert "Business niche: Artisan sourdough" in user_prompt
    assert "Unique selling points: Long-fermented loaves" in user_prompt
    assert "Treat business facts" in system_prompt and "owner writing preferences" in system_prompt


def test_profile_is_required_first(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    response = client.post(url(alice["organization"]["id"]), headers=alice["headers"], json={"topic": "New loaves"})
    assert response.status_code == 409
    assert provider.calls == []


def test_other_tenant_cannot_generate_for_this_organization(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bob = register(client, "bob@example.com", "Bob Studio")
    save_profile(client, alice)
    response = client.post(url(alice["organization"]["id"]), headers=bob["headers"], json={"topic": "New loaves"})
    assert response.status_code == 404
    assert provider.calls == []


def test_invalid_input_is_rejected(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    save_profile(client, alice)
    target = url(alice["organization"]["id"])
    assert client.post(target, headers=alice["headers"], json={"topic": " "}).status_code == 422
    assert client.post(target, headers=alice["headers"], json={"topic": "x" * 301}).status_code == 422
    assert client.post(target, headers=alice["headers"], json={"topic": "ok topic", "content_type": "nope"}).status_code == 422
    assert provider.calls == []


def test_provider_failure_returns_502_without_details(client: TestClient) -> None:
    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider(AIProviderError("HTTP 401 secret detail"))
    alice = register(client, "alice@example.com", "Alice Bakery")
    save_profile(client, alice)
    response = client.post(url(alice["organization"]["id"]), headers=alice["headers"], json={"topic": "New loaves"})
    assert response.status_code == 502
    assert "secret detail" not in response.text


def test_unconfigured_provider_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(content, "get_settings", lambda: Settings(openai_api_key="", _env_file=None))
    alice = register(client, "alice@example.com", "Alice Bakery")
    save_profile(client, alice)
    response = client.post(url(alice["organization"]["id"]), headers=alice["headers"], json={"topic": "New loaves"})
    assert response.status_code == 503


def test_hourly_limit_blocks_further_generations(client: TestClient, provider: FakeProvider, session_factory: sessionmaker, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(generation_limiter, "_max_attempts", 2)
    alice = register(client, "alice@example.com", "Alice Bakery")
    with session_factory() as db:  # premium so the monthly plan quota does not interfere
        db.get(Organization, UUID(alice["organization"]["id"])).plan = "premium"
        db.commit()
    save_profile(client, alice)
    target = url(alice["organization"]["id"])
    assert client.post(target, headers=alice["headers"], json={"topic": "One"}).status_code == 200
    assert client.post(target, headers=alice["headers"], json={"topic": "Two"}).status_code == 200
    blocked = client.post(target, headers=alice["headers"], json={"topic": "Three"})
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert len(provider.calls) == 2


def test_prompt_skips_empty_profile_fields() -> None:
    profile = BusinessProfile(business_name="Solo Shop", language="fr")
    industry = IndustryCategory(slug="retail", name="Retail")
    prompt = build_caption_prompt(profile, industry.name, "Soldes d'été", "general")
    assert "Business name: Solo Shop" in prompt and "Industry: Retail" in prompt and "Language to write in: fr" in prompt
    assert "Location:" not in prompt and "Owner-defined brand voice:" not in prompt
    assert "Brand voice mode: hybrid" in prompt


def test_caption_prompt_uses_new_brand_and_niche_preferences() -> None:
    profile = BusinessProfile(
        business_name="Solo Shop",
        niche="Handmade leather bags",
        audience_type="consumers",
        geographic_market="West Africa",
        unique_selling_points="Locally crafted in small batches",
        preferred_tone="Confident and warm",
        preferred_words="crafted with care",
        avoided_words="cheap; guaranteed",
        language="en",
    )
    prompt = build_caption_prompt(profile, "Fashion", "New collection", "promotion")
    assert "Business niche: Handmade leather bags" in prompt
    assert "Audience type: consumers" in prompt
    assert "Geographic market served: West Africa" in prompt
    assert "Unique selling points: Locally crafted in small batches" in prompt
    assert "Owner-preferred writing tone: Confident and warm" in prompt
    assert "Owner-avoided words or phrases: cheap; guaranteed" in prompt


def test_video_script_generation_is_platform_specific_and_brand_aware(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "video@example.com", "Alice Bakery")
    save_profile(client, alice)
    response = client.post(
        f"/api/v1/organizations/{alice['organization']['id']}/content/generate-video-script",
        headers=alice["headers"],
        json={
            "topic": "How we make sourdough",
            "platform": "youtube_shorts",
            "duration_seconds": 45,
            "style": "behind_the_scenes",
            "call_to_action": "Visit our bakery",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"script": "Fresh bread daily! #bakery", "model": "fake-model"}
    system_prompt, user_prompt = provider.calls[0]
    assert "YouTube Shorts" in user_prompt
    assert "45-second" in user_prompt
    assert "behind-the-scenes" in user_prompt
    assert "Alice Bakery" in user_prompt
    assert "Visit our bakery" in user_prompt
    assert "never invent business claims" in system_prompt


def test_video_script_requires_profile_and_valid_platform(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "novideo@example.com", "No Profile")
    target = f"/api/v1/organizations/{alice['organization']['id']}/content/generate-video-script"
    assert client.post(target, headers=alice["headers"], json={"topic": "A useful video"}).status_code == 409
    save_profile(client, alice)
    invalid = client.post(target, headers=alice["headers"], json={"topic": "A useful video", "platform": "myspace"})
    assert invalid.status_code == 422
    assert provider.calls == []


def test_generation_is_recorded_in_the_activity_log(client: TestClient, provider: FakeProvider) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    save_profile(client, alice)
    response = client.post(url(alice["organization"]["id"]), headers=alice["headers"], json={"topic": "New sourdough loaves"})
    assert response.status_code == 200, response.text
    log = client.get(
        f"/api/v1/organizations/{alice['organization']['id']}/activity?action_prefix=content.", headers=alice["headers"]
    ).json()
    assert [entry["action"] for entry in log] == ["content.caption_generated"]
    assert "New sourdough loaves" in log[0]["summary"]


def test_caption_prompt_respects_voice_mode_and_owner_instructions() -> None:
    learned = {"proposed_voice": "Friendly and conversational", "tone": ["warm"], "writing_patterns": ["short sentences"]}
    hybrid = build_caption_prompt({
        "business_name": "Solo Shop", "language": "en", "brand_voice_mode": "hybrid",
        "preferred_tone": "Confident", "custom_ai_instructions": "Avoid slang.",
        "learned_brand_voice": learned,
    }, "Retail", "New collection", "general")
    assert "Approved social-media brand observations" in hybrid
    assert "Friendly and conversational" in hybrid
    assert "Avoid slang." in hybrid

    manual = build_caption_prompt({
        "business_name": "Solo Shop", "language": "en", "brand_voice_mode": "manual",
        "preferred_tone": "Confident", "custom_ai_instructions": "Avoid slang.",
        "learned_brand_voice": learned,
    }, "Retail", "New collection", "general")
    assert "Approved social-media brand observations" not in manual
    assert "Avoid slang." in manual


def test_caption_generation_uses_only_approved_social_voice_in_hybrid_mode(client: TestClient, provider: FakeProvider, session_factory: sessionmaker) -> None:
    alice = register(client, "hybrid@example.com", "Hybrid Bakery")
    organization_id = UUID(alice["organization"]["id"])
    response = client.put(
        f"/api/v1/organizations/{organization_id}/profile", headers=alice["headers"],
        json={"business_name": "Hybrid Bakery", "industry_id": None, "niche": "Sourdough",
              "description": "Local bakery", "language": "en", "brand_voice_mode": "hybrid",
              "custom_ai_instructions": "Avoid slang."},
    )
    assert response.status_code == 200, response.text
    with session_factory() as db:
        db.add(BrandIntelligenceAnalysis(
            organization_id=organization_id, status="approved",
            proposal={"proposed_voice": "Warm, community-focused", "tone": ["friendly"],
                      "writing_patterns": ["short sentences"]},
            reviewed_at=datetime.now(timezone.utc),
        ))
        db.add(BrandIntelligenceAnalysis(
            organization_id=organization_id, status="pending",
            proposal={"proposed_voice": "Unreviewed and formal"},
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
    generated = client.post(url(str(organization_id)), headers=alice["headers"], json={"topic": "Fresh bread"})
    assert generated.status_code == 200, generated.text
    prompt = provider.calls[0][1]
    assert "Warm, community-focused" in prompt
    assert "Unreviewed and formal" not in prompt
    assert "Avoid slang." in prompt


def test_automatic_voice_mode_uses_social_analysis_without_manual_tone_fields() -> None:
    prompt = build_caption_prompt({
        "business_name": "Solo Shop", "language": "en", "brand_voice_mode": "automatic",
        "preferred_tone": "Strictly formal", "brand_voice": "Very serious",
        "preferred_words": "dear customer", "avoided_words": "hey",
        "custom_ai_instructions": "Avoid long paragraphs.",
        "learned_brand_voice": {"proposed_voice": "Friendly and warm"},
    }, "Retail", "New collection", "general")
    assert "Friendly and warm" in prompt
    assert "Strictly formal" not in prompt
    assert "Very serious" not in prompt
    assert "Avoid long paragraphs." in prompt
