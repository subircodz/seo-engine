"""Industry Intelligence Synthesis engine (Phase 10).

Orchestrates industry-specific intelligence synthesis, combining:
- General SEO intelligence (ranking, visibility, SERP)
- Industry entity coverage (casino, crypto, crypto-casino)
- Content gaps analysis
- Competitor analysis
- Opportunity identification

Produces deterministic, prioritized strategic findings.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from sie.domain.engines.search_casino import (
    extract_casino_entities,
)
from sie.domain.engines.search_crypto import (
    extract_crypto_entities,
)
from sie.domain.engines.search_crypto_casino import (
    identify_crypto_casino_entities,
)
from sie.domain.models.industry import (
    CasinoSearchIntent,
    CryptoSearchIntent,
    IndustryIntelligenceResult,
    IndustryOpportunity,
    IndustryOpportunityScorer,
    IndustryProfile,
    IndustryStrategicFinding,
    IndustryType,
)

__all__ = [
    "generate_industry_intelligence",
    "synthesize_industry_findings",
]

# ── Finding categories ─────────────────────────────────────────────────────

_CAT_RANKING = "ranking"
_CAT_CONTENT = "content"
_CAT_TECHNICAL = "technical"
_CAT_SERP = "serp"
_CAT_AIO = "aio"
_CAT_GEO = "geo"
_CAT_ENTITY = "entity"
_CAT_PERFORMANCE = "performance"
_CAT_COMPETITOR = "competitor"
_CAT_CANNIBALIZATION = "cannibalization"
_CAT_VOLATILITY = "volatility"
_CAT_INDUSTRY = "industry"


@dataclass(frozen=True)
class _IndustryInputs:
    """Normalized inputs for industry intelligence synthesis."""

    profile: IndustryProfile
    visibility_score: float = 0.0
    keywords_not_ranking: int = 0
    total_keywords: int = 0
    entity_coverage: float = 0.0
    entity_gap_count: int = 0
    ranking_health: dict[str, float] = field(default_factory=dict)
    content_health: dict[str, float] = field(default_factory=dict)
    technical_health: dict[str, float] = field(default_factory=dict)
    aio_visibility: float = 0.0
    geo_visibility: float = 0.0
    performance_health: dict[str, float] = field(default_factory=dict)
    volatility_score: float = 0.0
    cannibalization_count: int = 0
    casino_entities: tuple = ()
    crypto_entities: tuple = ()
    casino_analysis: object = None
    crypto_analysis: object = None
    content: str = ""
    competitor_domains: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


def generate_industry_intelligence(
    *,
    profile: IndustryProfile,
    visibility_score: float = 0.0,
    keywords_not_ranking: int = 0,
    total_keywords: int = 0,
    entity_coverage: float = 0.0,
    entity_gap_count: int = 0,
    ranking_health: dict[str, float] | None = None,
    content_health: dict[str, float] | None = None,
    technical_health: dict[str, float] | None = None,
    aio_visibility: float = 0.0,
    geo_visibility: float = 0.0,
    performance_health: dict[str, float] | None = None,
    volatility: float = 0.0,
    cannibalization: int = 0,
    content: str = "",
    crypto_content: str = "",
    competitor_domains: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
) -> IndustryIntelligenceResult:
    """Generate industry-intelligence synthesis from all inputs.

    True deterministic function: same inputs always produce same output.
    No network calls, no LLM dependencies, no random values.
    """
    inputs = _IndustryInputs(
        profile=profile,
        visibility_score=visibility_score,
        keywords_not_ranking=keywords_not_ranking,
        total_keywords=total_keywords,
        entity_coverage=entity_coverage,
        entity_gap_count=entity_gap_count,
        ranking_health=ranking_health or {},
        content_health=content_health or {},
        technical_health=technical_health or {},
        aio_visibility=aio_visibility,
        geo_visibility=geo_visibility,
        performance_health=performance_health or {},
        volatility_score=volatility,
        cannibalization_count=cannibalization,
        content=content,
        competitor_domains=competitor_domains,
        keywords=keywords,
    )

    return synthesize_industry_findings(inputs)


def synthesize_industry_findings(inputs: _IndustryInputs) -> IndustryIntelligenceResult:
    """Synthesize industry findings from normalized inputs.

    Combines generic SEO metrics with industry-specific intelligence
    to produce indexed, prioritized strategic findings.
    """
    findings: list[IndustryStrategicFinding] = []
    opportunities: list[IndustryOpportunity] = []

    industry_type = inputs.profile.industry_type

    findings.extend(_analyze_ranking_intelligence(inputs, industry_type))
    findings.extend(_analyze_content_intelligence(inputs, industry_type))
    findings.extend(_analyze_entity_intelligence(inputs, industry_type))
    findings.extend(_analyze_competitor_intelligence(inputs, industry_type))
    findings.extend(_analyze_industry_specific_intelligence(inputs, industry_type))

    if inputs.cannibalization_count > 0:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_CANNIBALIZATION,
                severity="high",
                impact=0.8,
                confidence=0.9,
                title=f"Cannibalization detected ({inputs.cannibalization_count} instances)",
                description=(
                    "Multiple pages compete for the same keywords. "
                    "Consolidate content or implement canonical tags."
                ),
                recommendation="Review cannibalized keywords and fix content overlap.",
                industry_type=industry_type,
            )
        )

    if inputs.keywords_not_ranking > 0 and inputs.total_keywords > 0:
        pct = inputs.keywords_not_ranking / inputs.total_keywords
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_INDUSTRY,
                severity="high" if pct > 0.5 else "medium",
                impact=0.7,
                confidence=0.9,
                title=f"{inputs.keywords_not_ranking} keywords not ranking",
                description=(
                    f"{inputs.keywords_not_ranking} of {inputs.total_keywords} "
                    f"keywords ({pct:.0%}) have no current ranking."
                ),
                recommendation="Create or improve content targeting unranked keywords.",
                industry_type=industry_type,
            )
        )

    if industry_type == IndustryType.CASINO:
        opportunities.extend(_generate_casino_opportunities(inputs))
    elif industry_type == IndustryType.CRYPTO:
        opportunities.extend(_generate_crypto_opportunities(inputs))
    elif industry_type == IndustryType.CRYPTO_CASINO:
        opportunities.extend(_generate_crypto_casino_opportunities(inputs))

    findings.sort(key=lambda f: (-f.impact, -f.confidence))
    opportunities.sort(key=lambda o: -o.priority)

    return IndustryIntelligenceResult(
        profile=inputs.profile,
        visibility_score=inputs.visibility_score,
        ranking_health=inputs.ranking_health,
        entity_coverage=inputs.entity_coverage,
        content_health=inputs.content_health,
        technical_health=inputs.technical_health,
        aio_visibility=inputs.aio_visibility,
        geo_visibility=inputs.geo_visibility,
        performance_health=inputs.performance_health,
        competitor_pressure=(
            inputs.profile.target_domain.lower() in " ".join(inputs.competitor_domains).lower()
        ),
        volatility=inputs.volatility_score,
        cannibalization_issues=inputs.cannibalization_count,
        industry_entity_coverage={},
        industry_topic_coverage={},
        industry_intent_coverage={},
        findings=tuple(findings),
        opportunities=tuple(opportunities),
    )


def _analyze_ranking_intelligence(
    inputs: _IndustryInputs, industry_type: IndustryType
) -> list[IndustryStrategicFinding]:
    findings = []

    if inputs.visibility_score < 0.3 and inputs.total_keywords > 0:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_RANKING,
                severity="high",
                impact=0.9,
                confidence=0.95,
                title="Low visibility score",
                description=(
                    f"Visibility score is {inputs.visibility_score:.2f} (below 0.3 threshold). "
                    "Major SEO improvements needed."
                ),
                recommendation="Review content quality, technical SEO, and authority building.",
                industry_type=industry_type,
            )
        )

    return findings


def _analyze_content_intelligence(
    inputs: _IndustryInputs, industry_type: IndustryType
) -> list[IndustryStrategicFinding]:
    findings = []

    if inputs.content_health:
        weak_topics = [k for k, v in inputs.content_health.items() if v < 0.5]
        if weak_topics:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_CONTENT,
                    severity="medium",
                    impact=0.6,
                    confidence=0.8,
                    title=f"Weak content coverage for: {', '.join(weak_topics[:3])}",
                    description=f"Content health scores below 0.5 for: {', '.join(weak_topics)}",
                    recommendation="Improve content depth and quality for these topics.",
                    industry_type=industry_type,
                )
            )

    return findings


def _analyze_entity_intelligence(
    inputs: _IndustryInputs, industry_type: IndustryType
) -> list[IndustryStrategicFinding]:
    findings = []

    if inputs.entity_coverage > 0 and inputs.entity_coverage < 0.3:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_ENTITY,
                severity="medium",
                impact=0.6,
                confidence=0.7,
                title="Low entity coverage",
                description=(
                    f"Entity coverage is {inputs.entity_coverage:.0%}, indicating "
                    "limited topic authority."
                ),
                recommendation="Expand content to cover key industry entities.",
                industry_type=industry_type,
            )
        )

    if inputs.entity_gap_count > 0:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_ENTITY,
                severity="medium",
                impact=0.6,
                confidence=0.75,
                title=f"{inputs.entity_gap_count} entity coverage gaps",
                description="Competitors mention entities not covered in target content.",
                recommendation="Add content covering missing entities.",
                industry_type=industry_type,
            )
        )

    return findings


def _analyze_competitor_intelligence(
    inputs: _IndustryInputs, industry_type: IndustryType
) -> list[IndustryStrategicFinding]:
    findings = []

    if inputs.competitor_domains:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_COMPETITOR,
                severity="medium",
                impact=0.7,
                confidence=0.8,
                title="Competitor presence detected",
                description=f"Found in {len(inputs.competitor_domains)} competitor domains.",
                recommendation="Analyze competitor content strategy and identify gaps.",
                industry_type=industry_type,
            )
        )

    return findings


def _analyze_industry_specific_intelligence(
    inputs: _IndustryInputs, industry_type: IndustryType
) -> list[IndustryStrategicFinding]:
    findings = []

    content = inputs.content
    if not content and inputs.profile.industry_type != IndustryType.GENERAL:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_INDUSTRY,
                severity="low",
                impact=0.5,
                confidence=0.6,
                title="No industry content provided",
                description="Industry-specific analysis requires content input.",
                recommendation="Provide industry-relevant content for analysis.",
                industry_type=industry_type,
            )
        )
        return findings

    if industry_type == IndustryType.CASINO:
        findings.extend(_analyze_casino_intelligence(inputs))
    elif industry_type == IndustryType.CRYPTO:
        findings.extend(_analyze_crypto_intelligence(inputs))
    elif industry_type == IndustryType.CRYPTO_CASINO:
        findings.extend(_analyze_crypto_casino_intelligence(inputs))

    return findings


def _analyze_casino_intelligence(inputs: _IndustryInputs) -> list[IndustryStrategicFinding]:
    findings = []

    if not inputs.content:
        return findings

    entities = extract_casino_entities(inputs.content)
    if entities:
        entity_types = defaultdict(int)
        for e in entities:
            entity_types[e.entity_type] += 1

        if "game" not in entity_types or entity_types["game"] < 3:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.6,
                    confidence=0.7,
                    title="Limited casino game coverage",
                    description="Content has limited coverage of casino games and topics.",
                    recommendation="Add content about games, slots, table games, and live dealer.",
                    industry_type=IndustryType.CASINO,
                )
            )

        if "bonus" not in entity_types:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.6,
                    confidence=0.7,
                    title="Missing bonus content",
                    description="No bonus-specific content detected in target content.",
                    recommendation="Add content about welcome bonuses, deposit bonuses.",
                    industry_type=IndustryType.CASINO,
                )
            )

        if "payment_method" not in entity_types:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.5,
                    confidence=0.6,
                    title="Missing payment method content",
                    description="No payment method details detected.",
                    recommendation="Document accepted payment methods and processing times.",
                    industry_type=IndustryType.CASINO,
                )
            )

    return findings


def _analyze_crypto_intelligence(inputs: _IndustryInputs) -> list[IndustryStrategicFinding]:
    findings = []

    if not inputs.content:
        return findings

    entities = extract_crypto_entities(inputs.content)
    if entities:
        entity_types = defaultdict(int)
        for e in entities:
            entity_types[e.entity_type] += 1

        if "coin" not in entity_types and "token" not in entity_types:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.6,
                    confidence=0.7,
                    title="Missing cryptocurrency content",
                    description="No coins or tokens mentioned in content.",
                    recommendation="Add information about supported cryptocurrencies and tokens.",
                    industry_type=IndustryType.CRYPTO,
                )
            )

        if "network" not in entity_types:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.5,
                    confidence=0.6,
                    title="Missing network information",
                    description="No blockchain network details detected.",
                    recommendation="Explain supported networks and transaction methods.",
                    industry_type=IndustryType.CRYPTO,
                )
            )

        if "wallet" not in entity_types:
            findings.append(
                IndustryStrategicFinding(
                    category=_CAT_INDUSTRY,
                    severity="medium",
                    impact=0.5,
                    confidence=0.6,
                    title="Missing wallet guidance",
                    description="No wallet setup or usage instructions found.",
                    recommendation="Add wallet setup guides and support information.",
                    industry_type=IndustryType.CRYPTO,
                )
            )

    return findings


def _analyze_crypto_casino_intelligence(inputs: _IndustryInputs) -> list[IndustryStrategicFinding]:
    findings = []

    if not inputs.content:
        return findings

    crypto_casino_entities = identify_crypto_casino_entities(inputs.content, inputs.content)

    if not crypto_casino_entities:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_INDUSTRY,
                severity="medium",
                impact=0.7,
                confidence=0.8,
                title="Limited crypto-casino intersection",
                description="Content lacks intersection of casino and crypto topics.",
                recommendation="Add content about crypto payments, BTC deposits.",
                industry_type=IndustryType.CRYPTO_CASINO,
            )
        )

    content_lower = inputs.content.lower()
    found_keywords = []
    for kw in ["bitcoin", "ethereum", "cryptocurrency", "crypto"]:
        if kw in content_lower:
            found_keywords.append(kw)

    if len(found_keywords) < 2:
        findings.append(
            IndustryStrategicFinding(
                category=_CAT_INDUSTRY,
                severity="medium",
                impact=0.6,
                confidence=0.75,
                title="Insufficient crypto terminology",
                description=f"Only {len(found_keywords)} crypto keywords found: {found_keywords}",
                recommendation="Add more crypto-related keywords and concepts.",
                industry_type=IndustryType.CRYPTO_CASINO,
            )
        )

    return findings


def _generate_casino_opportunities(inputs: _IndustryInputs) -> list[IndustryOpportunity]:
    opportunities = []
    content_lower = inputs.content.lower()

    has_game_content = any(
        word in content_lower
        for word in [
            "game",
            "slot",
            "table game",
            "live dealer",
            "blackjack",
            "roulette",
            "baccarat",
        ]
    )
    if not has_game_content:
        score = IndustryOpportunityScorer.score(
            impact=0.6, coverage=0.5, intent_match=True, entity_gap=True, base_priority=0.6
        )
        opportunities.append(
            IndustryOpportunity(
                topic="casino-game-coverage",
                entities=(),
                intent=CasinoSearchIntent.GAME_SEEKING,
                priority=score,
                recommendation="Add content about casino games, slots, and table games.",
                impact=0.6,
                effort=0.7,
            )
        )

    has_bonus_content = any(
        word in content_lower for word in ["bonus", "promo", "offer", "deal", "free spin"]
    )
    if not has_bonus_content:
        score = IndustryOpportunityScorer.score(
            impact=0.7, coverage=0.6, intent_match=True, entity_gap=True, base_priority=0.7
        )
        opportunities.append(
            IndustryOpportunity(
                topic="casino-bonus-coverage",
                entities=(),
                intent=CasinoSearchIntent.BONUS_SEEKING,
                priority=score,
                recommendation="Create content about bonuses, promotions, and welcome offers.",
                impact=0.7,
                effort=0.6,
            )
        )

    return opportunities


def _generate_crypto_opportunities(inputs: _IndustryInputs) -> list[IndustryOpportunity]:
    opportunities = []
    content_lower = inputs.content.lower()

    if "bitcoin" not in content_lower and "btc" not in content_lower:
        score = IndustryOpportunityScorer.score(
            impact=0.7, coverage=0.6, intent_match=True, entity_gap=True, base_priority=0.7
        )
        opportunities.append(
            IndustryOpportunity(
                topic="bitcoin-payment-coverage",
                entities=(),
                intent=CryptoSearchIntent.PAYMENT_METHOD,
                priority=score,
                recommendation="Add content about Bitcoin payments and wallets.",
                impact=0.7,
                effort=0.6,
            )
        )

    if "ethereum" not in content_lower and "eth" not in content_lower:
        score = IndustryOpportunityScorer.score(
            impact=0.7, coverage=0.6, intent_match=True, entity_gap=True, base_priority=0.7
        )
        opportunities.append(
            IndustryOpportunity(
                topic="ethereum-payment-coverage",
                entities=(),
                intent=CryptoSearchIntent.PAYMENT_METHOD,
                priority=score,
                recommendation="Add content about Ethereum payments and wallets.",
                impact=0.7,
                effort=0.6,
            )
        )

    return opportunities


def _generate_crypto_casino_opportunities(inputs: _IndustryInputs) -> list[IndustryOpportunity]:
    opportunities = []
    content_lower = inputs.content.lower()

    if "bitcoin" not in content_lower and "btc" not in content_lower:
        score = IndustryOpportunityScorer.score(
            impact=0.8, coverage=0.7, intent_match=True, entity_gap=True, base_priority=0.8
        )
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-casino-bitcoin",
                entities=(),
                intent=CasinoSearchIntent.PAYMENT_METHOD,
                priority=score,
                recommendation="Add content about Bitcoin casino deposits and withdrawals.",
                impact=0.8,
                effort=0.6,
            )
        )

    if "ethereum" not in content_lower and "eth" not in content_lower:
        score = IndustryOpportunityScorer.score(
            impact=0.8, coverage=0.7, intent_match=True, entity_gap=True, base_priority=0.8
        )
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-casino-ethereum",
                entities=(),
                intent=CasinoSearchIntent.PAYMENT_METHOD,
                priority=score,
                recommendation="Add content about Ethereum casino deposits and withdrawals.",
                impact=0.8,
                effort=0.6,
            )
        )

    if "slot" not in content_lower and "game" not in content_lower:
        score = IndustryOpportunityScorer.score(
            impact=0.6, coverage=0.5, intent_match=True, entity_gap=True, base_priority=0.6
        )
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-casino-games",
                entities=(),
                intent=CasinoSearchIntent.GAME_SEEKING,
                priority=score,
                recommendation="Add content about crypto casino games and slots.",
                impact=0.6,
                effort=0.7,
            )
        )

    return opportunities
