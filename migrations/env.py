"""Alembic env.py (synchronous migration runner).

Migrations deliberately use *sync* database URLs (e.g. ``sqlite://`` instead of
``sqlite+aiosqlite://``) so they can execute identically from the Alembic CLI
and from inside a running asyncio event loop (auto-migrate on app startup),
where spawning a nested event loop is not possible.
"""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from sie.config import MigrationSettings
from sie.infrastructure.models import crawl_orm  # noqa: F401  (registers mappers)
from sie.infrastructure.persistence.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

_ASYNC_TO_SYNC_DRIVERS = {
    "sqlite+aiosqlite": "sqlite",
    "postgresql+asyncpg": "postgresql+psycopg2",
}


def _database_url() -> str:
    url = (
        os.environ.get("SIE_DATABASE_URL")
        or config.get_main_option("sqlalchemy.url")
        or MigrationSettings().database_url
    )
    for async_driver, sync_driver in _ASYNC_TO_SYNC_DRIVERS.items():
        if url.startswith(f"{async_driver}:"):
            return f"{sync_driver}:{url.split(':', 1)[1]}"
    return url


def _include_object(object_, name, type_, reflected, compare_to):
    """Keep DB-only legacy/raw tables from being treated as removals.

    Some persisted tables are intentionally managed by raw SQL or retained as
    legacy data and therefore are not represented in the ORM metadata. They
    must not be dropped merely because Alembic autogenerate cannot see them.
    Any intentional destructive schema change should be represented explicitly
    by a migration instead.
    """
    return not (type_ == "table" and reflected and compare_to is None)


def _configure(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
        include_object=_include_object,
    )


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _configure(connection)
        with connection.begin():
            context.run_migrations()
    connectable.dispose()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
