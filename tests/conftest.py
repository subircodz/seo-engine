"""Shared fixtures."""

import os
from types import SimpleNamespace

import httpx
import pytest

from sie.api.app import create_app
from sie.config import Settings


@pytest.fixture(autouse=True)
def _clear_sie_env(monkeypatch):
    """Remove all SIE_ env vars so tests get clean defaults.

    pydantic-settings reads os.environ even when ``_env_file=None``.
    The .env file in the repo root exports production values that
    break tests asserting default behaviour.  This fixture provides
    hermetic isolation.
    """
    for key in [k for k in os.environ if k.startswith("SIE_")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """Hermetic settings: no .env file, throwaway SQLite database."""
    return Settings(
        _env_file=None,
        environment="test",
        debug=False,
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
    )


@pytest.fixture
async def harness(test_settings):
    """App + HTTP client sharing one lifespan (so state wiring is visible)."""
    app = create_app(test_settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            yield SimpleNamespace(app=app, settings=test_settings, client=http)


@pytest.fixture
async def client(harness):
    return harness.client


@pytest.fixture
async def app_client(harness):
    """Alias for client for backward compatibility."""
    return harness.client
