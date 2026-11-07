import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.core import demo
from app.core.database import Base
from app.models import BusinessProfile, IndustryCategory, Membership, Organization, User


def test_demo_mode_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="DEMO_MODE"):
        Settings(app_env="production", demo_mode=True, secret_key="x" * 40, _env_file=None)


def test_demo_seed_creates_a_working_account_and_is_repeatable(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(demo, "engine", engine)
    monkeypatch.setattr(demo, "SessionLocal", factory)

    demo.prepare_demo_environment()
    demo.prepare_demo_environment()  # running twice must not duplicate anything

    with factory() as db:
        users = db.scalars(select(User)).all()
        assert {u.email for u in users} == {"customer-demo@example.com", "platform-owner-demo@example.com"}
        assert len(db.scalars(select(Membership)).all()) == 2
        assert all(m.role == "owner" for m in db.scalars(select(Membership)).all())
        customer = db.scalar(select(User).where(User.email == "customer-demo@example.com"))
        platform_owner = db.scalar(select(User).where(User.email == "platform-owner-demo@example.com"))
        assert customer is not None and customer.has_password is True
        assert platform_owner is not None and platform_owner.has_password is False
        assert all(o.plan == "premium" for o in db.scalars(select(Organization)).all())
        assert db.scalars(select(BusinessProfile)).all()[0].onboarding_completed_at is not None
        assert db.scalars(select(IndustryCategory)).all()


def test_demo_info_endpoint_is_off_by_default(client) -> None:
    assert client.get("/api/v1/auth/demo").json() == {"enabled": False}


def test_demo_mode_generates_a_random_secret() -> None:
    settings = Settings(demo_mode=True, app_env="staging", database_url="sqlite+pysqlite:///./demo.db", _env_file=None)
    assert len(settings.secret_key) >= 32 and "development-only" not in settings.secret_key


def test_demo_mode_requires_isolated_sqlite_database() -> None:
    with pytest.raises(ValidationError, match="isolated SQLite"):
        Settings(demo_mode=True, app_env="staging", database_url="postgresql+psycopg://demo:demo@localhost/demo", secret_key="x" * 40, _env_file=None)


def test_demo_customer_and_admin_emails_must_be_distinct() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            app_env="staging", demo_mode=True, database_url="sqlite+pysqlite:///./demo.db",
            secret_key="x" * 40, demo_email="same@example.com", demo_admin_email="SAME@example.com",
            _env_file=None,
        )
