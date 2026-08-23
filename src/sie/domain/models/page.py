"""Core page models produced by fetching and rendering ports."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime

_FALLBACK_ENCODINGS = ("utf-8", "cp1252")


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class FetchedPage:
    """Raw result of retrieving a single URL over plain HTTP.

    Contract context: transport-level failures raise ``FetchError`` instead;
    HTTP error statuses (404, 500, ...) are *data*, not exceptions, because
    they are primary input for SEO diagnostics.
    """

    url: str
    final_url: str
    status_code: int
    headers: Mapping[str, str]
    content: bytes
    content_type: str | None = None
    encoding: str | None = None
    fetched_at: datetime = field(default_factory=_utc_now)
    duration_ms: int = 0
    rendered: bool = False
    depth: int = 0
    parent_url: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def is_html(self) -> bool:
        return self.content_type is not None and "html" in self.content_type.lower()

    def decoded_text(self) -> str:
        """Decode the body honouring the declared charset, with safe fallbacks."""
        if self.encoding:
            try:
                return self.content.decode(self.encoding)
            except (LookupError, UnicodeDecodeError):
                pass
        for candidate in _FALLBACK_ENCODINGS:
            try:
                return self.content.decode(candidate)
            except UnicodeDecodeError:
                continue
        return self.content.decode("utf-8", errors="replace")


@dataclass(frozen=True, slots=True)
class RenderedPage:
    """Result of executing JavaScript for a URL (future browser-backed adapter)."""

    url: str
    final_url: str
    status_code: int
    html: str
    rendered_at: datetime = field(default_factory=_utc_now)
    duration_ms: int = 0
