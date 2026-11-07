from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.v1 import auth, billing
from app.core.security import hash_password
from app.models import Membership, Organization, User


def _demo_settings(enabled=True):
    return SimpleNamespace(
        demo_mode=enabled,
        demo_email="customer-demo@example.com",
        demo_admin_email="platform-owner-demo@example.com",
        demo_password="pass",
        platform_admin_emails="",
        trusted_proxy_count=0,
        email_verification_required=False,
    )


def test_demo_owner_can_open_admin_dashboard_without_mfa(client, session_factory, monkeypatch):
    settings = _demo_settings()
    monkeypatch.setattr(auth, "_settings", settings)
    monkeypatch.setattr(billing, "get_settings", lambda: settings)
    with session_factory() as db:
        user = User(
            email="platform-owner-demo@example.com", full_name="Demo Owner", password_hash=hash_password("pass"),
            has_password=True, is_active=True, email_verified_at=datetime.now(timezone.utc),
        )
        organization = Organization(name="Demo Business", slug="demo-business", plan="premium")
        db.add_all([user, organization])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()

    login = client.post("/api/v1/auth/demo-admin")
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    dashboard = client.get("/api/v1/platform-admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert dashboard.status_code == 200, dashboard.text


def test_demo_admin_login_is_disabled_outside_demo_mode(client, monkeypatch):
    monkeypatch.setattr(auth, "_settings", _demo_settings(enabled=False))
    response = client.post("/api/v1/auth/demo-admin")
    assert response.status_code == 404


def test_demo_session_does_not_grant_admin_access_to_other_users(client, session_factory, monkeypatch):
    settings = _demo_settings()
    monkeypatch.setattr(auth, "_settings", settings)
    monkeypatch.setattr(billing, "get_settings", lambda: settings)
    with session_factory() as db:
        user = User(
            email="customer@example.com", full_name="Customer", password_hash=hash_password("pass"),
            has_password=True, is_active=True, email_verified_at=datetime.now(timezone.utc),
        )
        organization = Organization(name="Customer Business", slug="customer-business", plan="premium")
        db.add_all([user, organization])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()
        from app.core.security import create_access_token
        token = create_access_token(user.id, user.token_version)
    response = client.get("/api/v1/platform-admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_customer_demo_identity_cannot_access_platform_admin(client, session_factory, monkeypatch):
    settings = _demo_settings()
    monkeypatch.setattr(auth, "_settings", settings)
    monkeypatch.setattr(billing, "get_settings", lambda: settings)
    with session_factory() as db:
        user = User(
            email="customer-demo@example.com", full_name="Demo Customer", password_hash=hash_password("pass"),
            has_password=True, is_active=True, email_verified_at=datetime.now(timezone.utc),
        )
        organization = Organization(name="Customer Demo", slug="customer-demo", plan="premium")
        db.add_all([user, organization])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()
        from app.core.security import create_access_token
        token = create_access_token(user.id, user.token_version)
    response = client.get("/api/v1/platform-admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403



def test_admin_demo_identity_cannot_password_login_through_customer_route(client, session_factory, monkeypatch):
    settings = _demo_settings()
    monkeypatch.setattr(auth, "_settings", settings)
    with session_factory() as db:
        user = User(
            email="platform-owner-demo@example.com", full_name="Demo Owner",
            password_hash=hash_password("a-random-unavailable-password"), has_password=False,
            is_active=True, email_verified_at=datetime.now(timezone.utc),
        )
        organization = Organization(name="Owner Demo", slug="owner-demo", plan="premium")
        db.add_all([user, organization])
        db.flush()
        db.add(Membership(user_id=user.id, organization_id=organization.id, role="owner"))
        db.commit()
    response = client.post("/api/v1/auth/login", json={"email": "platform-owner-demo@example.com", "password": "pass"})
    assert response.status_code == 401

