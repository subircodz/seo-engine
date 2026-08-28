"""Google Analytics 4 Data API provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx

from sie.infrastructure.google.oauth_client import GoogleOAuthClient

__all__ = ["AnalyticsDataProvider", "AnalyticsObservation"]


@dataclass(frozen=True, slots=True)
class AnalyticsObservation:
    """Normalized GA4 report row."""

    dimensions: tuple[str, ...]
    metrics: tuple[tuple[str, float], ...]


class AnalyticsDataProvider:
    """Read-only GA4 Data API client using the REST ``runReport`` endpoint."""

    ENDPOINT = "https://analyticsdata.googleapis.com/v1beta/properties"

    def __init__(
        self, oauth: GoogleOAuthClient, property_id: str, *, timeout_seconds: float = 20.0
    ) -> None:
        if not property_id.strip():
            raise ValueError("GA4 property_id is required")
        self._oauth = oauth
        self._property_id = property_id.removeprefix("properties/")
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def run_report(
        self,
        start_date: date,
        end_date: date,
        *,
        dimensions: tuple[str, ...] = ("date",),
        metrics: tuple[str, ...] = ("sessions", "totalUsers", "screenPageViews"),
        limit: int = 10000,
    ) -> tuple[AnalyticsObservation, ...]:
        token = await self._oauth.access_token()
        response = await self._client.post(
            f"{self.ENDPOINT}/{self._property_id}:runReport",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "dateRanges": [
                    {"startDate": start_date.isoformat(), "endDate": end_date.isoformat()}
                ],
                "dimensions": [{"name": name} for name in dimensions],
                "metrics": [{"name": name} for name in metrics],
                "limit": limit,
            },
        )
        response.raise_for_status()
        result: list[AnalyticsObservation] = []
        for row in response.json().get("rows", []):
            if not isinstance(row, dict):
                continue
            dimension_values = tuple(
                str(item.get("value", ""))
                for item in row.get("dimensionValues", [])
                if isinstance(item, dict)
            )
            normalized: list[tuple[str, float]] = []
            for name, item in zip(metrics, row.get("metricValues", []), strict=False):
                if not isinstance(item, dict):
                    continue
                try:
                    normalized.append((name, float(item.get("value", "0"))))
                except (TypeError, ValueError):
                    normalized.append((name, 0.0))
            result.append(AnalyticsObservation(dimension_values, tuple(normalized)))
        return tuple(result)

    async def close(self) -> None:
        await self._client.aclose()
        await self._oauth.close()
