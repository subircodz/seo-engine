"""In-memory LRU response cache for search providers.

Reduces redundant API calls by caching (keyword, country, language, device,
provider) tuples.  Entries expire after a configurable TTL (default 24 hours).

Thread-safe: asyncio is single-threaded per event loop so no lock is needed.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from sie.logging import get_logger

logger = get_logger(__name__)

__all__ = ["SearchResponseCache"]


@dataclass(frozen=True)
class CacheKey:
    """Normalized cache key for a search query."""

    keyword: str
    country: str
    language: str
    device: str
    provider: str
    search_engine: str

    @classmethod
    def from_query(
        cls,
        keyword: str,
        country: str,
        language: str,
        device: str,
        provider: str,
        search_engine: str = "google",
    ) -> CacheKey:
        return cls(
            keyword=keyword.strip().casefold(),
            country=country.strip().casefold(),
            language=language.strip().casefold(),
            device=device.strip().casefold(),
            provider=provider.strip().casefold(),
            search_engine=search_engine.strip().casefold(),
        )

    def hash(self) -> str:
        """Deterministic string hash for storage key."""
        raw = f"{self.keyword}|{self.country}|{self.language}|{self.device}|{self.provider}|{self.search_engine}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SearchResponseCache:
    """LRU cache with TTL for search provider responses.

    Parameters
    ----------
    max_entries:
        Maximum number of cached responses (LRU eviction when exceeded).
    ttl_seconds:
        Time-to-live for cached entries.  Default 24 hours (86400s).
    """

    def __init__(
        self,
        max_entries: int = 10_000,
        ttl_seconds: float = 86_400.0,
    ) -> None:
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: CacheKey) -> Any | None:
        """Retrieve a cached response, or ``None`` on miss/expiry."""
        hash_key = key.hash()
        entry = self._cache.get(hash_key)
        if entry is None:
            self._misses += 1
            return None

        stored_at, value = entry
        if (time.time() - stored_at) > self._ttl:
            # Expired
            del self._cache[hash_key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(hash_key)
        self._hits += 1
        return value

    def put(self, key: CacheKey, value: Any) -> None:
        """Store a response in the cache."""
        hash_key = key.hash()

        # If already exists, update
        if hash_key in self._cache:
            self._cache.move_to_end(hash_key)
            self._cache[hash_key] = (time.time(), value)
            return

        # Evict LRU if at capacity
        while len(self._cache) >= self._max_entries:
            self._cache.popitem(last=False)

        self._cache[hash_key] = (time.time(), value)

    def invalidate(self, key: CacheKey) -> bool:
        """Remove a specific entry. Returns True if found and removed."""
        hash_key = key.hash()
        if hash_key in self._cache:
            del self._cache[hash_key]
            return True
        return False

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    @property
    def size(self) -> int:
        """Number of entries currently in cache."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Cache hit ratio (0.0-1.0). Returns 0.0 if no requests yet."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        """Return cache statistics for observability."""
        return {
            "size": self.size,
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
        }
