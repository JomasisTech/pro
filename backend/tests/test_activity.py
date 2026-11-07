from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models import Membership, Organization, User


def register(client: TestClient, email: str, organization_name: str, full_name: str | None = None) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongPass123!",
            "full_name": full_name or email.split("@")[0].title(),
            "organization_name": organization_name,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def org_url(user: dict, suffix: str) -> str:
    return f"/api/v1/organizations/{user['organization']['id']}{suffix}"


def add_member(client: TestClient, session_factory: sessionmaker, organization_id: str, name: str, role: str) -> dict:
    email = f"{name.lower()}@example.com"
    with session_factory() as db:
        user = User(email=email, password_hash=hash_password("StrongPass123!"), full_name=name)
        db.add(Membership(user=user, organization=db.get(Organization, UUID(organization_id)), role=role))
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def log_of(client: TestClient, user: dict, *, include_auth: bool = False) -> list[dict]:
    """Activity entries newest first. Registration/sign-in entries are hidden unless asked for."""
    response = client.get(org_url(user, "/activity"), headers=user["headers"])
    assert response.status_code == 200, response.text
    entries = response.json()
    return entries if include_auth else [entry for entry in entries if not entry["action"].startswith("auth.")]


def test_activity_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000/activity").status_code == 401


def test_draft_lifecycle_is_logged_with_the_acting_member(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery", full_name="Alice Owner")
    bola = add_member(client, session_factory, alice["organization"]["id"], "Bola", "member")

    created = client.post(org_url(alice, "/drafts"), headers=bola, json={"content": "Fresh bread today"}).json()
    draft_url = org_url(alice, f"/drafts/{created['id']}")
    client.patch(draft_url, headers=bola, json={"content": "Fresh bread tomorrow"})
    client.patch(draft_url, headers=alice["headers"], json={"status": "approved"})
    client.delete(draft_url, headers=bola)

    entries = log_of(client, alice)
    by_action = {entry["action"]: entry for entry in entries}
    assert {"draft.created", "draft.updated", "draft.approved", "draft.deleted"} <= set(by_action)
    assert by_action["draft.created"]["actor_name"] == "Bola"
    assert by_action["draft.deleted"]["actor_name"] == "Bola"
    assert by_action["draft.approved"]["actor_name"] == "Alice Owner"
    assert "Fresh bread tomorrow" in by_action["draft.deleted"]["summary"]
    assert all(entry["entity_id"] == created["id"] for entry in entries if entry["entity_type"] == "draft")


def test_log_entries_survive_deleting_the_draft(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": "Gone soon"}).json()
    client.delete(org_url(alice, f"/drafts/{draft['id']}"), headers=alice["headers"])
    actions = [entry["action"] for entry in log_of(client, alice)]
    assert "draft.created" in actions and "draft.deleted" in actions


def test_unchanged_updates_are_not_logged(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": "Same text"}).json()
    client.patch(org_url(alice, f"/drafts/{draft['id']}"), headers=alice["headers"], json={"content": "Same text"})
    client.patch(org_url(alice, f"/drafts/{draft['id']}"), headers=alice["headers"], json={"status": "draft"})
    assert [entry["action"] for entry in log_of(client, alice)] == ["draft.created"]


def test_rejected_changes_are_not_logged(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bola = add_member(client, session_factory, alice["organization"]["id"], "Bola", "member")
    draft = client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": "Text"}).json()
    assert client.patch(org_url(alice, f"/drafts/{draft['id']}"), headers=bola, json={"status": "approved"}).status_code == 403
    assert "draft.approved" not in [entry["action"] for entry in log_of(client, alice)]


def test_profile_and_workspace_changes_are_logged(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    profile = {"business_name": "Alice Bakery", "language": "en"}
    client.put(org_url(alice, "/profile"), headers=alice["headers"], json=profile)
    client.put(org_url(alice, "/profile"), headers=alice["headers"], json=profile)
    created = client.post("/api/v1/organizations", headers=alice["headers"], json={"name": "Second Shop"}).json()

    actions = [entry["action"] for entry in log_of(client, alice)]
    assert actions.count("profile.created") == 1 and actions.count("profile.updated") == 1
    second = client.get(f"/api/v1/organizations/{created['id']}/activity", headers=alice["headers"]).json()
    assert [entry["action"] for entry in second] == ["organization.created"]


def test_plain_members_cannot_read_the_log(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bola = add_member(client, session_factory, alice["organization"]["id"], "Bola", "member")
    assert client.get(org_url(alice, "/activity"), headers=bola).status_code == 403


def test_other_tenants_cannot_read_the_log(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bob = register(client, "bob@example.com", "Bob Studio")
    client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": "Secret plan"})
    response = client.get(org_url(alice, "/activity"), headers=bob["headers"])
    assert response.status_code == 404 and "Secret" not in response.text
    assert all("Secret" not in entry["summary"] for entry in log_of(client, bob))


def test_log_is_read_only_and_paginated(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    for index in range(3):
        client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": f"Draft {index}"})
    url = org_url(alice, "/activity")
    assert client.post(url, headers=alice["headers"], json={}).status_code == 405
    assert client.delete(url, headers=alice["headers"]).status_code == 405
    drafts = f"{url}?entity_type=draft"
    assert len(client.get(f"{drafts}&limit=2", headers=alice["headers"]).json()) == 2
    assert len(client.get(f"{drafts}&limit=2&offset=2", headers=alice["headers"]).json()) == 1
    assert client.get(f"{url}?limit=0", headers=alice["headers"]).status_code == 422


def test_registration_and_sign_in_are_logged(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    assert [entry["action"] for entry in log_of(client, alice, include_auth=True)] == ["auth.registered"]

    login = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "StrongPass123!"})
    assert login.status_code == 200, login.text
    entries = log_of(client, alice, include_auth=True)
    assert [entry["action"] for entry in entries] == ["auth.login", "auth.registered"]
    assert entries[0]["actor_name"] == "Alice" and "email and password" in entries[0]["summary"]


def test_sign_in_is_logged_in_every_workspace_the_user_belongs_to(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    second = client.post("/api/v1/organizations", headers=alice["headers"], json={"name": "Second Shop"}).json()
    client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "StrongPass123!"})
    second_log = client.get(f"/api/v1/organizations/{second['id']}/activity", headers=alice["headers"]).json()
    assert "auth.login" in [entry["action"] for entry in second_log]


def test_failed_sign_in_is_not_logged(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    assert client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "WrongPass123!"}).status_code == 401
    assert [entry["action"] for entry in log_of(client, alice, include_auth=True)] == ["auth.registered"]


def test_activity_can_be_filtered_by_action_prefix(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    client.post(org_url(alice, "/drafts"), headers=alice["headers"], json={"content": "Hello"})
    response = client.get(org_url(alice, "/activity?action_prefix=auth."), headers=alice["headers"])
    assert [entry["action"] for entry in response.json()] == ["auth.registered"]
