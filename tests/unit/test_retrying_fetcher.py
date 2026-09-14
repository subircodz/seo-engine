"""RetryingFetcher backoff, status retry and transient retry."""

import asyncio

import httpx
import pytest

from sie.domain.errors import FetchError
from sie.domain.models.page import FetchedPage
from sie.infrastructure.fetching.retrying_fetcher import RetryingFetcher


class FakeInner:
    """Scripted ``Fetcher`` stub that returns pages in sequence then raises."""

    def __init__(self, pages=(), *, exception: FetchError | None = None):
        self._pages = list(pages)
        self._idx = 0
        self._exception = exception

    async def fetch(self, url: str) -> FetchedPage:
        if self._idx < len(self._pages):
            p = self._pages[self._idx]
            self._idx += 1
            return p
        if self._exception is not None:
            raise self._exception
        raise FetchError("unexpected extra call")

    async def close(self):
        pass


def _page(status: int, headers: dict | None = None) -> FetchedPage:
    return FetchedPage(
        url="https://example.com",
        final_url="https://example.com",
        status_code=status,
        headers=headers or {},
        content=b"",
    )


def _transport_exc() -> FetchError:
    return FetchError("boom") from httpx.ConnectError("connection failed")


def make_retrier(inner, **kwargs):
    return RetryingFetcher(inner, sleep=asyncio.sleep, **kwargs)


class TestRetryingFetcher:
    def test_no_retry_on_success(self):
        inner = FakeInner(pages=[_page(200)])
        retrier = make_retrier(inner, max_retries=3)
        page = asyncio.run(retrier.fetch("https://example.com"))
        assert page.status_code == 200

    def test_retries_on_429_then_succeeds(self):
        inner = FakeInner(pages=[_page(429), _page(429), _page(200)])
        retrier = make_retrier(inner, max_retries=3, jitter=False)
        page = asyncio.run(retrier.fetch("https://example.com"))
        assert page.status_code == 200

    def test_exhausts_retries_returns_last_503(self):
        inner = FakeInner(pages=[_page(503), _page(503)])
        retrier = make_retrier(inner, max_retries=1, jitter=False)
        page = asyncio.run(retrier.fetch("https://example.com"))
        assert page.status_code == 503

    def test_honors_retry_after_header(self):
        """Verify retry-after is used when it is > backoff."""
        clock_time = [0.0]

        def clock():
            return clock_time[0]

        sleeps: list[float] = []

        async def fake_sleep(s):
            sleeps.append(s)
            clock_time[0] += s

        inner = FakeInner(pages=[_page(429, {"Retry-After": "10"}), _page(200)])
        retrier = RetryingFetcher(inner, max_retries=2, jitter=False, clock=clock, sleep=fake_sleep)
        page = asyncio.run(retrier.fetch("https://example.com"))
        assert page.status_code == 200
        assert sleeps == [pytest.approx(10.0)]

    def test_caps_excessive_retry_after_header(self):
        sleeps: list[float] = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        inner = FakeInner(pages=[_page(429, {"Retry-After": "86400"}), _page(200)])
        retrier = RetryingFetcher(inner, max_retries=1, jitter=False, sleep=fake_sleep)
        page = asyncio.run(retrier.fetch("https://example.com"))

        assert page.status_code == 200
        assert sleeps == [pytest.approx(30.0)]


class TestRetryingFetcherTransportRetry:
    def test_transport_error_retried_up_to_max(self):
        inner = FakeInner(exception=_transport_exc())
        retrier = make_retrier(inner, max_retries=2)
        with pytest.raises(FetchError):
            asyncio.run(retrier.fetch("https://example.com"))
        assert inner._idx == 0
