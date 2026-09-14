"""Reference ``Fetcher`` implementation backed by httpx.

Deliberately minimal: fetches a single URL. Crawling logic (frontier, dedupe,
robots, pacing) belongs to the future Crawler Engine, behind the ``Crawler``
port.
"""

from __future__ import annotations

import time
from urllib.parse import urljoin

import httpx

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage
from sie.domain.security.ssrf import resolve_and_validate


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
        max_redirects: int = 10,
        max_response_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        # ``client`` is injectable so tests can supply an httpx.MockTransport.
        # Keep the legacy timeout argument for API compatibility; granular
        # timeout settings are the effective HTTPX controls.
        del timeout_seconds
        timeout = httpx.Timeout(
            connect=connect_timeout_seconds,
            read=read_timeout_seconds,
            write=write_timeout_seconds,
            pool=pool_timeout_seconds,
        )
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": user_agent},
        )
        self._allow_localhost = allow_localhost
        if max_redirects < 0:
            raise ValueError("max_redirects must be non-negative")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self._max_redirects = max_redirects
        self._max_response_bytes = max_response_bytes

    async def fetch(self, url: str) -> FetchedPage:
        # SSRF protection: validate syntax and DNS resolution before every
        # outbound request, including every manually followed redirect.
        safe, error = await resolve_and_validate(
            url, allow_localhost=self._allow_localhost
        )
        if not safe:
            raise FetchError(f"SSRF protection blocked request to {url}: {error}")

        started = time.perf_counter()
        current_url = url
        response: httpx.Response | None = None
        content = b""
        try:
            for redirect_count in range(self._max_redirects + 1):
                async with self._client.stream(
                    "GET", current_url, follow_redirects=False
                ) as streamed_response:
                    if streamed_response.status_code in {301, 302, 303, 307, 308}:
                        location = streamed_response.headers.get("location")
                        if not location:
                            response = streamed_response
                            content = b""
                            break
                        if redirect_count >= self._max_redirects:
                            raise FetchError(
                                f"maximum redirects exceeded while fetching {url}"
                            )

                        redirect_url = urljoin(current_url, location)
                        safe, error = await resolve_and_validate(
                            redirect_url, allow_localhost=self._allow_localhost
                        )
                        if not safe:
                            raise FetchError(
                                f"SSRF protection blocked redirect to {redirect_url}: {error}"
                            )
                        current_url = redirect_url
                        continue

                    content_length = streamed_response.headers.get("content-length")
                    if (
                        content_length
                        and content_length.isdigit()
                        and int(content_length) > self._max_response_bytes
                    ):
                        raise FetchError(
                            f"response body exceeds maximum size of "
                            f"{self._max_response_bytes} bytes"
                        )

                    chunks: list[bytes] = []
                    total_bytes = 0
                    async for chunk in streamed_response.aiter_bytes():
                        total_bytes += len(chunk)
                        if total_bytes > self._max_response_bytes:
                            raise FetchError(
                                f"response body exceeds maximum size of "
                                f"{self._max_response_bytes} bytes"
                            )
                        chunks.append(chunk)

                    response = streamed_response
                    content = b"".join(chunks)
                    break
        except httpx.HTTPError as exc:
            raise FetchError(f"failed to fetch {current_url}: {exc!r}") from exc

        if response is None:  # pragma: no cover - loop always executes at least once
            raise FetchError(f"failed to fetch {url}: no response")

        duration_ms = int((time.perf_counter() - started) * 1000)
        return FetchedPage(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            headers=response.headers,
            content=content,
            content_type=response.headers.get("content-type"),
            encoding=response.encoding,
            duration_ms=duration_ms,
        )

    async def close(self) -> None:
        await self._client.aclose()
