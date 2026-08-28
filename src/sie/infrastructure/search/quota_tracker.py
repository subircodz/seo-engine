"""Search provider quota tracking — production observability for API costs.

Tracks request counts, successes, failures, and estimated costs per provider
instance.  Thread-safe via simple counters (asyncio is single-threaded per
event loop so no lock is needed).

Every ``SearchProvider`` implementation can optionally hold a ``QuotaTracker``
instance.  The tracker is purely observational — it never blocks or retries.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class QuotaSnapshot:
    """Point-in-time view of quota usage."""

    provider_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    rate_limited_requests: int
    estimated_cost_usd: float
    first_request_at: str | None
    last_request_at: str | None
    requests_by_minute: list[tuple[str, int]]  # (minute_key, count)


class QuotaTracker:
    """Lightweight, in-memory quota tracker for a single provider.

    Parameters
    ----------
    provider_name:
        Human-readable provider label (e.g. ``"serpapi"``).
    cost_per_request_usd:
        Estimated cost per successful request in USD.  Set to ``0.0`` for
        free providers.  The actual SerpAPI cost is ~$0.005/request.
    """

    def __init__(
        self,
        provider_name: str,
        cost_per_request_usd: float = 0.0,
    ) -> None:
        self._provider_name = provider_name
        self._cost_per_request = cost_per_request_usd

        self._total_requests: int = 0
        self._successful: int = 0
        self._failed: int = 0
        self._rate_limited: int = 0
        self._first_request_at: float | None = None
        self._last_request_at: float | None = None
        # Minute-keyed request counts for recent window
        self._minute_counts: dict[str, int] = {}

    # ── Recording methods ─────────────────────────────────────────────

    def record_request(self, *, success: bool = True, rate_limited: bool = False) -> None:
        """Record a single API request."""
        now = time.time()
        self._total_requests += 1
        self._last_request_at = now
        if self._first_request_at is None:
            self._first_request_at = now

        if rate_limited:
            self._rate_limited += 1
        elif success:
            self._successful += 1
        else:
            self._failed += 1

        # Track per-minute counts (sliding window of last 10 minutes)
        minute_key = datetime.fromtimestamp(now, tz=UTC).strftime("%Y-%m-%dT%H:%M")
        self._minute_counts[minute_key] = self._minute_counts.get(minute_key, 0) + 1
        self._prune_old_minutes()

    def _prune_old_minutes(self) -> None:
        """Remove minute keys older than 10 minutes."""
        if len(self._minute_counts) <= 10:
            return
        keys = sorted(self._minute_counts.keys())
        for old_key in keys[:-10]:
            del self._minute_counts[old_key]

    # ── Query methods ─────────────────────────────────────────────────

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def successful_requests(self) -> int:
        return self._successful

    @property
    def failed_requests(self) -> int:
        return self._failed

    @property
    def rate_limited_requests(self) -> int:
        return self._rate_limited

    @property
    def estimated_cost_usd(self) -> float:
        """Estimated cost based on successful requests only."""
        return self._successful * self._cost_per_request

    @property
    def requests_last_minute(self) -> int:
        """Number of requests in the most recent minute."""
        if not self._minute_counts:
            return 0
        latest_key = max(self._minute_counts.keys())
        return self._minute_counts[latest_key]

    @property
    def requests_remaining_estimate(self) -> int | None:
        """Rough estimate of remaining quota.

        SerpAPI's free tier allows ~100 requests/month.  This is a heuristic
        and should be replaced with actual quota tracking when the provider
        exposes a quota endpoint.
        """
        # Only approximate for SerpAPI
        if self._provider_name.lower() != "serpapi":
            return None
        monthly_limit = 100  # Free tier
        return max(0, monthly_limit - self._total_requests)

    def snapshot(self) -> QuotaSnapshot:
        """Return a point-in-time snapshot of quota usage."""
        first_at = None
        if self._first_request_at:
            first_at = datetime.fromtimestamp(self._first_request_at, tz=UTC).isoformat()
        last_at = None
        if self._last_request_at:
            last_at = datetime.fromtimestamp(self._last_request_at, tz=UTC).isoformat()

        return QuotaSnapshot(
            provider_name=self._provider_name,
            total_requests=self._total_requests,
            successful_requests=self._successful,
            failed_requests=self._failed,
            rate_limited_requests=self._rate_limited,
            estimated_cost_usd=round(self.estimated_cost_usd, 4),
            first_request_at=first_at,
            last_request_at=last_at,
            requests_by_minute=list(self._minute_counts.items()),
        )

    def reset(self) -> None:
        """Reset all counters (e.g. for a new billing period)."""
        self._total_requests = 0
        self._successful = 0
        self._failed = 0
        self._rate_limited = 0
        self._first_request_at = None
        self._last_request_at = None
        self._minute_counts.clear()
