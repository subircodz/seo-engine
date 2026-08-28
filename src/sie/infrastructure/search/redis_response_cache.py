"""Redis-backed shared response cache for search providers.

The cache stores provider raw JSON responses, not pickled Python objects. Redis
is an optimization: a Redis outage must never become a search-provider outage.
"""

from __future__ import annotations

import contextlib
import json
from typing import Any

from redis.asyncio import Redis

from sie.infrastructure.search.response_cache import CacheKey

__all__ = ["RedisSearchResponseCache"]


class RedisSearchResponseCache:
    """Shared TTL cache for raw provider JSON responses."""

    def __init__(
        self, redis_url: str, *, prefix: str = "sie:search:", ttl_seconds: int = 86_400
    ) -> None:
        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix
        self._ttl = ttl_seconds

    def _key(self, key: CacheKey, operation: str) -> str:
        return f"{self._prefix}{operation}:{key.hash()}"

    async def get(self, key: CacheKey, *, operation: str = "search") -> dict[str, Any] | None:
        redis_key = self._key(key, operation)
        try:
            value = await self._redis.get(redis_key)
        except Exception:
            return None
        if value is None:
            return None
        try:
            decoded = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            with contextlib.suppress(Exception):
                await self._redis.delete(redis_key)
            return None
        return decoded if isinstance(decoded, dict) else None

    async def put(
        self,
        key: CacheKey,
        value: dict[str, Any],
        *,
        operation: str = "search",
        ttl_seconds: int | None = None,
    ) -> None:
        try:
            await self._redis.set(
                self._key(key, operation),
                json.dumps(value, separators=(",", ":")),
                ex=ttl_seconds or self._ttl,
            )
        except Exception:
            return

    async def close(self) -> None:
        try:
            await self._redis.aclose()
        except Exception:
            return

    async def ping(self) -> bool:
        try:
            return bool(await self._redis.ping())
        except Exception:
            return False
