"""Small OAuth refresh-token client for Google APIs.

Uses standard OAuth 2.0 refresh-token exchange and keeps access tokens in
memory only. Credentials must come from environment/secret management.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

__all__ = ["GoogleOAuthClient"]


class GoogleOAuthClient:
    """Acquire and refresh Google API access tokens without a Google SDK."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        timeout_seconds: float = 20.0,
        access_token: str = "",
    ) -> None:
        if not refresh_token and not access_token:
            raise ValueError("A refresh_token or access_token is required")
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token = access_token
        self._expires_at: datetime | None = None
        self._timeout = timeout_seconds
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def access_token(self) -> str:
        if (
            self._access_token
            and self._expires_at
            and datetime.now(UTC) < self._expires_at - timedelta(seconds=60)
        ):
            return self._access_token
        if self._access_token and not self._refresh_token:
            return self._access_token
        response = await self._client.post(
            self.TOKEN_URL,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Google OAuth response did not contain access_token")
        self._access_token = token
        expires_in = int(data.get("expires_in", 3600))
        self._expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)
        return token

    async def close(self) -> None:
        await self._client.aclose()
