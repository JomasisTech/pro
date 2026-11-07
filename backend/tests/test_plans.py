from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.api.v1.content import get_ai_provider
from app.core import plans
from app.core.plans import PLAN_LIMITS, PLAN_NAMES, Metric
from app.integrations.ai_provider import GeneratedText
from app.main import app
from app.models import Organization


class FakeProvider:
    def generate_text(self, system_prompt: str, user_prompt: str) -> GeneratedText:
        return GeneratedText(text="A caption #tag", model="fake")


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


def setup_org(client: TestClient) -> dict:
    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()
    alice = register(client, "alice@example.com", "Alice Bakery")
    saved = client.put(
        f"/api/v1/organizations/{alice['organization']['id']}/profile",
        headers=alice["headers"],
        json={"business_name": "Alice Bakery", "language": "en"},
    )
    assert saved.status_code == 200, saved.text
    return alice


def generate(client: TestClient, user: dict):
    return client.post(
        f"/api/v1/organizations/{user['organization']['id']}/content/generate-caption",
        headers=user["headers"],
        json={"topic": "New loaves"},
    )


def usage(client: TestClient, user: dict) -> dict:
    response = client.get(f"/api/v1/organizations/{user['organization']['id']}/usage", headers=user["headers"])
    assert response.status_code == 200, response.text
    return {item["metric"]: item for item in response.json()["metrics"]} | {"_plan": response.json()}


def test_every_plan_defines_every_metric_and_has_a_name() -> None:
    metrics = {value for key, value in vars(Metric).items() if not key.startswith("_")}
    assert set(PLAN_LIMITS) == set(PLAN_NAMES)
    for plan, limits in PLAN_LIMITS.items():
        assert set(limits) == metrics, f"plan {plan} must define exactly the declared metrics"
        assert all(value is None or value >= 0 for value in limits.values())


def test_unknown_plan_falls_back_to_the_default_plan() -> None:
    assert plans.get_limit("made-up", Metric.AI_CAPTIONS) == plans.get_limit(plans.DEFAULT_PLAN, Metric.AI_CAPTIONS)
    assert plans.get_limit(None, Metric.AI_CAPTIONS) == plans.get_limit(plans.DEFAULT_PLAN, Metric.AI_CAPTIONS)


def test_new_organizations_start_on_the_free_plan(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    body = usage(client, alice)
    assert body["_plan"]["plan"] == "free"
    assert body[Metric.AI_CAPTIONS]["limit"] == PLAN_LIMITS["free"][Metric.AI_CAPTIONS]
    assert body[Metric.AI_CAPTIONS]["used"] == 0


def test_usage_requires_authentication_and_membership(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bob = register(client, "bob@example.com", "Bob Studio")
    url = f"/api/v1/organizations/{alice['organization']['id']}/usage"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bob["headers"]).status_code == 404


def test_free_plan_limit_is_enforced_and_failures_do_not_consume_quota(client: TestClient) -> None:
    alice = setup_org(client)
    limit = PLAN_LIMITS["free"][Metric.AI_CAPTIONS]
    for _ in range(limit):
        assert generate(client, alice).status_code == 200
    blocked = generate(client, alice)
    assert blocked.status_code == 402
    assert "Free plan" in blocked.json()["detail"] and "AI captions" in blocked.json()["detail"]
    body = usage(client, alice)
    assert body[Metric.AI_CAPTIONS]["used"] == limit
    assert body[Metric.AI_CAPTIONS]["remaining"] == 0


def test_changing_one_number_in_the_catalog_changes_enforcement_and_usage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice = setup_org(client)
    monkeypatch.setitem(PLAN_LIMITS["free"], Metric.AI_CAPTIONS, 1)
    assert generate(client, alice).status_code == 200
    assert generate(client, alice).status_code == 402
    assert usage(client, alice)[Metric.AI_CAPTIONS]["limit"] == 1

    monkeypatch.setitem(PLAN_LIMITS["free"], Metric.AI_CAPTIONS, 3)
    assert generate(client, alice).status_code == 200
    assert usage(client, alice)[Metric.AI_CAPTIONS]["remaining"] == 1


def test_unlimited_plan_is_never_blocked(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alice = setup_org(client)
    monkeypatch.setitem(PLAN_LIMITS["free"], Metric.AI_CAPTIONS, None)
    for _ in range(4):
        assert generate(client, alice).status_code == 200
    assert usage(client, alice)[Metric.AI_CAPTIONS]["remaining"] is None


def test_upgrading_the_plan_raises_the_limit(client: TestClient, session_factory: sessionmaker) -> None:
    alice = setup_org(client)
    for _ in range(PLAN_LIMITS["free"][Metric.AI_CAPTIONS]):
        generate(client, alice)
    assert generate(client, alice).status_code == 402
    with session_factory() as db:
        db.get(Organization, UUID(alice["organization"]["id"])).plan = "standard"
        db.commit()
    assert generate(client, alice).status_code == 200
    assert usage(client, alice)["_plan"]["plan_name"] == "Standard"


def test_usage_is_counted_per_organization(client: TestClient) -> None:
    alice = setup_org(client)
    bob = register(client, "bob@example.com", "Bob Studio")
    for _ in range(PLAN_LIMITS["free"][Metric.AI_CAPTIONS]):
        generate(client, alice)
    assert usage(client, bob)[Metric.AI_CAPTIONS]["used"] == 0


def test_last_months_usage_does_not_count(client: TestClient, session_factory: sessionmaker) -> None:
    from datetime import UTC, datetime, timedelta

    from app.models import UsageEvent

    alice = setup_org(client)
    with session_factory() as db:
        db.add(
            UsageEvent(
                organization_id=UUID(alice["organization"]["id"]),
                metric=Metric.AI_CAPTIONS,
                quantity=99,
                created_at=datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
            )
        )
        db.commit()
    assert usage(client, alice)[Metric.AI_CAPTIONS]["used"] == 0
    assert generate(client, alice).status_code == 200
