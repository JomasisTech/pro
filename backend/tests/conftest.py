from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.auth import (
    login_limiter,
    password_change_limiter,
    reset_email_limiter,
    reset_ip_limiter,
    verification_email_limiter, verification_ip_limiter,
    whatsapp_request_ip_limiter,
    whatsapp_verify_ip_limiter,
)
from app.api.v1.content import generation_limiter
from app.core.database import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def reset_login_limiter() -> Generator[None, None, None]:
    """Failed-login counters are process-wide; start and end every test with a clean slate."""
    for limiter in (
        login_limiter, generation_limiter, reset_email_limiter, reset_ip_limiter, password_change_limiter,
        whatsapp_request_ip_limiter, whatsapp_verify_ip_limiter, verification_email_limiter, verification_ip_limiter,
    ):
        limiter.reset()
    yield
    for limiter in (
        login_limiter, generation_limiter, reset_email_limiter, reset_ip_limiter, password_change_limiter,
        whatsapp_request_ip_limiter, whatsapp_verify_ip_limiter, verification_email_limiter, verification_ip_limiter,
    ):
        limiter.reset()


@pytest.fixture()
def session_factory() -> Generator[sessionmaker, None, None]:
    """An isolated in-memory SQLite database with all tables created."""
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(test_engine)
    yield sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    test_engine.dispose()


@pytest.fixture()
def client(session_factory: sessionmaker) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
