from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models import BusinessProfileVersion, IndustryCategory


def register(client: TestClient, email: str, organization_name: str) -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": email.split("@")[0],
        "organization_name": organization_name,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def test_products_crud_and_primary_selection_are_tenant_scoped(client: TestClient) -> None:
    alice = register(client, "products-alice@example.com", "Alice Studio")
    bob = register(client, "products-bob@example.com", "Bob Bakery")
    alice_id = alice["organization"]["id"]
    bob_id = bob["organization"]["id"]
    alice_url = f"/api/v1/organizations/{alice_id}/products"
    bob_url = f"/api/v1/organizations/{bob_id}/products"

    created = client.post(alice_url, headers=alice["headers"], json={
        "name": "Bridal gown", "description": "Custom made", "price_amount": 250000,
        "price_currency": "ngn", "is_primary": True,
    })
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]
    assert created.json()["price_currency"] == "NGN"
    assert created.json()["is_primary"] is True

    second = client.post(alice_url, headers=alice["headers"], json={"name": "Alterations", "is_primary": True})
    assert second.status_code == 201
    listed = client.get(alice_url, headers=alice["headers"]).json()
    assert len(listed) == 2
    assert sum(item["is_primary"] for item in listed) == 1
    assert listed[0]["name"] == "Alterations"

    # A different tenant cannot read, edit, or delete the product.
    assert client.patch(f"{bob_url}/{product_id}", headers=bob["headers"], json={"name": "Hijack"}).status_code == 404
    assert client.delete(f"{bob_url}/{product_id}", headers=bob["headers"]).status_code == 404

    updated = client.patch(f"{alice_url}/{product_id}", headers=alice["headers"], json={"is_active": False})
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert client.delete(f"{alice_url}/{product_id}", headers=alice["headers"]).status_code == 204
    activity = client.get(f"/api/v1/organizations/{alice_id}/activity", headers=alice["headers"])
    assert activity.status_code == 200
    actions = [entry["action"] for entry in activity.json()]
    assert actions.count("business_product.created") == 2
    assert "business_product.updated" in actions
    assert "business_product.primary_changed" in actions
    assert "business_product.deleted" in actions
    assert all(entry["entity_type"] == "business_product" for entry in activity.json() if not entry["action"].startswith("auth."))


def test_product_validation_and_member_write_restrictions(client: TestClient) -> None:
    alice = register(client, "products-validation@example.com", "Alice Studio")
    url = f"/api/v1/organizations/{alice['organization']['id']}/products"
    assert client.post(url, headers=alice["headers"], json={"name": " "}).status_code == 422
    assert client.post(url, headers=alice["headers"], json={"name": "Service", "price_amount": -1}).status_code == 422


def test_profile_confirmation_requires_complete_profile_and_creates_history(
    client: TestClient, session_factory: sessionmaker
) -> None:
    alice = register(client, "confirm-profile@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    profile_url = f"/api/v1/organizations/{organization_id}/profile"
    confirm_url = f"{profile_url}/confirm"
    incomplete = client.put(profile_url, headers=alice["headers"], json={"business_name": "Alice Studio"})
    assert incomplete.status_code == 200
    assert client.post(confirm_url, headers=alice["headers"]).status_code == 409

    with session_factory() as db:
        industry = IndustryCategory(slug="confirm-industry", name="Fashion")
        db.add(industry)
        db.commit()
        industry_id = str(industry.id)

    complete = client.put(profile_url, headers=alice["headers"], json={
        "business_name": "Alice Studio", "industry_id": industry_id,
        "niche": "Custom bridal wear", "description": "Made-to-measure gowns",
        "products_services": "Wedding dresses", "marketing_goals": "Generate enquiries",
    })
    assert complete.status_code == 200
    assert complete.json()["profile_version"] == 2

    confirmed = client.post(confirm_url, headers=alice["headers"])
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["message"] == "Business profile confirmed"
    fetched = client.get(profile_url, headers=alice["headers"]).json()
    assert fetched["confirmed_at"] is not None
    assert fetched["onboarding_completed_at"] is not None

    history = client.get(f"{profile_url}/versions", headers=alice["headers"])
    assert history.status_code == 200
    assert [item["action"] for item in history.json()] == ["confirmed", "updated", "created"]

    # Any later profile edit invalidates confirmation and requires a fresh review.
    changed = client.put(profile_url, headers=alice["headers"], json={
        "business_name": "Alice Atelier", "industry_id": industry_id,
        "niche": "Custom bridal wear", "description": "Made-to-measure gowns",
        "products_services": "Wedding dresses", "marketing_goals": "Generate enquiries",
    })
    assert changed.status_code == 200
    assert changed.json()["confirmed_at"] is None
    assert client.get(f"{profile_url}/versions", headers=alice["headers"]).json()[0]["action"] == "updated"


def test_profile_confirmation_and_history_are_protected(client: TestClient) -> None:
    alice = register(client, "confirm-owner@example.com", "Alice Studio")
    bob = register(client, "confirm-outsider@example.com", "Bob Bakery")
    url = f"/api/v1/organizations/{alice['organization']['id']}/profile"
    assert client.post(f"{url}/confirm", headers=bob["headers"]).status_code == 404
    assert client.get(f"{url}/versions", headers=bob["headers"]).status_code == 404


def test_structured_product_satisfies_offer_requirement_for_confirmation_and_context(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "structured-offer@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    with session_factory() as db:
        industry = IndustryCategory(slug="structured-offer-industry", name="Fashion")
        db.add(industry)
        db.commit()
        industry_id = str(industry.id)

    profile_url = f"/api/v1/organizations/{organization_id}/profile"
    saved = client.put(profile_url, headers=alice["headers"], json={
        "business_name": "Alice Studio", "industry_id": industry_id,
        "niche": "Bridal fashion", "description": "Custom bridal gowns",
        "marketing_goals": "Generate enquiries",
    })
    assert saved.status_code == 200
    product_url = f"/api/v1/organizations/{organization_id}/products"
    product = client.post(product_url, headers=alice["headers"], json={"name": "Made-to-measure gown"})
    assert product.status_code == 201

    context = client.get(f"/api/v1/organizations/{organization_id}/business-context", headers=alice["headers"])
    assert context.status_code == 200
    assert context.json()["completeness_percent"] == 100
    assert context.json()["products"][0]["name"] == "Made-to-measure gown"
    assert client.post(f"{profile_url}/confirm", headers=alice["headers"]).status_code == 200
