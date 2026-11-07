from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from uuid import UUID

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


def add_member(session_factory: sessionmaker, organization_id: str, email: str, role: str) -> dict:
    """Create a second user directly in the database and attach them to an organization."""
    from uuid import UUID

    with session_factory() as db:
        user = User(email=email, password_hash=hash_password("StrongPass123!"), full_name="Added Member")
        organization = db.get(Organization, UUID(organization_id))
        db.add(Membership(user=user, organization=organization, role=role))
        db.commit()
    return {"email": email, "password": "StrongPass123!"}


def sign_in(client: TestClient, credentials: dict) -> dict:
    response = client.post("/api/v1/auth/login", json=credentials)
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_organization_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/organizations").status_code == 401
    assert client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000").status_code == 401


def test_user_lists_only_their_own_organizations(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    register(client, "bob@example.com", "Bob Bakery")

    response = client.get("/api/v1/organizations", headers=alice["headers"])
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == ["Alice Studio"]
    assert response.json()[0]["role"] == "owner"


def test_member_can_read_their_organization(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    response = client.get(f"/api/v1/organizations/{alice['organization']['id']}", headers=alice["headers"])
    assert response.status_code == 200
    assert response.json()["name"] == "Alice Studio"


def test_other_tenants_organization_is_hidden_with_404(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    bob = register(client, "bob@example.com", "Bob Bakery")

    detail = client.get(f"/api/v1/organizations/{bob['organization']['id']}", headers=alice["headers"])
    members = client.get(f"/api/v1/organizations/{bob['organization']['id']}/members", headers=alice["headers"])
    assert detail.status_code == 404
    assert members.status_code == 404
    assert "Bob" not in detail.text


def test_unknown_organization_id_returns_404_and_invalid_id_returns_422(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    missing = client.get("/api/v1/organizations/00000000-0000-0000-0000-000000000000", headers=alice["headers"])
    invalid = client.get("/api/v1/organizations/not-a-uuid", headers=alice["headers"])
    assert missing.status_code == 404
    assert invalid.status_code == 422


def test_owner_can_list_members_but_plain_member_cannot(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    member_credentials = add_member(session_factory, organization_id, "sam@example.com", "member")

    owner_view = client.get(f"/api/v1/organizations/{organization_id}/members", headers=alice["headers"])
    assert owner_view.status_code == 200
    assert {(m["email"], m["role"]) for m in owner_view.json()} == {
        ("alice@example.com", "owner"),
        ("sam@example.com", "member"),
    }
    assert all("password" not in key for m in owner_view.json() for key in m)

    sam_headers = sign_in(client, member_credentials)
    assert client.get(f"/api/v1/organizations/{organization_id}", headers=sam_headers).status_code == 200
    forbidden = client.get(f"/api/v1/organizations/{organization_id}/members", headers=sam_headers)
    assert forbidden.status_code == 403


def test_admin_role_can_list_members(client: TestClient, session_factory: sessionmaker) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    organization_id = alice["organization"]["id"]
    admin_credentials = add_member(session_factory, organization_id, "ada@example.com", "admin")
    admin_headers = sign_in(client, admin_credentials)
    assert client.get(f"/api/v1/organizations/{organization_id}/members", headers=admin_headers).status_code == 200


def test_creating_an_organization_requires_authentication(client: TestClient) -> None:
    assert client.post("/api/v1/organizations", json={"name": "New Shop"}).status_code == 401


def test_user_can_create_another_workspace_and_becomes_its_owner(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    created = client.post("/api/v1/organizations", json={"name": "  Alice Bakery  "}, headers=alice["headers"])
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Alice Bakery"
    assert body["role"] == "owner"
    assert body["id"] != alice["organization"]["id"]

    names = {item["name"] for item in client.get("/api/v1/organizations", headers=alice["headers"]).json()}
    assert names == {"Alice Studio", "Alice Bakery"}
    members = client.get(f"/api/v1/organizations/{body['id']}/members", headers=alice["headers"])
    assert members.status_code == 200
    assert [m["email"] for m in members.json()] == ["alice@example.com"]


def test_new_workspace_is_invisible_to_other_users(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    bob = register(client, "bob@example.com", "Bob Bakery")
    created = client.post("/api/v1/organizations", json={"name": "Alice Secret"}, headers=alice["headers"]).json()

    assert client.get(f"/api/v1/organizations/{created['id']}", headers=bob["headers"]).status_code == 404
    assert "Alice Secret" not in client.get("/api/v1/organizations", headers=bob["headers"]).text


def test_same_workspace_name_is_allowed_with_unique_slugs(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    first = client.post("/api/v1/organizations", json={"name": "Twin"}, headers=alice["headers"]).json()
    second = client.post("/api/v1/organizations", json={"name": "Twin"}, headers=alice["headers"]).json()
    assert first["slug"] != second["slug"]


def test_workspace_name_is_validated(client: TestClient) -> None:
    alice = register(client, "alice@example.com", "Alice Studio")
    for bad in ({"name": ""}, {"name": " a "}, {"name": "x" * 161}, {}):
        assert client.post("/api/v1/organizations", json=bad, headers=alice["headers"]).status_code == 422


def test_workspace_count_is_limited_per_user(client: TestClient, monkeypatch) -> None:
    from app.api.v1 import organizations as organizations_module

    monkeypatch.setattr(organizations_module, "MAX_ORGANIZATIONS_PER_USER", 2)
    alice = register(client, "alice@example.com", "Alice Studio")
    assert client.post("/api/v1/organizations", json={"name": "Second"}, headers=alice["headers"]).status_code == 201
    over = client.post("/api/v1/organizations", json={"name": "Third"}, headers=alice["headers"])
    assert over.status_code == 400
    assert "maximum" in over.json()["detail"]



def test_owner_can_change_member_role_and_remove_member(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "owner-roles@example.com", "Role Workspace")
    organization_id = owner["organization"]["id"]
    add_member(session_factory, organization_id, "role-member@example.com", "member")
    member_id = None
    from sqlalchemy import select
    with session_factory() as db:
        member_id = str(db.scalar(select(Membership).where(Membership.organization_id == UUID(organization_id), Membership.role == "member")).user_id)

    changed = client.patch(
        f"/api/v1/organizations/{organization_id}/members/{member_id}",
        headers=owner["headers"], json={"role": "admin"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["role"] == "admin"

    removed = client.delete(
        f"/api/v1/organizations/{organization_id}/members/{member_id}", headers=owner["headers"]
    )
    assert removed.status_code == 204
    assert client.get(f"/api/v1/organizations/{organization_id}/members", headers=owner["headers"]).json() == [
        {"user_id": owner["user"]["id"], "email": "owner-roles@example.com", "full_name": "Owner-Roles", "role": "owner"}
    ]


def test_only_owner_can_manage_roles_and_owner_cannot_be_demoted(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "owner-protect@example.com", "Protected Workspace")
    organization_id = owner["organization"]["id"]
    admin_credentials = add_member(session_factory, organization_id, "admin-protect@example.com", "admin")
    admin_headers = sign_in(client, admin_credentials)
    with session_factory() as db:
        owner_id = str(db.scalar(select(Membership).where(
            Membership.organization_id == UUID(organization_id), Membership.role == "owner"
        )).user_id)

    forbidden = client.patch(
        f"/api/v1/organizations/{organization_id}/members/{owner_id}",
        headers=admin_headers, json={"role": "member"},
    )
    assert forbidden.status_code == 403
    protected = client.patch(
        f"/api/v1/organizations/{organization_id}/members/{owner_id}",
        headers=owner["headers"], json={"role": "member"},
    )
    assert protected.status_code == 400


def test_owner_can_invite_matching_email_and_invitee_can_accept(client: TestClient, monkeypatch) -> None:
    import re
    from app.api.v1 import organizations as organizations_module
    sent = []
    monkeypatch.setattr(organizations_module, "send_email", lambda *args: sent.append(args))
    owner = register(client, "invite-owner@example.com", "Invite Workspace")
    invite = client.post(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations",
        headers=owner["headers"], json={"email": "new-member@example.com", "role": "member"},
    )
    assert invite.status_code == 201, invite.text
    assert sent and sent[0][1] == "new-member@example.com"
    token = re.search(r"token=([A-Za-z0-9_-]+)", sent[0][3]).group(1)
    member = register(client, "new-member@example.com", "Personal Workspace")
    accepted = client.post("/api/v1/organizations/invitations/accept", headers=member["headers"], json={"token": token})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["id"] == owner["organization"]["id"]
    assert accepted.json()["role"] == "member"
    listed = client.get(f"/api/v1/organizations/{owner['organization']['id']}/members", headers=owner["headers"])
    assert {item["email"] for item in listed.json()} == {"invite-owner@example.com", "new-member@example.com"}


def test_invitation_cannot_be_accepted_by_wrong_email_or_twice(client: TestClient, monkeypatch) -> None:
    import re
    from app.api.v1 import organizations as organizations_module
    sent = []
    monkeypatch.setattr(organizations_module, "send_email", lambda *args: sent.append(args))
    owner = register(client, "invite-owner2@example.com", "Invite Workspace 2")
    response = client.post(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations",
        headers=owner["headers"], json={"email": "target@example.com"},
    )
    assert response.status_code == 201
    token = re.search(r"token=([A-Za-z0-9_-]+)", sent[0][3]).group(1)
    wrong = register(client, "wrong@example.com", "Wrong Workspace")
    denied = client.post("/api/v1/organizations/invitations/accept", headers=wrong["headers"], json={"token": token})
    assert denied.status_code == 403
    target = register(client, "target@example.com", "Target Workspace")
    path = "/api/v1/organizations/invitations/accept"
    assert client.post(path, headers=target["headers"], json={"token": token}).status_code == 200
    assert client.post(path, headers=target["headers"], json={"token": token}).status_code == 400


def test_admin_cannot_invite_another_admin(client: TestClient, session_factory: sessionmaker, monkeypatch) -> None:
    owner = register(client, "invite-admin-owner@example.com", "Admin Invite Workspace")
    admin_credentials = add_member(session_factory, owner["organization"]["id"], "invite-admin@example.com", "admin")
    admin_headers = sign_in(client, admin_credentials)
    response = client.post(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations",
        headers=admin_headers, json={"email": "another-admin@example.com", "role": "admin"},
    )
    assert response.status_code == 403


def test_admin_can_list_and_revoke_pending_invitation(client: TestClient, session_factory: sessionmaker) -> None:
    owner = register(client, "invite-admin-ui-owner@example.com", "Invitation Admin UI")
    admin_credentials = add_member(session_factory, owner["organization"]["id"], "invite-admin-ui@example.com", "admin")
    admin_headers = sign_in(client, admin_credentials)
    created = client.post(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations",
        headers=owner["headers"], json={"email": "pending-ui@example.com", "role": "member"},
    )
    assert created.status_code == 201
    listed = client.get(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations", headers=admin_headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["email"] == "pending-ui@example.com"
    invitation_id = listed.json()[0]["id"]
    revoked = client.delete(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations/{invitation_id}",
        headers=admin_headers,
    )
    assert revoked.status_code == 204
    assert client.get(
        f"/api/v1/organizations/{owner['organization']['id']}/invitations", headers=admin_headers,
    ).json() == []


def _invite(client: TestClient, owner: dict, monkeypatch, email: str = "resend-guest@example.com", role: str = "member"):
    import re
    from app.api.v1 import organizations as organizations_module
    sent: list = []
    monkeypatch.setattr(organizations_module, "send_email", lambda *args: sent.append(args))
    base = f"/api/v1/organizations/{owner['organization']['id']}/invitations"
    assert client.post(base, headers=owner["headers"], json={"email": email, "role": role}).status_code == 201
    item = client.get(base, headers=owner["headers"]).json()[0]
    token = lambda: re.search(r"token=([A-Za-z0-9_-]+)", sent[-1][3]).group(1)  # noqa: E731
    return base, item, sent, token


def test_invitation_list_reports_status(client: TestClient, monkeypatch) -> None:
    owner = register(client, "inv-status-owner@example.com", "Status Space")
    _, item, _, _ = _invite(client, owner, monkeypatch)
    assert item["status"] == "pending" and item["last_sent_at"]


def test_resend_replaces_link_respects_cooldown_and_extends_expiry(client: TestClient, session_factory: sessionmaker, monkeypatch) -> None:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import update
    from app.models import OrganizationInvitation
    owner = register(client, "inv-resend-owner@example.com", "Resend Space")
    base, item, sent, token = _invite(client, owner, monkeypatch)
    first = token()
    too_soon = client.post(f"{base}/{item['id']}/resend", headers=owner["headers"])
    assert too_soon.status_code == 429 and "Retry-After" in too_soon.headers
    with session_factory() as db:
        db.execute(update(OrganizationInvitation).values(last_sent_at=None, expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
        db.commit()
    assert client.get(base, headers=owner["headers"]).json()[0]["status"] == "expired"
    assert client.post(f"{base}/{item['id']}/resend", headers=owner["headers"]).status_code == 200
    second = token()
    assert first != second and client.get(base, headers=owner["headers"]).json()[0]["status"] == "pending"
    guest = register(client, "resend-guest@example.com", "Guest Space")
    accept = "/api/v1/organizations/invitations/accept"
    assert client.post(accept, headers=guest["headers"], json={"token": first}).status_code == 400
    assert client.post(accept, headers=guest["headers"], json={"token": second}).status_code == 200
    assert client.post(f"{base}/{item['id']}/resend", headers=owner["headers"]).status_code == 409


def test_accepting_an_invitation_verifies_the_email_address(client: TestClient, session_factory: sessionmaker, monkeypatch) -> None:
    owner = register(client, "inv-verify-owner@example.com", "Verify Space")
    _, _, _, token = _invite(client, owner, monkeypatch, "verify-guest@example.com")
    guest = register(client, "verify-guest@example.com", "Verify Guest Space")
    assert client.post("/api/v1/organizations/invitations/accept", headers=guest["headers"], json={"token": token()}).status_code == 200
    with session_factory() as db:
        assert db.scalar(select(User.email_verified_at).where(User.email == "verify-guest@example.com")) is not None


def test_admins_cannot_resend_or_revoke_admin_invitations_and_members_cannot_resend(client: TestClient, session_factory: sessionmaker, monkeypatch) -> None:
    owner = register(client, "inv-guard-owner@example.com", "Guard Space")
    base, item, _, _ = _invite(client, owner, monkeypatch, "future-admin@example.com", "admin")
    org = owner["organization"]["id"]
    admin = sign_in(client, add_member(session_factory, org, "guard-admin@example.com", "admin"))
    member = sign_in(client, add_member(session_factory, org, "guard-member@example.com", "member"))
    assert client.post(f"{base}/{item['id']}/resend", headers=admin).status_code == 403
    assert client.delete(f"{base}/{item['id']}", headers=admin).status_code == 403
    assert client.post(f"{base}/{item['id']}/resend", headers=member).status_code == 403
