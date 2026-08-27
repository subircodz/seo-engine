"""AIO/GEO Trend Analysis Services (Phase 2).

Pure functions for calculating trend metrics from historical AIO/GEO observations.
No I/O, no network, deterministic. Same input always yields same output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


@dataclass(frozen=True, slots=True)
class AIOTrendMetrics:
    """Trend metrics for AIO observations over a period."""

    domain: str
    period_days: int
    total_observations: int
    ai_overview_rate: float
    """Fraction of observations where AI Overview was present (0.0-1.0)."""
    citation_rate: float
    """Average citations per observation."""
    target_citation_rate: float
    """Fraction of AI-present observations where target was cited (0.0-1.0)."""
    trend: str
    """Overall trend: 'improving', 'declining', or 'stable'."""
    current_period: dict[str, float]
    """Metrics for the most recent half of the period."""
    previous_period: dict[str, float]
    """Metrics for the first half of the period."""
    trend_details: str = ""
    """Human-readable trend description."""


@dataclass(frozen=True, slots=True)
class GEOTrendMetrics:
    """Trend metrics for GEO observations over a period."""

    domain: str
    period_days: int
    total_observations: int
    mention_rate: float
    """Fraction of observations where target was mentioned (0.0-1.0)."""
    competitor_mention_rate: float
    """Fraction of observations where competitors were mentioned (0.0-1.0)."""
    avg_mentions_per_observation: float
    """Average target mentions per observation."""
    trend: str
    """Overall trend: 'improving', 'declining', or 'stable'."""
    current_period: dict[str, float]
    """Metrics for the most recent half of the period."""
    previous_period: dict[str, float]
    """Metrics for the first half of the period."""
    trend_details: str = ""
    """Human-readable trend description."""


def _split_observations_by_time(
    observations: list[Any],
    period_days: int,
) -> tuple[list[Any], list[Any]]:
    """Split observations into current (recent half) and previous (older half) periods."""
    if not observations:
        return [], []

    end_date = datetime.now(UTC)
    mid_date = end_date - timedelta(days=period_days // 2)

    current = [o for o in observations if o.observed_at >= mid_date]
    previous = [o for o in observations if o.observed_at < mid_date]

    return current, previous


def calculate_aio_trend(
    domain: str,
    observations: list[Any],
    period_days: int = 30,
) -> Any:
    """Calculate AIO trend metrics for a domain over a period.

    Args:
        domain: Target domain being tracked.
        observations: List of AIO observations (newest first).
        period_days: Period in days to analyze.

    Returns:
        AIOTrendMetrics with trend analysis.
    """
    if not observations:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class EmptyResult:
            domain: str
            period_days: int
            total_observations: int = 0
            ai_overview_rate: float = 0.0
            citation_rate: float = 0.0
            target_citation_rate: float = 0.0
            trend: str = "insufficient_data"
            current_period: dict = None
            previous_period: dict = None
            trend_details: str = "No observations in period"

        return EmptyResult(
            domain=domain,
            period_days=period_days,
        )

    # Filter to period
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=period_days)
    filtered = [o for o in observations if start_date <= o.observed_at <= end_date]

    if not filtered:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class EmptyResult:
            domain: str
            period_days: int
            total_observations: int = 0
            ai_overview_rate: float = 0.0
            citation_rate: float = 0.0
            target_citation_rate: float = 0.0
            trend: str = "insufficient_data"
            current_period: dict = None
            previous_period: dict = None
            trend_details: str = "No observations in period"

        return EmptyResult(
            domain=domain,
            period_days=period_days,
        )

    # Split into current (recent half) and previous (older half) periods
    current, previous = _split_observations_by_time(filtered, period_days)

    def calc_metrics(obs_list):
        if not obs_list:
            return {
                "ai_overview_rate": 0.0,
                "citation_rate": 0.0,
                "target_citation_rate": 0.0,
            }
        total = len(obs_list)
        ai_present = sum(1 for o in obs_list if o.present)
        cited = sum(1 for o in obs_list if o.target_cited)
        total_citations = sum(o.citation_count for o in obs_list)
        return {
            "ai_overview_rate": ai_present / total,
            "citation_rate": total_citations / total if total > 0 else 0.0,
            "target_citation_rate": cited / total if total > 0 else 0.0,
        }

    current_metrics = calc_metrics(current)
    previous_metrics = calc_metrics(previous)

    # Determine trend
    trend = "stable"
    if current_metrics["target_citation_rate"] > previous_metrics["target_citation_rate"] + 0.05:
        trend = "improving"
    elif current_metrics["target_citation_rate"] < previous_metrics["target_citation_rate"] - 0.05:
        trend = "declining"

    # Determine trend details
    details = []
    if trend == "improving":
        details.append(
            f"Target citation rate improved from {previous_metrics['target_citation_rate']:.1%} "
            f"to {current_metrics['target_citation_rate']:.1%}"
        )
    elif trend == "declining":
        details.append(
            f"Target citation rate declined from "
            f"{previous_metrics['target_citation_rate']:.1%} "
            f"to {current_metrics['target_citation_rate']:.1%}"
        )

    if current_metrics["ai_overview_rate"] > previous_metrics.get("ai_overview_rate", 0) + 0.05:
        details.append("AI Overview presence increased")
    elif current_metrics["ai_overview_rate"] < previous_metrics.get("ai_overview_rate", 0) - 0.05:
        details.append("AI Overview presence decreased")

    trend_details = "; ".join(details) if details else "No significant change"

    @dataclass(frozen=True, slots=True)
    class AIOverviewTrendMetrics:
        domain: str
        period_days: int
        total_observations: int
        ai_overview_rate: float
        citation_rate: float
        target_citation_rate: float
        trend: str
        current_period: dict[str, float]
        previous_period: dict[str, float]
        trend_details: str = ""

    return AIOverviewTrendMetrics(
        domain=domain,
        period_days=period_days,
        total_observations=len(filtered),
        ai_overview_rate=current_metrics["ai_overview_rate"],
        citation_rate=current_metrics["citation_rate"],
        target_citation_rate=current_metrics["target_citation_rate"],
        trend=trend,
        current_period=current_metrics,
        previous_period=previous_metrics,
        trend_details=trend_details,
    )


def calculate_geo_trend(
    domain: str,
    observations: list[Any],
    period_days: int = 30,
) -> Any:
    """Calculate GEO trend metrics for a domain over a period.

    Args:
        domain: Target domain being tracked.
        observations: List of GEO observations (newest first).
        period_days: Period in days to analyze.

    Returns:
        GEOTrendMetrics with trend analysis.
    """
    if not observations:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class EmptyResult:
            domain: str
            period_days: int
            total_observations: int = 0
            mention_rate: float = 0.0
            competitor_mention_rate: float = 0.0
            avg_mentions_per_observation: float = 0.0
            trend: str = "insufficient_data"
            current_period: dict = None
            previous_period: dict = None
            trend_details: str = "No observations in period"

        return EmptyResult(
            domain=domain,
            period_days=period_days,
        )

    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=period_days)
    filtered = [o for o in observations if start_date <= o.observed_at <= end_date]

    if not filtered:
        from dataclasses import dataclass

        @dataclass(frozen=True, slots=True)
        class EmptyResult:
            domain: str
            period_days: int
            total_observations: int = 0
            mention_rate: float = 0.0
            competitor_mention_rate: float = 0.0
            avg_mentions_per_observation: float = 0.0
            trend: str = "insufficient_data"
            current_period: dict = None
            previous_period: dict = None
            trend_details: str = "No observations in period"

        return EmptyResult(
            domain=domain,
            period_days=period_days,
        )

    current, previous = _split_observations_by_time(filtered, period_days)

    def calc_metrics(obs_list):
        if not obs_list:
            return {
                "mention_rate": 0.0,
                "competitor_mention_rate": 0.0,
                "avg_mentions_per_observation": 0.0,
            }
        total = len(obs_list)
        mentioned = sum(1 for o in obs_list if o.target_mentioned)
        comp_mentioned = sum(1 for o in obs_list if o.competitor_domains)
        total_mentions = sum(o.mention_count for o in obs_list)
        return {
            "mention_rate": mentioned / total,
            "competitor_mention_rate": comp_mentioned / total,
            "avg_mentions_per_observation": total_mentions / total,
        }

    current_metrics = calc_metrics(current)
    previous_metrics = calc_metrics(previous)

    trend = "stable"
    if current_metrics["mention_rate"] > previous_metrics["mention_rate"] + 0.05:
        trend = "improving"
    elif current_metrics["mention_rate"] < previous_metrics["mention_rate"] - 0.05:
        trend = "declining"

    details = []
    if trend == "improving":
        details.append(
            f"Brand mention rate improved from {previous_metrics['mention_rate']:.1%} "
            f"to {current_metrics['mention_rate']:.1%}"
        )
    elif trend == "declining":
        details.append(
            f"Brand mention rate declined from {previous_metrics['mention_rate']:.1%} "
            f"to {current_metrics['mention_rate']:.1%}"
        )

    comp_rate_curr = current_metrics["competitor_mention_rate"]
    comp_rate_prev = previous_metrics.get("competitor_mention_rate", 0)
    if comp_rate_curr > comp_rate_prev + 0.05:
        details.append("Competitor mentions increased")
    elif comp_rate_curr < comp_rate_prev - 0.05:
        details.append("Competitor mentions decreased")

    trend_details = "; ".join(details) if details else "No significant change"

    @dataclass(frozen=True, slots=True)
    class GEOTrendMetrics:
        domain: str
        period_days: int
        total_observations: int
        mention_rate: float
        competitor_mention_rate: float
        avg_mentions_per_observation: float
        trend: str
        current_period: dict[str, float]
        previous_period: dict[str, float]
        trend_details: str = ""

    return GEOTrendMetrics(
        domain=domain,
        period_days=period_days,
        total_observations=len(filtered),
        mention_rate=current_metrics["mention_rate"],
        competitor_mention_rate=current_metrics["competitor_mention_rate"],
        avg_mentions_per_observation=current_metrics["avg_mentions_per_observation"],
        trend=trend,
        current_period=current_metrics,
        previous_period=previous_metrics,
        trend_details=trend_details,
    )


def _split_observations_by_time(
    observations: list[Any],
    period_days: int,
) -> tuple[list[Any], list[Any]]:
    """Split observations into current (recent half) and previous (older half) periods."""
    if not observations:
        return [], []

    end_date = datetime.now(UTC)
    mid_date = end_date - timedelta(days=period_days // 2)

    current = [o for o in observations if o.observed_at >= mid_date]
    previous = [o for o in observations if o.observed_at < mid_date]

    return current, previous


__all__ = [
    "calculate_aio_trend",
    "calculate_geo_trend",
]
