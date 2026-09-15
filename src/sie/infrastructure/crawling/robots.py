"""robots.txt compliance gate (RFC 9309 subset, conservative on failures).

Behaviour per RFC guidance:
* 2xx with parseable body -> rules apply (including Crawl-delay).
* 4xx (unreachable/nonexistent robots) -> crawling allowed.
* 401/403 or 5xx or transport failure -> complete disallow (conservative),
  cached briefly so the gate retries later instead of permanently blocking.
"""

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from sie.domain.errors import FetchError
from sie.domain.ports.fetching import Fetcher

_FRESH_TTL_SECONDS = 3600.0
_ERROR_TTL_SECONDS = 60.0
_DEFAULT_MAX_CACHE_ENTRIES = 10_000


@dataclass(slots=True)
class _RobotsEntry:
    allow_all: bool
    disallow_all: bool
    parser: RobotFileParser | None = None
    crawl_delay: float = 0.0
    expires_at: float = 0.0


class RobotsGate:
    """Caches one robots.txt decision set per origin for the process lifetime.

    The cache is bounded because a cross-origin crawl can otherwise accumulate
    one entry for every visited host across repeated runs.
    """

    def __init__(
        self,
        fetcher: Fetcher,
        *,
        user_agent: str,
        clock: Callable[[], float] = time.monotonic,
        max_cache_entries: int = _DEFAULT_MAX_CACHE_ENTRIES,
    ) -> None:
        if max_cache_entries < 1:
            raise ValueError("max_cache_entries must be positive")
        self._fetcher = fetcher
        self._user_agent = user_agent
        self._clock = clock
        self._max_cache_entries = max_cache_entries
        self._entries: OrderedDict[str, _RobotsEntry] = OrderedDict()

    async def allowed(self, url: str) -> bool:
        entry = await self._entry_for(url)
        if entry.allow_all:
            return True
        if entry.disallow_all:
            return False
        assert entry.parser is not None
        return entry.parser.can_fetch(self._user_agent, url)

    async def crawl_delay_seconds(self, url: str) -> float:
        entry = await self._entry_for(url)
        return entry.crawl_delay

    async def _entry_for(self, url: str) -> _RobotsEntry:
        parts = urlsplit(url)
        scheme = parts.scheme or "https"
        netloc = parts.netloc.lower()
        cache_key = f"{scheme}://{netloc}"
        cached = self._entries.get(cache_key)
        now = self._clock()
        if cached is not None and cached.expires_at > now:
            self._entries.move_to_end(cache_key)
            return cached
        entry = await self._fetch_entry(urlunsplit((scheme, netloc, "/robots.txt", "", "")))
        self._entries[cache_key] = entry
        self._entries.move_to_end(cache_key)
        while len(self._entries) > self._max_cache_entries:
            self._entries.popitem(last=False)
        return entry

    async def _fetch_entry(self, robots_url: str) -> _RobotsEntry:
        try:
            page = await self._fetcher.fetch(robots_url)
        except FetchError:
            return self._error_entry()

        if 200 <= page.status_code < 300:
            parser = RobotFileParser()
            parser.parse(page.decoded_text().splitlines())
            raw_delay = parser.crawl_delay(self._user_agent)
            delay = float(raw_delay) if raw_delay is not None else 0.0
            return _RobotsEntry(
                allow_all=False,
                disallow_all=False,
                parser=parser,
                crawl_delay=delay,
                expires_at=self._clock() + _FRESH_TTL_SECONDS,
            )
        if page.status_code in (401, 403) or page.status_code >= 500:
            return self._error_entry()
        return _RobotsEntry(
            allow_all=True, disallow_all=False, expires_at=self._clock() + _FRESH_TTL_SECONDS
        )

    def _error_entry(self) -> _RobotsEntry:
        return _RobotsEntry(
            allow_all=False,
            disallow_all=True,
            expires_at=self._clock() + _ERROR_TTL_SECONDS,
        )
