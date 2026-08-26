"""Reference ``Fetcher`` implementation backed by httpx.

Deliberately minimal: fetches a single URL. Crawling logic (frontier, dedupe,
robots, pacing) belongs to the future Crawler Engine, behind the ``Crawler``
port.
"""

import time

import httpx

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage
from sie.domain.security.ssrf import validate_url


class HttpxFetcher:
    """Deterministic HTTP fetcher; executes no JavaScript (see ``Renderer`` port)."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout_seconds: float = 20.0,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 20.0,
        write_timeout_seconds: float = 10.0,
        pool_timeout_seconds: float = 5.0,
        client: httpx.AsyncClient | None = None,
        allow_localhost: bool = False,
    ) -> None:
        # ``client`` is injectable so tests can supply an httpx.MockTransport.
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": user_agent},
        )
        self._allow_localhost = allow_localhost

    async def fetch(self, url: str) -> FetchedPage:
        # SSRF protection: validate URL before making request
        safe, error = validate_url(url, allow_localhost=self._allow_localhost)
        if not safe:
            raise FetchError(f"SSRF protection blocked request to {url}: {error}")

        started = time.perf_counter()
        try:
            response = await self._client.get(url, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise FetchError(f"failed to fetch {url}: {exc!r}") from exc
        duration_ms = int((time.perf_counter() - started) * 1000)

        # Validate redirect target as well
        final_url = str(response.url)
        if final_url != url:
            safe, error = validate_url(final_url, allow_localhost=self._allow_localhost)
            if not safe:
                raise FetchError(f"SSRF protection blocked redirect to {final_url}: {error}")

        return FetchedPage(
            url=url,
            final_url=final_url,
            status_code=response.status_code,
            headers=response.headers,
            content=response.content,
            content_type=response.headers.get("content-type"),
            encoding=response.encoding,
            duration_ms=duration_ms,
        )

    async def close(self) -> None:
        await self._client.aclose()
