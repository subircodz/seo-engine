"""``Fetcher`` decorator adding exponential backoff for transient failures.

Behaviour: retries on HTTP 429/503 and on transport-level errors (timeouts,
connection resets). Honours ``Retry-After`` headers when present and numeric.
The ``sleep`` parameter is injectable so tests can assert on delays without
touching wall-clock time.
"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable

import httpx

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage
from sie.domain.ports.fetching import Fetcher

_RETRY_STATUSES = frozenset({429, 503})
_MAX_BACKOFF = 30.0


def _retry_after_seconds(page: FetchedPage) -> float:
    header_value = (page.headers.get("Retry-After") or "").strip()
    if header_value.isdigit():
        try:
            return min(float(header_value), _MAX_BACKOFF)
        except ValueError:
            pass
    return 0.0


def _is_transient(exc: FetchError) -> bool:
    return isinstance(exc.__cause__, httpx.TransportError)


class RetryingFetcher:
    def __init__(
        self,
        inner: Fetcher,
        *,
        max_retries: int = 2,
        base_delay_seconds: float = 0.5,
        jitter: bool = True,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")
        self._inner = inner
        self._max_retries = max_retries
        self._base = base_delay_seconds
        self._jitter = jitter
        self._clock = clock
        self._sleep = sleep

    def _backoff(self, attempt: int) -> float:
        delay = self._base * (2**attempt)
        if self._jitter:
            delay *= 0.5 + random.random()
        return min(delay, _MAX_BACKOFF)

    async def fetch(self, url: str) -> FetchedPage:
        attempt = 0
        page: FetchedPage | None = None
        while True:
            try:
                page = await self._inner.fetch(url)
            except FetchError as exc:
                if attempt >= self._max_retries or not _is_transient(exc):
                    raise
                delay = self._backoff(attempt)
            else:
                retry_after = _retry_after_seconds(page)
                if page.status_code not in _RETRY_STATUSES or attempt >= self._max_retries:
                    return page
                delay = max(self._backoff(attempt), retry_after)
            await self._sleep(delay)
            attempt += 1

    async def close(self) -> None:
        await self._inner.close()
