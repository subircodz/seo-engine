"""Bounded LRU-based URL deduplication set.

Once the capacity is exceeded, the least-recently-seen URL is evicted and may
be re-crawled later. This bounds memory on very large sites while keeping hot
URLs (recently re-discovered) pinned.
"""

from collections import OrderedDict


class LRUSet:
    """Not thread-safe by design; callers guard access (the engine holds a lock)."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._items: OrderedDict[str, None] = OrderedDict()

    def add(self, item: str) -> bool:
        """Register an item. Returns True when newly added, False on duplicate."""
        if item in self._items:
            self._items.move_to_end(item)
            return False
        self._items[item] = None
        if len(self._items) > self._capacity:
            self._items.popitem(last=False)
        return True

    def __contains__(self, item: object) -> bool:
        if item not in self._items:
            return False
        self._items.move_to_end(item)  # type: ignore[arg-type]
        return True

    def __len__(self) -> int:
        return len(self._items)
