"""In-memory LRU response cache for search providers."""

from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

__all__ = ["CacheKey", "SearchResponseCache"]


@dataclass(frozen=True)
class CacheKey:
    """Normalized cache key for a provider operation."""

    keyword: str
    country: str
    language: str
    device: str
    provider: str
    search_engine: str
    context: str = ""

    @classmethod
    def from_query(
        cls,
        keyword: str,
        country: str,
        language: str,
        device: str,
        provider: str,
        search_engine: str = "google",
        context: str = "",
    ) -> "CacheKey":
        return cls(
            keyword=keyword.strip().casefold(),
            country=country.strip().casefold(),
            language=language.strip().casefold(),
            device=device.strip().casefold(),
            provider=provider.strip().casefold(),
            search_engine=search_engine.strip().casefold(),
            context=context.strip().casefold(),
        )

    def hash(self) -> str:
        raw = "|".join(
            (self.keyword, self.country, self.language, self.device, self.provider, self.search_engine, self.context)
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class SearchResponseCache:
    """LRU cache with TTL for provider responses."""

    def __init__(self, max_entries: int = 10_000, ttl_seconds: float = 86_400.0) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: CacheKey) -> Any | None:
        hash_key = key.hash()
        entry = self._cache.get(hash_key)
        if entry is None:
            self._misses += 1
            return None
        stored_at, value = entry
        if time.time() - stored_at > self._ttl:
            del self._cache[hash_key]
            self._misses += 1
            return None
        self._cache.move_to_end(hash_key)
        self._hits += 1
        return value

    def put(self, key: CacheKey, value: Any) -> None:
        hash_key = key.hash()
        if hash_key in self._cache:
            self._cache.move_to_end(hash_key)
        else:
            while len(self._cache) >= self._max_entries:
                self._cache.popitem(last=False)
        self._cache[hash_key] = (time.time(), value)

    def invalidate(self, key: CacheKey) -> bool:
        hash_key = key.hash()
        if hash_key not in self._cache:
            return False
        del self._cache[hash_key]
        return True

    def clear(self) -> None:
        self._cache.clear()
        self._hits = self._misses = 0

    @property
    def size(self) -> int:
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
        }
