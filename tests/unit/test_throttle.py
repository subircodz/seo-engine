"""Per-host rate limiter with injectable clock / sleep."""

import asyncio

import pytest

from sie.infrastructure.crawling.throttle import PerHostRateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


def make_limiter(rps: float, clock: FakeClock) -> PerHostRateLimiter:
    async def fake_sleep(seconds: float):
        clock.sleeps.append(seconds)
        clock.advance(seconds)

    return PerHostRateLimiter(rps, clock=clock, sleep=fake_sleep)


class TestPerHostRateLimiter:
    def test_second_acquire_waits(self):
        clock = FakeClock()
        limiter = make_limiter(1.0, clock)
        asyncio.run(limiter.acquire("host"))
        assert clock.sleeps == []
        asyncio.run(limiter.acquire("host"))
        assert clock.sleeps == [pytest.approx(1.0)]

    def test_different_hosts_are_independent(self):
        clock = FakeClock()
        limiter = make_limiter(1.0, clock)
        asyncio.run(limiter.acquire("a"))
        asyncio.run(limiter.acquire("b"))
        assert clock.sleeps == []

    def test_minimum_interval_override(self):
        clock = FakeClock()
        limiter = make_limiter(1.0, clock)
        asyncio.run(limiter.acquire("h", minimum_interval=5.0))
        asyncio.run(limiter.acquire("h"))
        assert clock.sleeps == [pytest.approx(5.0)]

    def test_rejects_zero_rps(self):
        with pytest.raises(ValueError):
            PerHostRateLimiter(0.0)
