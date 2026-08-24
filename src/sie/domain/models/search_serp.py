"""SERP feature domain models (Phase 6N).

Immutable value objects representing SERP (Search Engine Results Page) features
like featured snippets, People Also Ask, knowledge panels, etc.

These models are provider-independent and capture only the essential,
vendor-neutral aspects of SERP features for later analytics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

from sie.domain.models.search import _require_non_empty, _validate_url


class SERPFeatureType(StrEnum):
    """Types of SERP features that can appear in search results."""

    FEATURED_SNIPPET = "featured_snippet"
    """Featured snippet (position zero answer box)."""

    PEOPLE_ALSO_ASK = "people_also_ask"
    """People Also Ask expandable question box."""

    KNOWLEDGE_PANEL = "knowledge_panel"
    """Knowledge panel (typically on right side)."""

    LOCAL_PACK = "local_pack"
    """Local business pack with map."""

    SHOPPING = "shopping"
    """Shopping/product results carousel."""

    VIDEO = "video"
    """Video results carousel."""

    IMAGE_PACK = "image_pack"
    """Image results grid/carousel."""

    NEWS = "news"
    """News results carousel."""

    OTHER = "other"
    """Catch-all for unspecified/emerging feature types."""


def _validate_optional_url(url: str | None, field_name: str) -> str | None:
    """Validate an optional URL field.

    Returns None if input is None, otherwise validates and returns the URL.
    """
    if url is None:
        return None
    return _validate_url(url, field_name)


def _validate_optional_position(position: int | None, field_name: str) -> int | None:
    """Validate an optional position field.

    Returns None if input is None, otherwise validates and returns the position.
    Position can be >= 0 for features like featured snippets at position zero.
    """
    if position is None:
        return None
    if isinstance(position, bool) or not isinstance(position, int):
        raise ValueError(f"{field_name} must be an integer, got {position!r}")
    if position < 0:
        raise ValueError(f"{field_name} must be >= 0, got {position}")
    return position


@dataclass(frozen=True, slots=True)
class SearchSERPFeature:
    """A SERP (Search Engine Results Page) feature associated with a search result.

    SERP features are special result types that appear alongside or instead of
    traditional organic results, such as featured snippets, knowledge panels,
    local packs, etc.

    All fields are optional to accommodate varying feature types and provider
    capabilities. Only provider-independent information is captured.
    """

    feature_type: SERPFeatureType
    """The type of SERP feature."""

    position: int | None = None
    """1-based position where this feature appears, if applicable.

    For features that span multiple positions (like local packs), this should
    represent the starting position. None if position is not applicable or
    not provided by the source.
    """

    title: str | None = None
    """Short title or label for the feature, if available.

    Examples: "Featured snippet", "People also ask", "Local businesses".
    Left None if not meaningful for the feature type or not provided.
    """

    url: str | None = None
    """Associated URL for the feature, if applicable.

    For features that link to a specific page (like featured snippets).
    Left None if no URL association or not applicable.
    """

    domain: str | None = None
    """Extractable domain from URL, if URL is present.

    Provided for convenience and to avoid repeated parsing. Must be a bare,
    casefolded hostname with www. stripped if present. Left None if URL is None.
    """

    # Immutable tuple for metadata to prevent accidental mutation
    _metadata: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        # Validate feature_type is a valid SERPFeatureType enum member
        if not isinstance(self.feature_type, SERPFeatureType):
            raise ValueError(
                f"feature_type must be a SERPFeatureType, got {type(self.feature_type).__name__}"
            )

        if self.position is not None:
            object.__setattr__(
                self,
                "position",
                _validate_optional_position(self.position, "position"),
            )

        if self.title is not None:
            object.__setattr__(self, "title", _require_non_empty(self.title, "title"))

        if self.url is not None:
            validated_url = _validate_url(self.url, "url")
            object.__setattr__(self, "url", validated_url)
            parsed = urlparse(validated_url)
            host = (parsed.netloc or "").split(":")[0].casefold()
            if host.startswith("www."):
                host = host[4:]
            object.__setattr__(self, "domain", host if host else None)
        else:
            object.__setattr__(self, "domain", None)

        # Validate metadata - must be a tuple of tuples for immutability
        if not isinstance(self._metadata, tuple):
            raise ValueError("Metadata must be a tuple of (key, value) string pairs")
        validated_metadata = []
        for item in self._metadata:
            if not (
                isinstance(item, tuple)
                and len(item) == 2
                and all(isinstance(part, str) for part in item)
            ):
                raise ValueError("Metadata items must be tuples of two strings")
            validated_metadata.append(item)
        object.__setattr__(self, "_metadata", tuple(validated_metadata))

    @property
    def metadata(self) -> tuple[tuple[str, str], ...]:
        """Immutable metadata associated with the SERP feature.

        Returns a tuple of (key, value) string pairs. Empty tuple if no metadata.
        """
        return self._metadata


__all__ = [
    "SERPFeatureType",
    "SearchSERPFeature",
]
