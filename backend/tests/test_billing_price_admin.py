from types import SimpleNamespace

from app.api.v1 import billing
from app.models import BillingPrice, BillingPriceChange


def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "StrongPass123!", "full_name": "Platform Owner",
        "organization_name": "Platform Workspace",
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_platform_admin_can_update_price_and_change_is_audited(client, session_factory, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="owner@example.com"))
    headers = register(client, "owner@example.com")
    with session_factory() as db:
        from app.models import User
        owner = db.query(User).filter(User.email == "owner@example.com").one()
        from datetime import datetime, timezone
        owner.email_verified_at = datetime.now(timezone.utc)
        price = BillingPrice(plan_id="standard", currency="NGN", billing_interval="monthly", amount_minor=750000, enabled=True)
        db.add(price)
        db.commit()

    response = client.put("/api/v1/billing/admin/prices", headers=headers, json={
        "plan_id": "standard", "currency": "NGN", "billing_interval": "monthly",
        "amount_minor": 850000, "enabled": True,
    })
    assert response.status_code == 200
    assert response.json()["amount_minor"] == 850000
    with session_factory() as db:
        changes = db.query(BillingPriceChange).all()
        assert len(changes) == 1
        assert changes[0].previous_amount_minor == 750000
        assert changes[0].new_amount_minor == 850000


def test_non_platform_admin_cannot_change_global_price(client, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="admin@example.com"))
    headers = register(client, "ordinary@example.com")
    response = client.get("/api/v1/billing/admin/prices", headers=headers)
    assert response.status_code == 403


def test_allowlisted_but_unverified_email_cannot_access_platform_prices(client, monkeypatch):
    monkeypatch.setattr(billing, "get_settings", lambda: SimpleNamespace(platform_admin_emails="pending@example.com"))
    headers = register(client, "pending@example.com")
    response = client.get("/api/v1/billing/admin/prices", headers=headers)
    assert response.status_code == 403
