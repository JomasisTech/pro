import os

# Use an isolated local database for API tests; never require a live PostgreSQL
# server merely to import the application or test health/readiness responses.
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from app import main

client = TestClient(main.app)


def test_health_endpoint_does_not_require_database() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_v1_root() -> None:
    response = client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json()["message"] == "Business Automation Platform API v1"


def test_readiness_endpoint_when_database_is_available(monkeypatch) -> None:
    # Use an in-memory SQLite engine so this test never depends on a live PostgreSQL server.
    monkeypatch.setattr(main, "engine", create_engine("sqlite+pysqlite:///:memory:"))
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_readiness_endpoint_returns_503_when_database_fails(monkeypatch) -> None:
    def fail_to_connect():
        raise OperationalError("SELECT 1", {}, RuntimeError("database is offline"))

    monkeypatch.setattr(main.engine, "connect", fail_to_connect)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "database is offline" not in response.text


def test_readiness_checks_configured_redis(monkeypatch) -> None:
    class FakeRedis:
        def __init__(self):
            self.pinged = False
            self.closed = False

        def ping(self):
            self.pinged = True
            return True

        def close(self):
            self.closed = True

    fake_client = FakeRedis()
    monkeypatch.setattr(main.settings, "redis_url", "rediss://redis.example.com:6379/0")
    monkeypatch.setitem(
        __import__("sys").modules,
        "redis",
        __import__("types").SimpleNamespace(
            Redis=__import__("types").SimpleNamespace(from_url=lambda *args, **kwargs: fake_client)
        ),
    )
    monkeypatch.setattr(main, "engine", create_engine("sqlite+pysqlite:///:memory:"))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok", "redis": "ok"}
    assert fake_client.pinged is True
    assert fake_client.closed is True


def test_readiness_fails_closed_when_configured_redis_is_unavailable(monkeypatch) -> None:
    class FakeRedis:
        def ping(self):
            raise OSError("redis credentials or network details must not leak")

        def close(self):
            pass

    monkeypatch.setattr(main.settings, "redis_url", "rediss://redis.example.com:6379/0")
    monkeypatch.setitem(
        __import__("sys").modules,
        "redis",
        __import__("types").SimpleNamespace(
            Redis=__import__("types").SimpleNamespace(from_url=lambda *args, **kwargs: FakeRedis())
        ),
    )
    monkeypatch.setattr(main, "engine", create_engine("sqlite+pysqlite:///:memory:"))

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": "Rate-limit store unavailable"}
    assert "credentials" not in response.text
