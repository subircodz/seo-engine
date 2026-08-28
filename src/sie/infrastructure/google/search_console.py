"""Google Search Console Search Analytics provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from urllib.parse import quote

import httpx

from sie.infrastructure.google.oauth_client import GoogleOAuthClient

__all__ = ["SearchConsoleObservation", "SearchConsoleProvider"]


@dataclass(frozen=True, slots=True)
class SearchConsoleObservation:
    """Normalized Search Console row."""

    keys: tuple[str, ...]
    clicks: float
    impressions: float
    ctr: float
    position: float


class SearchConsoleProvider:
    """Read-only Search Console Search Analytics client."""

    ENDPOINT = "https://www.googleapis.com/webmasters/v3/sites"

    def __init__(self, oauth: GoogleOAuthClient, property_url: str, *, timeout_seconds: float = 20.0) -> None:
        if not property_url.strip():
            raise ValueError("Search Console property_url is required")
        self._oauth = oauth
        self._property_url = property_url
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def query(
        self,
        start_date: date,
        end_date: date,
        *,
        dimensions: tuple[str, ...] = ("query", "page"),
        row_limit: int = 25000,
        start_row: int = 0,
        search_type: str = "web",
    ) -> tuple[SearchConsoleObservation, ...]:
        token = await self._oauth.access_token()
        encoded_property = quote(self._property_url, safe="")
        response = await self._client.post(
            f"{self.ENDPOINT}/{encoded_property}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": list(dimensions),
                "rowLimit": row_limit,
                "startRow": start_row,
                "type": search_type,
            },
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("rows", [])
        observations: list[SearchConsoleObservation] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            keys = row.get("keys", [])
            if not isinstance(keys, list):
                continue
            observations.append(
                SearchConsoleObservation(
                    keys=tuple(str(key) for key in keys),
                    clicks=float(row.get("clicks", 0.0)),
                    impressions=float(row.get("impressions", 0.0)),
                    ctr=float(row.get("ctr", 0.0)),
                    position=float(row.get("position", 0.0)),
                )
            )
        return tuple(observations)

    async def close(self) -> None:
        await self._client.aclose()
