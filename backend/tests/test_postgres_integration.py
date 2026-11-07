"""Real PostgreSQL application workflow smoke test; enabled in CI via TEST_POSTGRES_URL."""
import os
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models import SocialAccount


def _disposable_postgres_engine():
    """Return an engine only for an explicitly approved disposable test DB.

    These integration tests drop and recreate every table in Base.metadata.
    The opt-in flag, local/test host, and test database name are deliberate
    safeguards against accidentally pointing them at a developer or live DB.
    """
    database_url = os.environ["TEST_POSTGRES_URL"]
    if os.getenv("TEST_POSTGRES_ALLOW_DESTRUCTIVE") != "1":
        raise RuntimeError(
            "Destructive PostgreSQL tests require TEST_POSTGRES_ALLOW_DESTRUCTIVE=1 "
            "and a disposable test database."
        )
    parsed = make_url(database_url)
    if parsed.get_backend_name() != "postgresql":
        raise RuntimeError("TEST_POSTGRES_URL must use PostgreSQL.")
    if parsed.host not in {"localhost", "127.0.0.1", "postgres"}:
        raise RuntimeError("Destructive PostgreSQL tests are restricted to a local test host.")
    if parsed.database != "ci_db" and not (parsed.database or "").startswith("test_"):
        raise RuntimeError(
            "Destructive PostgreSQL tests require database name 'ci_db' or a 'test_' prefix."
        )
    return create_engine(parsed, pool_pre_ping=True)


def test_destructive_postgres_helper_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_POSTGRES_URL", "postgresql+psycopg://tester:secret@localhost:5432/ci_db")
    monkeypatch.delenv("TEST_POSTGRES_ALLOW_DESTRUCTIVE", raising=False)
    with pytest.raises(RuntimeError, match="TEST_POSTGRES_ALLOW_DESTRUCTIVE=1"):
        _disposable_postgres_engine()


def test_destructive_postgres_helper_rejects_non_test_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_POSTGRES_URL", "postgresql+psycopg://tester:secret@localhost:5432/production")
    monkeypatch.setenv("TEST_POSTGRES_ALLOW_DESTRUCTIVE", "1")
    with pytest.raises(RuntimeError, match="database name.*ci_db"):
        _disposable_postgres_engine()


def test_destructive_postgres_helper_rejects_remote_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_POSTGRES_URL", "postgresql+psycopg://tester:secret@db.example.com:5432/ci_db")
    monkeypatch.setenv("TEST_POSTGRES_ALLOW_DESTRUCTIVE", "1")
    with pytest.raises(RuntimeError, match="local test host"):
        _disposable_postgres_engine()


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Set TEST_POSTGRES_URL for PostgreSQL workflow tests")
def test_registration_and_scheduling_workflow_on_postgresql() -> None:
    engine = _disposable_postgres_engine()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            registered = client.post("/api/v1/auth/register", json={
                "email": "postgres-workflow@example.com", "password": "StrongPass123!",
                "full_name": "Postgres Workflow", "organization_name": "Postgres Workspace",
            })
            assert registered.status_code == 201, registered.text
            body = registered.json()
            headers = {"Authorization": f"Bearer {body['access_token']}"}
            organization_id = body["organization"]["id"]
            with factory() as db:
                account = SocialAccount(
                    organization_id=UUID(organization_id), provider="facebook", provider_account_id="pg-page-1",
                    account_name="Postgres Page", account_type="page", granted_scopes=["pages_manage_posts"],
                )
                db.add(account)
                db.commit()
                account_id = str(account.id)
            scheduled = client.post(f"/api/v1/organizations/{organization_id}/scheduled-posts", headers=headers, json={
                "social_account_id": account_id, "provider": "facebook", "title": "Postgres integration",
                "content": "Persist this through PostgreSQL",
                "scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            })
            assert scheduled.status_code == 201, scheduled.text
            listed = client.get(f"/api/v1/organizations/{organization_id}/scheduled-posts", headers=headers)
            assert listed.status_code == 200
            assert listed.json()[0]["id"] == scheduled.json()["id"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="Set TEST_POSTGRES_URL for PostgreSQL workflow tests")
def test_postgres_enforces_one_renewal_attempt_per_subscription_period() -> None:
    """Exercise the database-level idempotency constraint on real PostgreSQL."""
    from sqlalchemy.exc import IntegrityError
    from app.models import Organization, PaymentTransaction, Subscription, SubscriptionRenewalAttempt

    engine = _disposable_postgres_engine()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    period_end = datetime.now(timezone.utc) + timedelta(days=30)
    try:
        with factory() as db:
            organization = Organization(name="Renewal Constraint", slug="renewal-constraint-pg")
            db.add(organization)
            db.flush()
            subscription = Subscription(
                organization_id=organization.id, provider="paystack", plan_id="standard", status="active",
                amount_minor=750000, currency="NGN", billing_interval="monthly", current_period_end=period_end,
            )
            db.add(subscription)
            db.flush()
            payment_one = PaymentTransaction(
                organization_id=organization.id, reference="pg-renewal-attempt-one", plan_id="standard",
                billing_interval="monthly", amount_minor=750000, currency="NGN",
                customer_email="billing@example.com", status="pending",
            )
            payment_two = PaymentTransaction(
                organization_id=organization.id, reference="pg-renewal-attempt-two", plan_id="standard",
                billing_interval="monthly", amount_minor=750000, currency="NGN",
                customer_email="billing@example.com", status="pending",
            )
            db.add_all([payment_one, payment_two])
            db.flush()
            db.add(SubscriptionRenewalAttempt(
                subscription_id=subscription.id, payment_transaction_id=payment_one.id,
                period_end=period_end, status="processing",
            ))
            db.commit()
            db.add(SubscriptionRenewalAttempt(
                subscription_id=subscription.id, payment_transaction_id=payment_two.id,
                period_end=period_end, status="processing",
            ))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
