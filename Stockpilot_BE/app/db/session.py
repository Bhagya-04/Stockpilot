from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        hide_parameters=True,  # keep bound values (e.g. password hashes) out of error messages/logs
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Request-scoped session. Services own the commit; anything uncommitted is rolled back on close,
    so a failed request can never leave a half-applied write behind."""
    db = get_sessionmaker()()
    try:
        yield db
    finally:
        db.close()
