"""Cannibalization detection (Phase 6N-D).

Detects when multiple distinct target URLs from the same dataset compete for the
same keyword in search results. This is a known SEO issue where the search engine
may show different pages for the same query, potentially diluting the effectiveness
of each individual page's ranking signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from sie.domain.models.search import RankingObservation


def _extract_domain(url: str) -> str:
    """Extract bare, casefolded hostname from URL, stripping www."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").split(":")[0].casefold()
    if host.startswith("www."):
        host = host[4:]
    return host


@dataclass(frozen=True, slots=True)
class CannibalizationFinding:
    """A single cannibalization finding.

    Represents one keyword that has multiple distinct target URLs competing for
    the same search query, with the affected URLs and their ranking positions.
    """

    keyword: str
    competing_urls: tuple[str, ...]
    competing_domains: tuple[str, ...]
    positions: tuple[int, ...]
    severity: str

    def __post_init__(self) -> None:
        if len(self.competing_urls) < 2:
            raise ValueError(
                f"competing_urls must have at least 2 entries, got {len(self.competing_urls)}"
            )
        if not isinstance(self.severity, str) or not self.severity:
            raise ValueError("severity must be a non-empty string")


class CannibalizationDetector:
    """Domain service for detecting cannibalization in search rankings.

    Cannibalization occurs when multiple distinct target URLs from the same
    dataset compete for the same keyword. This can dilute the effectiveness
    of each individual page's ranking signal.

    Key principles:
    - Group observations by normalized keyword
    - Identify multiple distinct target URLs ranking for the same keyword
    - Report affected keyword, competing URLs, ranking positions, and severity
    - Do not treat repeated observations of the same URL as cannibalization
    - Deterministic ordering
    - Do not fabricate competition
    - Single URL per keyword = no cannibalization
    """

    def detect_cannibalization(
        self,
        observations: tuple[RankingObservation, ...],
    ) -> tuple[CannibalizationFinding, ...]:
        """Detect cannibalization across all observations.

        Returns a tuple of findings, sorted deterministically by keyword.
        """
        # Group observations by keyword
        observations_by_keyword: dict[str, list[RankingObservation]] = {}
        for obs in observations:
            key = obs.keyword
            if key not in observations_by_keyword:
                observations_by_keyword[key] = []
            observations_by_keyword[key].append(obs)

        findings: list[CannibalizationFinding] = []
        for keyword, obs_list in observations_by_keyword.items():
            finding = self._detect_for_keyword(keyword, obs_list)
            if finding is not None:
                findings.append(finding)

        # Return in sorted order for deterministic output
        return tuple(sorted(findings, key=lambda f: f.keyword))

    def _detect_for_keyword(
        self, keyword: str, observations: list[RankingObservation]
    ) -> CannibalizationFinding | None:
        """Detect cannibalization for a single keyword.

        Returns None if there are fewer than 2 distinct target URLs.
        """
        # Get distinct target URLs
        distinct_urls = set()
        for obs in observations:
            distinct_urls.add(obs.target_url)

        if len(distinct_urls) < 2:
            return None

        # Get the latest observation for each URL to determine its position
        # (using observed_at ordering)
        url_to_latest: dict[str, RankingObservation] = {}
        for obs in observations:
            if (
                obs.target_url not in url_to_latest
                or obs.observed_at > url_to_latest[obs.target_url].observed_at
            ):
                url_to_latest[obs.target_url] = obs

        # Sort URLs by position for deterministic ordering
        sorted_urls = sorted(url_to_latest.items(), key=lambda item: item[1].position)

        competing_urls = tuple(url for url, _ in sorted_urls)
        competing_domains = tuple(_extract_domain(url) for url, _ in sorted_urls)
        positions = tuple(obs.position for _, obs in sorted_urls)

        severity = self._calculate_severity(positions)

        return CannibalizationFinding(
            keyword=keyword,
            competing_urls=competing_urls,
            competing_domains=competing_domains,
            positions=positions,
            severity=severity,
        )

    def _calculate_severity(self, positions: tuple[int, ...]) -> str:
        """Calculate severity based on position spread.

        Severity levels:
        - low: positions are within 1-2 of each other
        - medium: positions are within 3-5 of each other
        - high: positions are within 6-10 of each other
        - extreme: positions are more than 10 apart
        """
        if len(positions) < 2:
            return "none"

        position_spread = max(positions) - min(positions)

        if position_spread <= 2:
            return "low"
        elif position_spread <= 5:
            return "medium"
        elif position_spread <= 10:
            return "high"
        else:
            return "extreme"

    def get_cannibalized_keywords(
        self,
        observations: tuple[RankingObservation, ...],
    ) -> tuple[str, ...]:
        """Return keywords that exhibit cannibalization.

        Useful for identifying keywords that may need attention to resolve
        competing URL issues.
        """
        findings = self.detect_cannibalization(observations)
        return tuple(sorted(f.keyword for f in findings))


__all__ = [
    "CannibalizationDetector",
    "CannibalizationFinding",
]
