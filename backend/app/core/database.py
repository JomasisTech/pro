from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy database models added in later stages."""


settings = get_settings()

# pool_pre_ping checks stale database connections before using them.
# SQLite (used by demo mode and fast tests) needs check_same_thread=False because FastAPI runs requests in a thread pool.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide one database session per request and always close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
