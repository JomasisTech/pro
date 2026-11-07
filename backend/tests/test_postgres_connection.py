"""Optional connectivity check against a real PostgreSQL test database.

Set TEST_POSTGRES_URL to enable this test. It only runs SELECT 1 and does not
modify the database schema or data.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="Set TEST_POSTGRES_URL to run the PostgreSQL connectivity test",
)
def test_configured_postgres_database_is_reachable() -> None:
    database_url = make_url(os.environ["TEST_POSTGRES_URL"])
    assert database_url.get_backend_name() == "postgresql", (
        "TEST_POSTGRES_URL must use a PostgreSQL URL"
    )

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
