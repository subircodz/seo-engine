"""Domain error hierarchy."""


class SieError(Exception):
    """Base class for all domain-level errors."""


class FetchError(SieError):
    """Transport-level failure while retrieving a page (DNS, TLS, timeout, ...).

    HTTP error statuses (4xx/5xx) are *not* fetch errors; they are data.
    """


class RobotsDisallowedError(SieError):
    """A URL may not be fetched because robots.txt disallows it."""


class CrawlAlreadyRunningError(SieError):
    """Attempted to start a second concurrent crawl while one was active."""


class CrawlNotRunningError(SieError):
    """Attempted to interact with a crawl that was not running."""


class InvalidCrawlTargetError(SieError):
    """The seed URL or scope is invalid (bad scheme, missing host, ...)."""
