"""API key authentication for the SEO Intelligence Engine.

Provides a minimal, configurable API key authentication mechanism
suitable for production deployment while remaining disabled by default
for development.
"""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, Request, status

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

    # Constant-time comparison against each valid key
    return any(secrets.compare_digest(api_key, valid_key) for valid_key in valid_keys)


async def api_key_auth(
    request: Request,
    api_key_header: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """FastAPI dependency for API key authentication.

    Validates the API key from the X-API-Key header.
    Raises 401 if authentication is enabled but key is missing or invalid.

    Args:
        request: The FastAPI request object.
        api_key_header: The API key from the X-API-Key header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: 401 if authentication fails or is missing.
    """
    settings: APISettings = request.app.state.settings.api

    # If auth is disabled, allow all requests
    if not settings.enabled:
        return "dev-mode"

    # Check for API key in header
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Validate the API key
    if not verify_api_key(api_key_header, settings.api_keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key_header


async def optional_api_key_auth(
    request: Request,
    api_key_header: str | None = Header(None, alias="X-API-Key"),
) -> str | None:
    """Optional API key authentication dependency.

    Validates the API key if provided, but doesn't require it.
    Useful for endpoints that work with or without authentication.

    Args:
        request: The FastAPI request object.
        api_key_header: The API key from the X-API-Key header.

    Returns:
        The validated API key, or None if not provided/invalid.
    """
    settings: APISettings = request.app.state.settings.api

    # If auth is disabled or no header provided, return None
    if not settings.enabled or not api_key_header:
        return None

    # Validate the API key
    if verify_api_key(api_key_header, settings.api_keys):
        return api_key_header

    return None


def get_api_key_dependency(settings: APISettings):
    """Factory function to create the appropriate auth dependency.

    Returns the required auth dependency if enabled, otherwise returns
    a no-op dependency that always succeeds.

    Args:
        settings: The API authentication settings.

    Returns:
        A FastAPI dependency callable.
    """
    if settings.enabled:
        return api_key_auth
    else:
        # Return a no-op dependency for development
        async def no_auth() -> str:
            return "dev-mode"
        return no_auth
