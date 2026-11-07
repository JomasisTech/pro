from fastapi.testclient import TestClient
from uuid import UUID

from app.models import SocialAccount, SocialCredential


def register(client: TestClient, email: str, organization_name: str) -> dict:
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": email.split("@")[0],
        "organization_name": organization_name,
    })
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def test_provider_registry_is_tenant_scoped_and_never_claims_unconfigured_oauth(client: TestClient) -> None:
    owner = register(client, "social-owner@example.com", "Owner Studio")
    outsider = register(client, "social-outsider@example.com", "Other Studio")
    base = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts"
    providers = client.get(f"{base}/providers", headers=owner["headers"])
    assert providers.status_code == 200
    assert {item["key"] for item in providers.json()} == {"instagram", "facebook", "tiktok", "youtube", "linkedin"}
    assert all(item["connection_available"] is False for item in providers.json())
    assert client.get(base, headers=outsider["headers"]).status_code == 404


def test_social_account_disconnect_is_owner_admin_only_and_tenant_scoped(client: TestClient, session_factory) -> None:
    owner = register(client, "social-disconnect@example.com", "Owner Studio")
    outsider = register(client, "social-outsider2@example.com", "Other Studio")
    with session_factory() as db:
        account = SocialAccount(
            organization_id=UUID(owner["organization"]["id"]), provider="instagram",
            provider_account_id="ig-123", account_name="@ownerstudio", granted_scopes=["user_profile"],
        )
        db.add(account); db.commit(); account_id = str(account.id)
    base = f"/api/v1/organizations/{owner['organization']['id']}/social-accounts"
    listed = client.get(base, headers=owner["headers"])
    assert listed.status_code == 200
    assert listed.json()[0]["account_name"] == "@ownerstudio"
    assert client.delete(f"{base}/{account_id}", headers=outsider["headers"]).status_code == 404
    assert client.delete(f"{base}/{account_id}", headers=owner["headers"]).status_code == 204
    assert client.get(base, headers=owner["headers"]).json() == []
    activity = client.get(f"/api/v1/organizations/{owner['organization']['id']}/activity", headers=owner["headers"])
    assert activity.status_code == 200
    assert "social_account.disconnected" in [entry["action"] for entry in activity.json()]
