"""Search provider factory (Phase 6L).

Centralises provider selection so the composition root (``app.py``) no
longer contains branching logic for provider construction.

The factory reads ``SearchProviderSettings`` and returns a concrete
``SearchProvider`` implementation:

- ``enabled=False``  → ``MockSearchProvider``
- ``enabled=True``   → dispatch on ``provider_name`` (``"mock"``, ``"http"``)
- unsupported name   → raise ``SearchProviderConfigError``

All providers live in ``sie.infrastructure.search``; the domain layer
never sees this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sie.config import SearchProviderSettings
from sie.domain.ports.search_provider import SearchProvider
from sie.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

__all__ = [
    "SearchProviderConfigError",
    "create_search_provider",
]

# Registry mapping provider names → lazy import callables.
# Each callable receives ``SearchProviderSettings`` and returns a
# ``SearchProvider``.  Lazy imports keep heavy dependencies (e.g. httpx)
# out of the import path when they are not needed.


def _create_mock(settings: SearchProviderSettings) -> SearchProvider:
    from sie.infrastructure.search.mock_provider import MockSearchProvider

    return MockSearchProvider()


def _create_http(settings: SearchProviderSettings) -> SearchProvider:
    if not settings.base_url or not settings.base_url.strip():
        raise SearchProviderConfigError(
            "Search provider 'http' requires SIE_SEARCH_PROVIDER__BASE_URL"
        )
    from sie.infrastructure.search.http_provider import HttpSearchProvider

    return HttpSearchProvider(
        base_url=settings.base_url,
        api_key=settings.api_key,
        timeout_seconds=settings.timeout_seconds,
        connect_timeout_seconds=settings.connect_timeout_seconds,
        read_timeout_seconds=settings.read_timeout_seconds,
        write_timeout_seconds=settings.write_timeout_seconds,
        pool_timeout_seconds=settings.pool_timeout_seconds,
        allow_localhost=settings.allow_localhost,
    )


_REGISTRY: dict[str, tuple[str, object]] = {
    "mock": ("MockSearchProvider", _create_mock),
    "http": ("HttpSearchProvider", _create_http),
}


class SearchProviderConfigError(Exception):
    """Raised when the search provider cannot be constructed from config."""


def create_search_provider(settings: SearchProviderSettings) -> SearchProvider:
    """Construct and return a ``SearchProvider`` from *settings*.

    Behaviour
    ---------
    - When ``settings.enabled`` is ``False`` the factory always returns
      a ``MockSearchProvider`` regardless of ``provider_name``.
    - When ``enabled`` is ``True`` the ``provider_name`` is looked up
      in the registry.  An unsupported name raises
      ``SearchProviderConfigError``.

    No API keys are exposed in log messages or error strings.

    Raises
    ------
    SearchProviderConfigError
        When the provider is enabled but misconfigured (missing base_url,
        unsupported provider_name, etc.).
    """
    if not settings.enabled:
        logger.info(
            "Search provider disabled — mock provider active. "
            "Set SIE_SEARCH_PROVIDER__ENABLED=true for real SERP data."
        )
        return _create_mock(settings)

    name = settings.provider_name.lower().strip()

    entry = _REGISTRY.get(name)
    if entry is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise SearchProviderConfigError(
            f"Unsupported search provider: {settings.provider_name!r}. "
            f"Supported providers: {supported}"
        )

    _label, factory = entry
    logger.info("Search provider enabled: name=%s base_url=%s", name, settings.base_url)
    return factory(settings)
