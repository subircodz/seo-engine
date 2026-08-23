"""Per-host request pacing (default 1 request/second per domain)."""

import asyncio
import time
from collections.abc import Awaitable, Callable


class PerHostRateLimiter:
    """Reserves slots atomically, then sleeps outside the lock.

    Safe under concurrency: each caller reserves its slot before yielding, so
    parallel acquires serialize correctly per host while different hosts are
    independent.
    """

    def __init__(
        self,
        requests_per_second: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._min_interval = 1.0 / requests_per_second
        self._clock = clock
        self._sleep = sleep
        self._next_allowed: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, host: str, *, minimum_interval: float | None = None) -> None:
        interval = max(self._min_interval, minimum_interval or 0.0)
        async with self._lock:
            now = self._clock()
            ready = self._next_allowed.get(host, 0.0)
            wait = max(0.0, ready - now)
            self._next_allowed[host] = max(now, ready) + interval
        if wait > 0:
            await self._sleep(wait)
