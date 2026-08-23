"""Port: raw page retrieval over plain HTTP. Deterministic, no browser."""

from typing import Protocol, runtime_checkable

from sie.domain.models.page import FetchedPage


@runtime_checkable
class Fetcher(Protocol):
    """Retrieves a single URL.

    Contract:
    * Redirects are followed; HTTP error statuses (4xx, 5xx) are returned as
      normal ``FetchedPage`` values -- they are SEO signals, not failures.
    * Only transport-level failures (DNS, TLS, timeouts, resets) raise
      ``FetchError``.
    * Implementations must be safe for concurrent ``fetch`` calls.
    """

    async def fetch(self, url: str) -> FetchedPage: ...

    async def close(self) -> None:
        """Release underlying connections."""
