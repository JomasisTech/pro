from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models import IndustryCategory, Membership, Organization, User


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


def seed_categories(session_factory: sessionmaker) -> dict:
    """Two industries, one subcategory each (migration seed data is not present in SQLite tests)."""
    with session_factory() as db:
        fashion = IndustryCategory(slug="fashion", name="Fashion", sort_order=0)
        food = IndustryCategory(slug="restaurants", name="Restaurants & Food", sort_order=1)
        db.add_all([fashion, food])
        db.flush()
        womenswear = IndustryCategory(slug="fashion-womenswear", name="Womenswear", parent_id=fashion.id)
        cafe = IndustryCategory(slug="restaurants-cafe", name="Cafe", parent_id=food.id)
        db.add_all([womenswear, cafe])
        db.commit()
        return {
            "fashion": str(fashion.id),
            "food": str(food.id),
            "womenswear": str(womenswear.id),
            "cafe": str(cafe.id),
        }


def profile_url(organization_id: str) -> str:
    return f"/api/v1/organizations/{organization_id}/profile"


def valid_profile(**overrides: object) -> dict:
    data = {"business_name": "Alice Studio", "description": "Custom dresses", "language": "en"}
    data.update(overrides)
    return data


def test_categories_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/categories").status_code == 401


def test_categories_are_returned_nested_and_ordered(client: TestClient, session_factory: sessionmaker) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "alice@example.com", "Alice Studio")

    response = client.get("/api/v1/categories", headers=alice["headers"])
    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body] == ["fashion", "restaurants"]
    assert body[0]["id"] == ids["fashion"]
    assert [sub["name"] for sub in body[0]["subcategories"]] == ["Womenswear"]
    assert body[1]["subcategories"][0]["id"] == ids["cafe"]


def test_profile_requires_authentication(client: TestClient) -> None:
    organization_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(profile_url(organization_id)).status_code == 401
    assert client.put(profile_url(organization_id), json=valid_profile()).status_code == 401


def test_profile_is_404_until_saved(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    response = client.get(profile_url(alice["organization"]["id"]), headers=alice["headers"])
    assert response.status_code == 404


def test_owner_can_create_then_replace_profile(client: TestClient, session_factory: sessionmaker) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "alice@example.com", "Alice Studio")
    url = profile_url(alice["organization"]["id"])

    created = client.put(
        url,
        headers=alice["headers"],
        json=valid_profile(industry_id=ids["fashion"], subcategory_id=ids["womenswear"], location="Lagos"),
    )
    assert created.status_code == 200, created.text
    assert created.json()["industry_id"] == ids["fashion"]
    assert created.json()["location"] == "Lagos"

    replaced = client.put(url, headers=alice["headers"], json=valid_profile(business_name="Alice Atelier"))
    assert replaced.status_code == 200
    assert replaced.json()["business_name"] == "Alice Atelier"
    # PUT replaces the whole profile, so omitted optional fields are cleared.
    assert replaced.json()["industry_id"] is None
    assert replaced.json()["location"] is None

    fetched = client.get(url, headers=alice["headers"])
    assert fetched.status_code == 200
    assert fetched.json()["business_name"] == "Alice Atelier"


def test_text_is_trimmed_and_blank_optional_text_becomes_null(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    response = client.put(
        profile_url(alice["organization"]["id"]),
        headers=alice["headers"],
        json=valid_profile(business_name="  Alice Studio  ", description="   ", brand_voice=" Warm "),
    )
    assert response.status_code == 200
    assert response.json()["business_name"] == "Alice Studio"
    assert response.json()["description"] is None
    assert response.json()["brand_voice"] == "Warm"


def test_invalid_profile_input_is_rejected(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    url = profile_url(alice["organization"]["id"])
    assert client.put(url, headers=alice["headers"], json=valid_profile(business_name="   ")).status_code == 422
    assert client.put(url, headers=alice["headers"], json=valid_profile(description="x" * 2001)).status_code == 422
    assert client.put(url, headers=alice["headers"], json=valid_profile(language="")).status_code == 422
    assert client.put(url, headers=alice["headers"], json={}).status_code == 422


def test_category_choices_are_validated(client: TestClient, session_factory: sessionmaker) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "alice@example.com", "Alice Studio")
    url = profile_url(alice["organization"]["id"])
    missing = "11111111-1111-1111-1111-111111111111"

    unknown_industry = client.put(url, headers=alice["headers"], json=valid_profile(industry_id=missing))
    subcategory_as_industry = client.put(url, headers=alice["headers"], json=valid_profile(industry_id=ids["cafe"]))
    subcategory_without_industry = client.put(
        url, headers=alice["headers"], json=valid_profile(subcategory_id=ids["cafe"])
    )
    mismatched = client.put(
        url, headers=alice["headers"], json=valid_profile(industry_id=ids["fashion"], subcategory_id=ids["cafe"])
    )
    assert unknown_industry.status_code == 400
    assert subcategory_as_industry.status_code == 400
    assert subcategory_without_industry.status_code == 400
    assert mismatched.status_code == 400
    assert client.get(url, headers=alice["headers"]).status_code == 404  # nothing was saved


def test_other_tenants_profile_is_hidden_and_cannot_be_changed(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    bob = register(client, "bob@example.com", "Bob Bakery")
    client.put(profile_url(bob["organization"]["id"]), headers=bob["headers"], json=valid_profile(business_name="Bob Bakery"))

    url = profile_url(bob["organization"]["id"])
    read = client.get(url, headers=alice["headers"])
    write = client.put(url, headers=alice["headers"], json=valid_profile(business_name="Hijacked"))
    assert read.status_code == 404
    assert write.status_code == 404
    assert client.get(url, headers=bob["headers"]).json()["business_name"] == "Bob Bakery"


def test_plain_member_can_read_but_not_write_profile(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    url = profile_url(alice["organization"]["id"])
    client.put(url, headers=alice["headers"], json=valid_profile())

    with session_factory() as db:
        user = User(email="member@example.com", password_hash=hash_password("StrongPass123!"), full_name="Member")
        organization = db.get(Organization, UUID(alice["organization"]["id"]))
        db.add(Membership(user=user, organization=organization, role="member"))
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "member@example.com", "password": "StrongPass123!"})
    member_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert client.get(url, headers=member_headers).status_code == 200
    assert client.put(url, headers=member_headers, json=valid_profile(business_name="Nope")).status_code == 403


def test_profile_saves_extended_onboarding_fields(client: TestClient, session_factory: sessionmaker) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "onboarding@example.com", "Alice Studio")
    response = client.put(
        profile_url(alice["organization"]["id"]),
        headers=alice["headers"],
        json=valid_profile(
            industry_id=ids["fashion"],
            niche="Custom bridal wear",
            audience_type="consumers",
            geographic_market="Lagos and Abuja",
            unique_selling_points="Made-to-measure fittings",
            preferred_tone="Warm and confident",
            preferred_words="made for you; thoughtful design",
            avoided_words="cheap; guaranteed results",
        ),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["niche"] == "Custom bridal wear"
    assert body["audience_type"] == "consumers"
    assert body["geographic_market"] == "Lagos and Abuja"
    assert body["unique_selling_points"] == "Made-to-measure fittings"
    assert body["preferred_tone"] == "Warm and confident"
    assert body["preferred_words"] == "made for you; thoughtful design"
    assert body["avoided_words"] == "cheap; guaranteed results"


def test_business_context_is_user_grounded_and_reports_completeness(
    client: TestClient, session_factory: sessionmaker
) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "context@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    response = client.put(
        profile_url(organization_id),
        headers=alice["headers"],
        json=valid_profile(
            industry_id=ids["fashion"],
            niche="Custom bridal wear",
            products_services="Made-to-measure wedding dresses",
            marketing_goals="Generate qualified enquiries",
        ),
    )
    assert response.status_code == 200, response.text

    context = client.get(
        f"/api/v1/organizations/{organization_id}/business-context", headers=alice["headers"]
    )
    assert context.status_code == 200, context.text
    body = context.json()
    assert body["industry"] == "Fashion"
    assert body["niche"] == "Custom bridal wear"
    assert body["source"] == "user_provided"
    assert body["completeness_percent"] == 100
    assert body["missing_fields"] == []


def test_business_context_requires_existing_profile_and_tenant_membership(client: TestClient) -> None:
    alice = register(client, "context-owner@example.com", "Alice Studio")
    bob = register(client, "context-outsider@example.com", "Bob Bakery")
    alice_context_url = f"/api/v1/organizations/{alice['organization']['id']}/business-context"
    assert client.get(alice_context_url, headers=alice["headers"]).status_code == 404
    assert client.get(alice_context_url, headers=bob["headers"]).status_code == 404


def test_profile_confirmation_is_written_to_activity_log(client: TestClient, session_factory: sessionmaker) -> None:
    ids = seed_categories(session_factory)
    alice = register(client, "confirm-log@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    response = client.put(
        profile_url(organization_id), headers=alice["headers"],
        json=valid_profile(
            industry_id=ids["fashion"], niche="Custom tailoring",
            products_services="Made-to-measure suits", marketing_goals="Generate enquiries",
        ),
    )
    assert response.status_code == 200, response.text
    confirmed = client.post(f"{profile_url(organization_id)}/confirm", headers=alice["headers"])
    assert confirmed.status_code == 200, confirmed.text
    with session_factory() as db:
        from app.models import ActivityLog
        events = db.query(ActivityLog).filter_by(organization_id=UUID(organization_id), action="profile.confirmed").all()
        assert len(events) == 1
        assert events[0].entity_type == "business_profile"


def test_owner_can_save_brand_voice_mode_and_custom_ai_instructions(client: TestClient) -> None:
    alice = register(client, "voice@example.com", "Alice Studio")
    response = client.put(
        profile_url(alice["organization"]["id"]),
        headers=alice["headers"],
        json=valid_profile(brand_voice_mode="manual", custom_ai_instructions="Avoid slang and excessive emojis."),
    )
    assert response.status_code == 200, response.text
    assert response.json()["brand_voice_mode"] == "manual"
    assert response.json()["custom_ai_instructions"] == "Avoid slang and excessive emojis."


def test_invalid_brand_voice_mode_is_rejected(client: TestClient) -> None:
    alice = register(client, "invalid-voice@example.com", "Alice Studio")
    response = client.put(
        profile_url(alice["organization"]["id"]), headers=alice["headers"],
        json=valid_profile(brand_voice_mode="unrestricted"),
    )
    assert response.status_code == 422
