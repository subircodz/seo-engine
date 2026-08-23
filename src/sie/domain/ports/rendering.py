"""Port: JavaScript-rendered page retrieval (browser-backed).

Deliberately unimplemented in Phase 1: Playwright is intentionally *not* a
dependency yet. A future adapter plugs in behind this Protocol without any
change to consumers.
"""

from typing import Protocol, runtime_checkable

from sie.domain.models.page import RenderedPage


@runtime_checkable
class Renderer(Protocol):
    """Executes JavaScript for a URL and returns the resulting DOM."""

    async def render(self, url: str) -> RenderedPage: ...

    async def close(self) -> None:
        """Release browser resources."""
