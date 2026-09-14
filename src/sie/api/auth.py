"""API key authentication for the SEO Intelligence Engine.

Provides a minimal, configurable API key authentication mechanism
suitable for production deployment while remaining disabled by default
for development.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

from sie.config import APISettings


def verify_api_key(
    api_key: str,
    valid_keys: list[str],
) -> bool:
    """Constant-time comparison of API key against valid keys.

    Uses secrets.compare_digest to prevent timing attacks.

    Args:
        api_key: The API key to verify.
        valid_keys: List of valid API keys.

    Returns:
        True if the key matches any valid key, False otherwise.
    """
    if not valid_keys:
        return False

    return any(secrets.compare_digest(api_key, valid_key) for valid_key in valid_keys)


def _get_api_key(request: Request, settings: APISettings) -> str | None:
    """Read the configured API-key header without exposing its value in logs."""
    return request.headers.get(settings.header_name)


async def api_key_auth(request: Request) -> str:
    """FastAPI dependency for required API key authentication."""
    settings: APISettings = request.app.state.settings.api

    if not settings.enabled:
        return "dev-mode"

    api_key = _get_api_key(request, settings)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API key required. Provide {settings.header_name} header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not verify_api_key(api_key, settings.api_keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


async def optional_api_key_auth(request: Request) -> str | None:
    """Validate an API key when supplied, without requiring authentication."""
    settings: APISettings = request.app.state.settings.api

    if not settings.enabled:
        return None

    api_key = _get_api_key(request, settings)
    if not api_key:
        return None

    if verify_api_key(api_key, settings.api_keys):
        return api_key

    return None


def get_api_key_dependency(settings: APISettings):
    """Return the required auth dependency when enabled, otherwise a no-op."""
    if settings.enabled:
        return api_key_auth

    async def no_auth() -> str:
        return "dev-mode"

    return no_auth
