from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models import Membership, Organization, User


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


def base(user: dict) -> str:
    return f"/api/v1/organizations/{user['organization']['id']}/drafts"


def member_headers(client: TestClient, session_factory: sessionmaker, organization_id: str, role: str) -> dict:
    email = f"{role}@example.com"
    with session_factory() as db:
        user = User(email=email, password_hash=hash_password("StrongPass123!"), full_name=role.title())
        db.add(Membership(user=user, organization=db.get(Organization, UUID(organization_id)), role=role))
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create(client: TestClient, user: dict, content: str = "Fresh bread! #bakery") -> dict:
    response = client.post(base(user), headers=user["headers"], json={"content": content, "topic": " Loaves "})
    assert response.status_code == 201, response.text
    return response.json()


def test_drafts_require_authentication(client: TestClient) -> None:
    url = "/api/v1/organizations/00000000-0000-0000-0000-000000000000/drafts"
    assert client.get(url).status_code == 401
    assert client.post(url, json={"content": "x"}).status_code == 401


def test_create_and_list_drafts_newest_first(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    first = create(client, alice, "First")
    second = create(client, alice, "Second")
    assert first["status"] == "draft" and first["topic"] == "Loaves" and first["content_type"] == "general"
    listed = client.get(base(alice), headers=alice["headers"]).json()
    assert {item["id"] for item in listed} == {first["id"], second["id"]}


def test_invalid_draft_input_is_rejected(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    for body in ({"content": "   "}, {"content": "x" * 12001}, {"content": "ok", "content_type": "nope"}, {}):
        assert client.post(base(alice), headers=alice["headers"], json=body).status_code == 422


def test_edit_text_and_delete(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = create(client, alice)
    url = f"{base(alice)}/{draft['id']}"
    edited = client.patch(url, headers=alice["headers"], json={"content": " New text "})
    assert edited.status_code == 200 and edited.json()["content"] == "New text"
    assert client.delete(url, headers=alice["headers"]).status_code == 204
    assert client.delete(url, headers=alice["headers"]).status_code == 404
    assert client.get(base(alice), headers=alice["headers"]).json() == []


def test_empty_patch_is_rejected(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = create(client, alice)
    assert client.patch(f"{base(alice)}/{draft['id']}", headers=alice["headers"], json={}).status_code == 422


def test_owner_can_approve_and_editing_resets_approval(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = create(client, alice)
    url = f"{base(alice)}/{draft['id']}"
    approved = client.patch(url, headers=alice["headers"], json={"status": "approved"})
    assert approved.json()["status"] == "approved"
    assert client.get(f"{base(alice)}?status=approved", headers=alice["headers"]).json()[0]["id"] == draft["id"]
    edited = client.patch(url, headers=alice["headers"], json={"content": "Changed after approval"})
    assert edited.json()["status"] == "draft"


def test_plain_member_can_edit_but_not_approve(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    draft = create(client, alice)
    headers = member_headers(client, session_factory, alice["organization"]["id"], "member")
    url = f"{base(alice)}/{draft['id']}"
    assert client.patch(url, headers=headers, json={"content": "Member edit"}).status_code == 200
    assert client.patch(url, headers=headers, json={"status": "approved"}).status_code == 403
    assert client.get(base(alice), headers=headers).status_code == 200


def test_other_tenant_cannot_see_or_change_drafts(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Bakery")
    bob = register(client, "bob@example.com", "Bob Studio")
    draft = create(client, alice)
    url = f"{base(alice)}/{draft['id']}"
    assert client.get(base(alice), headers=bob["headers"]).status_code == 404
    assert client.patch(url, headers=bob["headers"], json={"content": "hijack"}).status_code == 404
    assert client.delete(url, headers=bob["headers"]).status_code == 404
    # Bob's own organization cannot reach Alice's draft id either.
    assert client.patch(f"{base(bob)}/{draft['id']}", headers=bob["headers"], json={"content": "x"}).status_code == 404
    assert client.get(base(alice), headers=alice["headers"]).json()[0]["content"] == draft["content"]
