"""Reference ``Fetcher`` implementation backed by httpx.

Deliberately minimal: fetches a single URL. Crawling logic (frontier, dedupe,
robots, pacing) belongs to the future Crawler Engine, behind the ``Crawler``
port.
"""

import time

import httpx

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage


class HttpxFetcher:
    """Deterministic HTTP fetcher; executes no JavaScript (see ``Renderer`` port)."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        # ``client`` is injectable so tests can supply an httpx.MockTransport.
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )

    async def fetch(self, url: str) -> FetchedPage:
        started = time.perf_counter()
        try:
            response = await self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise FetchError(f"failed to fetch {url}: {exc!r}") from exc
        duration_ms = int((time.perf_counter() - started) * 1000)
        return FetchedPage(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            content_type=response.headers.get("content-type"),
            encoding=response.encoding,
            duration_ms=duration_ms,
        )

    async def close(self) -> None:
        await self._client.aclose()
