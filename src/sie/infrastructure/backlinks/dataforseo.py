"""DataForSEO Backlinks provider.

Uses the live Backlinks Summary endpoint. The provider reports observed
provider metrics and never invents authority/backlink values when unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

__all__ = ["BacklinkSummary", "DataForSeoBacklinkProvider"]


@dataclass(frozen=True, slots=True)
class BacklinkSummary:
    target: str
    backlinks: int
    referring_domains: int
    referring_pages: int
    rank: float | None
    spam_score: float | None
    crawled_pages: int | None
    source: str = "dataforseo"


class DataForSeoBacklinkProvider:
    """Read-only DataForSEO Backlinks API adapter."""

    ENDPOINT = "https://api.dataforseo.com/v3/backlinks/summary/live"

    def __init__(
        self,
        *,
        login: str,
        password: str,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not login.strip() or not password.strip():
            raise ValueError("DataForSEO login and password are required")
        self._login = login
        self._password = password
        self._endpoint = (base_url or "https://api.dataforseo.com").rstrip(
            "/"
        ) + "/v3/backlinks/summary/live"
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def summary(
        self,
        target: str,
        *,
        include_subdomains: bool = True,
        exclude_internal_backlinks: bool = True,
    ) -> BacklinkSummary:
        normalized = self._normalize_target(target)
        response = await self._client.post(
            self._endpoint,
            auth=(self._login, self._password),
            json=[
                {
                    "target": normalized,
                    "include_subdomains": include_subdomains,
                    "exclude_internal_backlinks": exclude_internal_backlinks,
                }
            ],
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status_code") not in (None, 20000):
            raise RuntimeError(f"DataForSEO error: {data.get('status_message', 'unknown error')}")
        tasks = data.get("tasks") or []
        if not tasks or not isinstance(tasks[0], dict):
            raise RuntimeError("DataForSEO returned no backlink task result")
        task = tasks[0]
        result = task.get("result") or []
        if not result or not isinstance(result[0], dict):
            raise RuntimeError("DataForSEO returned no backlink summary")
        value: dict[str, Any] = result[0]
        return BacklinkSummary(
            target=normalized,
            backlinks=int(value.get("backlinks", 0)),
            referring_domains=int(value.get("referring_domains", 0)),
            referring_pages=int(value.get("referring_pages", 0)),
            rank=float(value["rank"]) if value.get("rank") is not None else None,
            spam_score=float(value["backlinks_spam_score"])
            if value.get("backlinks_spam_score") is not None
            else None,
            crawled_pages=int(value["crawled_pages"])
            if value.get("crawled_pages") is not None
            else None,
        )

    @staticmethod
    def _normalize_target(target: str) -> str:
        value = target.strip()
        parsed = urlparse(value if "://" in value else f"https://{value}")
        if not parsed.hostname:
            raise ValueError("Invalid backlink target")
        return parsed.hostname.casefold().removeprefix("www.")

    async def close(self) -> None:
        await self._client.aclose()
