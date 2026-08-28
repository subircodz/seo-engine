"""Search-provider quota tracking and local cost enforcement."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime


class QuotaExceeded(RuntimeError):
    """Raised before an outbound request when the configured local quota is exhausted."""


@dataclass(frozen=True)
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
    requests_by_minute: list[tuple[str, int]]
    monthly_request_limit: int | None
    requests_remaining_estimate: int | None


class QuotaTracker:
    """Track and optionally enforce a provider request budget.

    The tracker is intentionally provider-agnostic. Pricing and quota limits
    must be supplied by configuration; no provider's current pricing or free
    tier is hard-coded here.

    This is a process-local guard. A distributed deployment should place the
    same reservation logic behind Redis or another shared atomic store.
    """

    def __init__(
        self,
        provider_name: str,
        cost_per_request_usd: float = 0.0,
        monthly_request_limit: int = 0,
    ) -> None:
        if cost_per_request_usd < 0:
            raise ValueError("cost_per_request_usd must be >= 0")
        if monthly_request_limit < 0:
            raise ValueError("monthly_request_limit must be >= 0")

        self._provider_name = provider_name
        self._cost_per_request = cost_per_request_usd
        self._monthly_limit = monthly_request_limit or None
        self._period_key = self._current_period_key()
        self._total_requests = 0
        self._successful = 0
        self._failed = 0
        self._rate_limited = 0
        self._first_request_at: float | None = None
        self._last_request_at: float | None = None
        self._minute_counts: dict[str, int] = {}

    @staticmethod
    def _current_period_key() -> str:
        return datetime.now(UTC).strftime("%Y-%m")

    def _roll_period_if_needed(self) -> None:
        period = self._current_period_key()
        if period != self._period_key:
            self.reset()
            self._period_key = period

    def reserve(self) -> None:
        """Reserve one outbound request or raise ``QuotaExceeded``.

        Call this immediately before the actual provider request. Failed and
        successful requests both consume the provider quota, so reservation is
        based on total outbound attempts rather than successful responses.
        """
        self._roll_period_if_needed()
        if self._monthly_limit is not None and self._total_requests >= self._monthly_limit:
            raise QuotaExceeded(
                f"{self._provider_name} local monthly request limit exhausted "
                f"({self._monthly_limit})"
            )
        self._total_requests += 1
        now = time.time()
        self._last_request_at = now
        if self._first_request_at is None:
            self._first_request_at = now
        minute_key = datetime.fromtimestamp(now, tz=UTC).strftime("%Y-%m-%dT%H:%M")
        self._minute_counts[minute_key] = self._minute_counts.get(minute_key, 0) + 1
        self._prune_old_minutes()

    def record_request(self, *, success: bool = True, rate_limited: bool = False) -> None:
        """Record the outcome of a request previously reserved with ``reserve``.

        For backwards compatibility, calling this method without a prior
        reservation still records a request.
        """
        self._roll_period_if_needed()
        if self._total_requests == 0:
            self.reserve()
        if rate_limited:
            self._rate_limited += 1
        elif success:
            self._successful += 1
        else:
            self._failed += 1

    def _prune_old_minutes(self) -> None:
        if len(self._minute_counts) > 10:
            for old_key in sorted(self._minute_counts)[:-10]:
                del self._minute_counts[old_key]

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
        """Estimated provider cost based on all outbound attempts."""
        return self._total_requests * self._cost_per_request

    @property
    def requests_last_minute(self) -> int:
        if not self._minute_counts:
            return 0
        return self._minute_counts[max(self._minute_counts)]

    @property
    def requests_remaining_estimate(self) -> int | None:
        if self._monthly_limit is None:
            return None
        self._roll_period_if_needed()
        return max(0, self._monthly_limit - self._total_requests)

    def snapshot(self) -> QuotaSnapshot:
        self._roll_period_if_needed()
        first_at = (
            datetime.fromtimestamp(self._first_request_at, tz=UTC).isoformat()
            if self._first_request_at is not None
            else None
        )
        last_at = (
            datetime.fromtimestamp(self._last_request_at, tz=UTC).isoformat()
            if self._last_request_at is not None
            else None
        )
        return QuotaSnapshot(
            provider_name=self._provider_name,
            total_requests=self._total_requests,
            successful_requests=self._successful,
            failed_requests=self._failed,
            rate_limited_requests=self._rate_limited,
            estimated_cost_usd=round(self.estimated_cost_usd, 6),
            first_request_at=first_at,
            last_request_at=last_at,
            requests_by_minute=list(self._minute_counts.items()),
            monthly_request_limit=self._monthly_limit,
            requests_remaining_estimate=self.requests_remaining_estimate,
        )

    def reset(self) -> None:
        """Reset the current period's counters."""
        self._total_requests = 0
        self._successful = 0
        self._failed = 0
        self._rate_limited = 0
        self._first_request_at = None
        self._last_request_at = None
        self._minute_counts.clear()
