"""Async SQLAlchemy wiring.

SQLite (via aiosqlite) today; Postgres later by changing ``database_url`` in
configuration only -- no code changes.  ``Base`` is the declarative base shared
by every ORM model; ``Database`` owns the engine, session factory, and a one-
line healthcheck.
"""

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from sie.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for all future ORM models."""


class Database:
    """Owns the async engine and session factory for one database URL."""

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_timeout: float = 30.0,
        pool_recycle: int = 1800,
    ) -> None:
        # Only apply pool settings for PostgreSQL (not SQLite)
        is_postgres = url.startswith("postgresql") or url.startswith("postgres")

        if is_postgres:
            self._engine = create_async_engine(
                url,
                echo=echo,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                pool_pre_ping=True,
            )
        else:
            # SQLite doesn't use connection pooling
            self._engine = create_async_engine(url, echo=echo)

        @event.listens_for(self._engine.sync_engine, "connect")
        def _pragma_fk_on(dbapi_conn, _):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        self.session_factory = async_sessionmaker(self._engine, expire_on_commit=False)

    async def healthcheck(self) -> bool:
        try:
            async with self.session_factory() as session:
                await session.execute(text("SELECT 1"))
        except Exception:
            logger.exception("database healthcheck failed")
            return False
        return True

    async def dispose(self) -> None:
        await self._engine.dispose()
