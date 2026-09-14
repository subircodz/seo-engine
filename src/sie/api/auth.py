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
    """Constant-time comparison of API key against valid keys."""
    if not valid_keys:
        return False
    return any(secrets.compare_digest(api_key, valid_key) for valid_key in valid_keys)


def _configured_header(request: Request) -> str:
    """Return the configured API-key header name, with a safe fallback."""
    header_name = request.app.state.settings.api.header_name.strip()
    return header_name or "X-API-Key"


async def api_key_auth(request: Request) -> str:
    """Require and validate the configured API-key header when enabled."""
    settings: APISettings = request.app.state.settings.api

    if not settings.enabled:
        return "dev-mode"

    header_name = _configured_header(request)
    api_key_header = request.headers.get(header_name)
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"API key required. Provide {header_name} header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not verify_api_key(api_key_header, settings.api_keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key_header


async def optional_api_key_auth(request: Request) -> str | None:
    """Validate the configured API-key header when present, without requiring it."""
    settings: APISettings = request.app.state.settings.api
    if not settings.enabled:
        return None

    api_key_header = request.headers.get(_configured_header(request))
    if not api_key_header:
        return None

    return api_key_header if verify_api_key(api_key_header, settings.api_keys) else None


def get_api_key_dependency(settings: APISettings):
    """Return the required auth dependency when enabled, otherwise a no-op dependency."""
    if settings.enabled:
        return api_key_auth

    async def no_auth() -> str:
        return "dev-mode"

    return no_auth
