"""Shared fixtures."""

from types import SimpleNamespace

import httpx
import pytest

from sie.api.app import create_app
from sie.config import Settings


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
