"""Workspace rename/delete, draft paging and delete permissions, account name, activity filters."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.models import ContentDraft, Membership, Organization, User

PASSWORD = "StrongPass123!"


def register(client: TestClient, email: str, organization_name: str = "Example Studio") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": email.split("@")[0].title(), "organization_name": organization_name},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["headers"] = {"Authorization": f"Bearer {body['access_token']}"}
    return body


def add_member(client: TestClient, session_factory: sessionmaker, organization_id: str, email: str, role: str) -> dict:
    with session_factory() as db:
        user = User(email=email, password_hash=hash_password(PASSWORD), full_name=role.title())
        db.add(Membership(user=user, organization=db.get(Organization, UUID(organization_id)), role=role))
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def org_url(user: dict) -> str:
    return f"/api/v1/organizations/{user['organization']['id']}"


# ---- rename / delete workspace ----------------------------------------------------------------


def test_owner_can_rename_workspace_and_it_is_logged(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    response = client.patch(org_url(owner), headers=owner["headers"], json={"name": "  Better Name  "})
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Better Name"
    assert response.json()["slug"] == owner["organization"]["slug"]
    log = client.get(f"{org_url(owner)}/activity", headers=owner["headers"]).json()
    assert any(entry["action"] == "organization.renamed" for entry in log)


def test_only_owner_can_rename_or_delete(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "owner@example.com")
    admin = add_member(client, session_factory, owner["organization"]["id"], "admin@example.com", "admin")
    assert client.patch(org_url(owner), headers=admin, json={"name": "Hijacked"}).status_code == 403
    assert client.delete(org_url(owner), headers=admin, params={"confirm_name": "Example Studio"}).status_code == 403


def test_other_tenant_cannot_rename_or_delete(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    stranger = register(client, "stranger@example.com", "Other Co")
    assert client.patch(org_url(owner), headers=stranger["headers"], json={"name": "Hijacked"}).status_code == 404
    assert client.delete(org_url(owner), headers=stranger["headers"], params={"confirm_name": "Example Studio"}).status_code == 404


def test_cannot_delete_only_workspace_or_with_wrong_name(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    assert client.delete(org_url(owner), headers=owner["headers"], params={"confirm_name": "wrong"}).status_code == 400
    only = client.delete(org_url(owner), headers=owner["headers"], params={"confirm_name": "Example Studio"})
    assert only.status_code == 400
    assert "only workspace" in only.json()["detail"]


def test_delete_workspace_removes_its_data_but_keeps_the_others(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "owner@example.com")
    second = client.post("/api/v1/organizations", headers=owner["headers"], json={"name": "Second Shop"}).json()
    client.post(f"{org_url(owner)}/drafts", headers=owner["headers"], json={"content": "Hello world", "content_type": "general"})
    client.post(f"/api/v1/organizations/{second['id']}/drafts", headers=owner["headers"], json={"content": "Keep me", "content_type": "general"})

    deleted = client.delete(org_url(owner), headers=owner["headers"], params={"confirm_name": "Example Studio"})
    assert deleted.status_code == 204, deleted.text

    assert client.get(org_url(owner), headers=owner["headers"]).status_code == 404
    names = [org["name"] for org in client.get("/api/v1/organizations", headers=owner["headers"]).json()]
    assert names == ["Second Shop"]
    with session_factory() as db:
        remaining = db.scalars(select(ContentDraft.content)).all()
        assert remaining == ["Keep me"]
        assert db.scalar(select(func.count()).select_from(Membership)) == 1


# ---- drafts ------------------------------------------------------------------------------------


def test_drafts_can_be_paged(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    for index in range(5):
        client.post(f"{org_url(owner)}/drafts", headers=owner["headers"], json={"content": f"Draft number {index}", "content_type": "general"})
    first = client.get(f"{org_url(owner)}/drafts", headers=owner["headers"], params={"limit": 2}).json()
    second = client.get(f"{org_url(owner)}/drafts", headers=owner["headers"], params={"limit": 2, "offset": 2}).json()
    third = client.get(f"{org_url(owner)}/drafts", headers=owner["headers"], params={"limit": 2, "offset": 4}).json()
    ids = [d["id"] for d in first + second + third]
    assert (len(first), len(second), len(third)) == (2, 2, 1)
    assert len(set(ids)) == 5
    assert client.get(f"{org_url(owner)}/drafts", headers=owner["headers"], params={"limit": 101}).status_code == 422


def test_plain_member_can_delete_only_their_own_drafts(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "owner@example.com")
    member = add_member(client, session_factory, owner["organization"]["id"], "member@example.com", "member")
    owners_draft = client.post(f"{org_url(owner)}/drafts", headers=owner["headers"], json={"content": "Owner post", "content_type": "general"}).json()
    members_draft = client.post(f"{org_url(owner)}/drafts", headers=member, json={"content": "Member post", "content_type": "general"}).json()
    assert client.delete(f"{org_url(owner)}/drafts/{owners_draft['id']}", headers=member).status_code == 403
    assert client.delete(f"{org_url(owner)}/drafts/{members_draft['id']}", headers=member).status_code == 204
    # Owners and admins can still delete anyone's draft.
    assert client.delete(f"{org_url(owner)}/drafts/{owners_draft['id']}", headers=owner["headers"]).status_code == 204


# ---- account and activity ---------------------------------------------------------------------


def test_user_can_update_their_display_name(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    response = client.patch("/api/v1/auth/me", headers=owner["headers"], json={"full_name": "  New Name "})
    assert response.status_code == 200, response.text
    assert response.json()["full_name"] == "New Name"
    assert client.get("/api/v1/auth/me", headers=owner["headers"]).json()["full_name"] == "New Name"
    assert client.patch("/api/v1/auth/me", headers=owner["headers"], json={"full_name": "   "}).status_code == 422
    assert client.patch("/api/v1/auth/me", json={"full_name": "x"}).status_code == 401


def test_activity_log_can_be_filtered(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    draft = client.post(f"{org_url(owner)}/drafts", headers=owner["headers"], json={"content": "Hello", "content_type": "general"}).json()
    client.patch(org_url(owner), headers=owner["headers"], json={"name": "Renamed Studio"})
    url = f"{org_url(owner)}/activity"
    drafts_only = client.get(url, headers=owner["headers"], params={"action_prefix": "draft."}).json()
    assert drafts_only and all(item["action"].startswith("draft.") for item in drafts_only)
    orgs_only = client.get(url, headers=owner["headers"], params={"entity_type": "organization"}).json()
    assert orgs_only and all(item["entity_type"] == "organization" for item in orgs_only)
    assert draft["id"] in [item["entity_id"] for item in drafts_only]
    # '%' and '_' are matched literally, not as wildcards.
    assert client.get(url, headers=owner["headers"], params={"action_prefix": "%"}).json() == []
