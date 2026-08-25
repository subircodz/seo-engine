"""Industry Intelligence domain models — Phase 10 strategic intelligence layer.

Provides comprehensive industry-aware intelligence synthesis:
- Industry profiles for configuration
- Industry-specific entity models
- Strategic finding models for industry gaps
- Opportunity scoring for cross-domain analysis

All models are immutable, deterministic, and provider-neutral.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class IndustryType(StrEnum):
    """Classification of industry domains for targeted analysis."""

    GENERAL = "general"
    CASINO = "casino"
    CRYPTO = "crypto"
    CRYPTO_CASINO = "crypto_casino"


class CasinoEntityType(StrEnum):
    """Entity types relevant to casino / iGaming analysis."""

    GAME = "game"
    GAME_PROVIDER = "game_provider"
    CASINO = "casino"
    BONUS = "bonus"
    PROMOTION = "promotion"
    PAYMENT_METHOD = "payment_method"
    CURRENCY = "currency"
    COUNTRY = "country"
    LICENSE = "license"
    REGULATOR = "regulator"
    JACKPOT = "jackpot"
    GAME_CATEGORY = "game_category"
    GAME_TYPE = "game_type"
    SLOT = "slot"
    TABLE_GAME = "table_game"
    LIVE_CASINO = "live_casino"
    FAQ = "faq"
    REVIEW = "review"
    COMPARISON = "comparison"
    WITHDRAWAL = "withdrawal"
    DEPOSIT = "deposit"
    OTHER = "other"


class CryptoEntityType(StrEnum):
    """Entity types relevant to cryptocurrency analysis."""

    COIN = "coin"
    TOKEN = "token"
    BLOCKCHAIN = "blockchain"
    NETWORK = "network"
    WALLET = "wallet"
    EXCHANGE = "exchange"
    PAYMENT_METHOD = "payment_method"
    STABLECOIN = "stablecoin"
    PROTOCOL = "protocol"
    SMART_CONTRACT = "smart_contract"
    ADDRESS = "address"
    TRANSACTION = "transaction"
    BLOCK = "block"
    FEE = "fee"
    CONFIRMATION = "confirmation"
    MINE = "mine"
    STAKE = "stake"
    BRIDGE = "bridge"
    OTHER = "other"


class CasinoSearchIntent(StrEnum):
    """Search intent classifications for casino-related queries."""

    NAVIGATIONAL = "navigational"
    INFORMATIONAL = "informational"
    COMMERCIAL_INVESTIGATION = "commercial_investigation"
    TRANSACTIONAL = "transactional"
    BONUS_SEEKING = "bonus_seeking"
    GAME_SEEKING = "game_seeking"
    PAYMENT_METHOD = "payment_method"
    GEO_REGULATORY = "geo_regulatory"
    COMPARISON = "comparison"
    OTHER = "other"


class CryptoSearchIntent(StrEnum):
    """Search intent classifications for cryptocurrency-related queries."""

    NAVIGATIONAL = "navigational"
    INFORMATIONAL = "informational"
    COMMERCIAL_INVESTIGATION = "commercial_investigation"
    TRANSACTIONAL = "transactional"
    PAYMENT_METHOD = "payment_method"
    WALLET_SETUP = "wallet_setup"
    NETWORK_INFO = "network_info"
    TOKEN_INFO = "token_info"
    EXCHANGE = "exchange"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CasinoEntity:
    """A casino-specific domain entity extracted from content."""

    name: str
    entity_type: CasinoEntityType
    frequency: int = 1
    confidence: float = 0.5
    context: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.frequency < 1:
            raise ValueError(f"frequency must be >= 1, got {self.frequency}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class CasinoTopic:
    """A topic cluster specific to the casino industry."""

    topic_label: str
    entities: tuple[CasinoEntity, ...] = ()
    relevance_score: float = 0.0
    keyword: str = ""

    @property
    def entity_count(self) -> int:
        return len(self.entities)


@dataclass(frozen=True, slots=True)
class CasinoAnalysisResult:
    """Result of casino content analysis."""

    total_entities: int = 0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    topics: tuple[CasinoTopic, ...] = ()
    content_gaps: tuple[str, ...] = ()
    entity_gaps: tuple[CasinoEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class CryptoEntity:
    """A cryptocurrency-specific domain entity extracted from content."""

    name: str
    entity_type: CryptoEntityType
    frequency: int = 1
    confidence: float = 0.5
    context: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.frequency < 1:
            raise ValueError(f"frequency must be >= 1, got {self.frequency}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class CryptoTopic:
    """A topic cluster specific to the cryptocurrency domain."""

    topic_label: str
    entities: tuple[CryptoEntity, ...] = ()
    relevance_score: float = 0.0
    keyword: str = ""

    @property
    def entity_count(self) -> int:
        return len(self.entities)


@dataclass(frozen=True, slots=True)
class CryptoAnalysisResult:
    """Result of cryptocurrency content analysis."""

    total_entities: int = 0
    entities_by_type: dict[str, int] = field(default_factory=dict)
    topics: tuple[CryptoTopic, ...] = ()
    content_gaps: tuple[str, ...] = ()
    entity_gaps: tuple[CryptoEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class IndustryEntity:
    """A generic industry entity (can be casino or crypto type)."""

    name: str
    entity_type: str
    frequency: int = 1
    confidence: float = 0.5
    context: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.frequency < 1:
            raise ValueError(f"frequency must be >= 1, got {self.frequency}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass(frozen=True, slots=True)
class IndustryTopic:
    """A topic cluster representing cross-domain industry topics."""

    topic_label: str
    entities: tuple[IndustryEntity, ...] = ()
    relevance_score: float = 0.0
    keyword: str = ""

    @property
    def entity_count(self) -> int:
        return len(self.entities)


@dataclass(frozen=True, slots=True)
class IndustryOpportunity:
    """An actionable SEO opportunity identified in industry analysis."""

    topic: str
    entities: tuple[IndustryEntity, ...] = ()
    intent: CasinoSearchIntent | CryptoSearchIntent | str = CasinoSearchIntent.OTHER
    priority: float = 0.0
    recommendation: str = ""
    impact: float = 0.5
    effort: float = 0.5

    def __post_init__(self) -> None:
        if not self.topic or not self.topic.strip():
            raise ValueError("topic must be a non-empty string")
        if not 0.0 <= self.priority <= 1.0:
            raise ValueError(f"priority must be in [0.0, 1.0], got {self.priority}")
        if not 0.0 <= self.impact <= 1.0:
            raise ValueError(f"impact must be in [0.0, 1.0], got {self.impact}")
        if not 0.0 <= self.effort <= 1.0:
            raise ValueError(f"effort must be in [0.0, 1.0], got {self.effort}")


@dataclass(frozen=True, slots=True)
class IndustryProfile:
    """Configuration profile for industry-specific intelligence analysis.

    Allows customization of analysis behavior without hardcoding.
    Provider-neutral and generic across all industry types.
    """

    industry_type: IndustryType = IndustryType.GENERAL
    target_domain: str = ""
    include_entity_analysis: bool = True
    include_opportunity_scoring: bool = True
    min_entity_confidence: float = 0.5
    min_opportunity_priority: float = 0.5

    def __post_init__(self) -> None:
        if not 0.0 <= self.min_entity_confidence <= 1.0:
            raise ValueError(
                f"min_entity_confidence must be in [0.0, 1.0], got {self.min_entity_confidence}"
            )
        if not 0.0 <= self.min_opportunity_priority <= 1.0:
            raise ValueError(
                f"min_opportunity_priority must be in [0.0, 1.0], "
                f"got {self.min_opportunity_priority}"
            )


@dataclass(frozen=True, slots=True)
class IndustryStrategicFinding:
    """A strategic finding from industry intelligence analysis.

    Contains evidence and recommendations for industry-specific gaps.
    """

    category: str
    severity: str
    impact: float
    confidence: float
    title: str
    description: str
    evidence: tuple[str, ...] = ()
    affected_keywords: tuple[str, ...] = ()
    affected_urls: tuple[str, ...] = ()
    recommendation: str = ""
    industry_type: IndustryType = IndustryType.GENERAL

    def __post_init__(self) -> None:
        for attr in ("impact", "confidence"):
            val = getattr(self, attr)
            if not 0.0 <= val <= 1.0:
                raise ValueError(f"{attr} must be in [0.0, 1.0], got {val}")


@dataclass(frozen=True, slots=True)
class IndustryIntelligenceResult:
    """Complete industry intelligence synthesis result.

    Combines general SEO intelligence with industry-specific analysis
    to produce actionable, prioritized recommendations.
    """

    profile: IndustryProfile
    total_keywords: int = 0
    ranking_health: dict[str, float] = field(default_factory=dict)
    visibility_score: float = 0.0
    serp_ownership: dict[str, int] = field(default_factory=dict)
    aio_visibility: float = 0.0
    geo_visibility: float = 0.0
    content_health: dict[str, float] = field(default_factory=dict)
    technical_health: dict[str, float] = field(default_factory=dict)
    entity_coverage: float = 0.0
    performance_health: dict[str, float] = field(default_factory=dict)
    competitor_pressure: float = 0.0
    volatility: float = 0.0
    cannibalization_issues: int = 0

    industry_entity_coverage: dict[str, int] = field(default_factory=dict)
    industry_topic_coverage: dict[str, int] = field(default_factory=dict)
    industry_intent_coverage: dict[str, int] = field(default_factory=dict)

    findings: tuple[IndustryStrategicFinding, ...] = ()
    opportunities: tuple[IndustryOpportunity, ...] = ()

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def high_priority_findings(self) -> tuple[IndustryStrategicFinding, ...]:
        return tuple(f for f in self.findings if f.impact >= 0.7)


@dataclass(frozen=True, slots=True)
class IndustryOpportunityScorer:
    """Deterministic scorer for industry opportunities.

    Scoring formula:
    score = base_priority * (impact * 0.4 + coverage * 0.3 + intent_match * 0.2 + entity_gap * 0.1)

    Where:
    - base_priority: 1.0 for high, 0.7 for medium, 0.4 for low
    - impact: 0-1 scale from opportunity
    - coverage: estimated keyword coverage ratio
    - intent_match: 1.0 if intent matches industry focus, 0.5 otherwise
    - entity_gap: 1.0 if entity gap present, 0.5 if not
    """

    @staticmethod
    def score(
        impact: float = 0.5,
        coverage: float = 0.5,
        intent_match: bool = False,
        entity_gap: bool = False,
        base_priority: float = 0.5,
    ) -> float:
        if not 0.0 <= impact <= 1.0:
            impact = 0.5
        if not 0.0 <= coverage <= 1.0:
            coverage = 0.5

        intent_weight = 1.0 if intent_match else 0.5
        gap_weight = 1.0 if entity_gap else 0.5

        score = base_priority * (
            impact * 0.4 + coverage * 0.3 + intent_weight * 0.2 + gap_weight * 0.1
        )

        return round(min(1.0, max(0.0, score)), 4)


__all__ = [
    "CasinoAnalysisResult",
    "CasinoEntity",
    "CasinoEntityType",
    "CasinoSearchIntent",
    "CasinoTopic",
    "CryptoAnalysisResult",
    "CryptoEntity",
    "CryptoEntityType",
    "CryptoSearchIntent",
    "CryptoTopic",
    "IndustryEntity",
    "IndustryIntelligenceResult",
    "IndustryOpportunity",
    "IndustryOpportunityScorer",
    "IndustryProfile",
    "IndustryStrategicFinding",
    "IndustryTopic",
    "IndustryType",
]
