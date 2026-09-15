"""Programmatic Alembic migration runner (runs ``alembic upgrade head``).

Designed to be called once at application startup so fresh databases get their
schema without requiring a separate CLI step.  The migration directory path is
calculated relative to *this file*, so it works in both editable and wheel
installs (where ``src/sie/infrastructure/persistence/migrations.py`` resolves
back to ``<project_root>/alembic.ini`` via the ``parents`` chain).

Returns ``True`` on success, ``False`` on non-fatal failure (e.g. when running
from an installed wheel where the migration files are not present).
"""

import os
from pathlib import Path

from sie.log_config import get_logger

logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"


def run_migrations(database_url: str) -> bool:
    if not _ALEMBIC_INI.exists():
        logger.info("alembic.ini not found at %s; skipping auto-migration", _ALEMBIC_INI)
        return False

    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
    except ImportError:
        logger.warning("alembic not installed; skipping auto-migration")
        return False

    original_env = os.environ.get("SIE_DATABASE_URL")
    try:
        os.environ["SIE_DATABASE_URL"] = database_url
        cfg = AlembicConfig(str(_ALEMBIC_INI))
        cfg.set_main_option("script_location", str(_REPO_ROOT / "migrations"))
        command.upgrade(cfg, "head")
    except Exception:
        logger.exception("auto-migration failed")
        return False
    finally:
        if original_env is None:
            os.environ.pop("SIE_DATABASE_URL", None)
        else:
            os.environ["SIE_DATABASE_URL"] = original_env
    return True
