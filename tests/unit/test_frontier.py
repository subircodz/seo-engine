"""LRU deduplication set (crawling frontier helper)."""

import pytest

from sie.infrastructure.crawling.frontier import LRUSet


class TestLRUSet:
    def test_add_new_returns_true(self):
        s = LRUSet(10)
        assert s.add("a") is True

    def test_duplicate_returns_false(self):
        s = LRUSet(10)
        s.add("a")
        assert s.add("a") is False

    def test_capacity_eviction(self):
        s = LRUSet(3)
        for i in ("a", "b", "c"):
            s.add(i)
        s.add("d")  # evicts "a"
        assert "a" not in s
        assert "d" in s

    def test_read_touches_recent(self):
        s = LRUSet(3)
        for i in ("a", "b", "c"):
            s.add(i)
        _ = "a" in s  # read touches "a"
        s.add("d")  # evicts "b" (oldest untouched)
        assert "a" in s
        assert "b" not in s

    def test_capacity_one(self):
        s = LRUSet(1)
        s.add("x")
        assert s.add("y") is True
        assert "x" not in s

    def test_rejects_capacity_zero(self):
        with pytest.raises(ValueError):
            LRUSet(0)
