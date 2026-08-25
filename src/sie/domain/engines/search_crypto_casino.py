"""Crypto-Casino Intelligence Engine — cross-domain analysis.

Pure functions for analyzing intersections between casino and cryptocurrency
domains. Identifies opportunities for crypto casino landing pages, payment
methods, deposits, withdrawals, and other cross-domain topics.

No I/O, no network, no LLM dependencies. All analysis is deterministic.
"""

from __future__ import annotations

from collections import defaultdict

from sie.domain.models.industry import (
    CasinoSearchIntent,
    CryptoSearchIntent,
    IndustryEntity,
    IndustryOpportunity,
    IndustryTopic,
)

__all__ = [
    "analyze_crypto_casino_intersections",
    "classify_crypto_casino_intent",
    "detect_crypto_casino_opportunities",
    "identify_crypto_casino_entities",
]

# ── Patterns and keywords ───────────────────────────────────────────────

_TYPES_KEYWORDS = {
    "game": {"slots", "table game", "live dealer", "baccarat", "blackjack", "roulette"},
    "payment_method": {
        "bitcoin",
        "ethereum",
        "bank transfer",
        "credit card",
        "crypto",
        "deposit",
    },
    "bonus": {"welcome bonus", "deposit bonus", "free spins", "cashback"},
    "currency": {"usdt", "usdc", "busd", "btc", "eth", "trb", "sol"},
}

# Actionable recommendation templates
_CRYPTO_PAYMENT_REC = (
    "Create content covering crypto payment methods for casino deposits and withdrawals."
)

_ETH_PAYMENT_REC = "Add Ethereum payment support details for deposit and withdrawal methods."

_STABLECOIN_REC = "Consider adding stablecoin payment options (USDT, USDC) for reduced volatility."

_GAME_SEEKING_REC = "Add content about {kw} to improve coverage for casino games."

_BONUS_REC = "Create content about cryptocurrency-specific bonuses and promotions."

_CRYPTO_EXPLANATION_REC = (
    "Add explanations for crypto deposits and withdrawals for users "
    "unfamiliar with blockchain payments."
)

_MARKET_REC = "Clarify availability for cryptocurrency casino services."

_TOPIC_EXPANSION_REC = "Expand coverage of {topic} with comprehensive content."


def identify_crypto_casino_entities(
    casino_content: str,
    crypto_content: str,
) -> tuple[IndustryEntity, ...]:
    """Identify entities common to both casino and cryptocurrency domains.

    Args:
        casino_content: Content from casino website.
        crypto_content: Content from cryptocurrency website.

    Returns:
        Tuple of IndustryEntity objects representing intersections.
    """
    casino_lower = casino_content.lower()
    crypto_lower = crypto_content.lower()

    intersection_names: set[str] = set()

    for entity_type, keywords in _TYPES_KEYWORDS.items():
        for keyword in keywords:
            if keyword in casino_lower and keyword in crypto_lower:
                intersection_names.add(f"{keyword} ({entity_type})")

    if "bitcoin" in casino_lower and "bitcoin" in crypto_lower:
        intersection_names.add("bitcoin (payment_method)")

    if "ethereum" in casino_lower and "ethereum" in crypto_lower:
        intersection_names.add("ethereum (payment_method)")

    if "usdt" in casino_lower and "usdt" in crypto_lower:
        intersection_names.add("usdt (currency)")

    if "deposit" in casino_lower and "deposit" in crypto_lower:
        intersection_names.add("crypto deposit")

    if "withdrawal" in crypto_lower and "withdrawal" in casino_lower:
        intersection_names.add("crypto withdrawal")

    entities: list[IndustryEntity] = []
    for name in intersection_names:
        entity_type = _classify_intersection_entity(name)
        entities.append(
            IndustryEntity(
                name=name,
                entity_type=entity_type,
                frequency=1,
                confidence=1.0,
                context="Intersection of casino and cryptocurrency domains",
            )
        )

    return tuple(sorted(entities, key=lambda e: e.name.lower()))


def _classify_intersection_entity(name: str) -> str:
    """Classify intersection entity type."""
    name_lower = name.lower()
    if "game" in name_lower or "slot" in name_lower:
        return "game"
    if "payment" in name_lower or "deposit" in name_lower or "withdrawal" in name_lower:
        return "payment_method"
    if "bonus" in name_lower:
        return "bonus"
    if "currency" in name_lower or "usdt" in name_lower or "btc" in name_lower:
        return "currency"
    if "crypto" in name_lower:
        return "payment_method"
    return "other"


def analyze_crypto_casino_intersections(
    casino_content: str,
    crypto_content: str,
    *,
    target_domain: str = "",
) -> tuple[IndustryTopic, ...]:
    """Analyze content for crypto-casino junction topics.

    Args:
        casino_content: Content from casino website.
        crypto_content: Content from cryptocurrency website.
        target_domain: Target domain being tracked.

    Returns:
        Tuple of IndustryTopic objects representing intersections.
    """
    intersection_entities = identify_crypto_casino_entities(casino_content, crypto_content)

    if not intersection_entities:
        return ()

    topics: dict[str, list[IndustryEntity]] = defaultdict(list)

    for entity in intersection_entities:
        if "payment" in entity.entity_type:
            topics["crypto_payments"].append(entity)
        elif "game" in entity.entity_type:
            topics["crypto_games"].append(entity)
        elif "bonus" in entity.entity_type:
            topics["crypto_bonuses"].append(entity)
        elif "currency" in entity.entity_type:
            topics["crypto_currencies"].append(entity)
        else:
            topics["general_intersections"].append(entity)

    result: list[IndustryTopic] = []
    for topic_label, ents in topics.items():
        result.append(
            IndustryTopic(
                topic_label=topic_label.replace("_", " ").title(),
                entities=tuple(ents),
                relevance_score=0.8,
                keyword=topic_label.replace("_", " "),
            )
        )

    result.sort(key=lambda t: -t.relevance_score)

    return tuple(result)


def detect_crypto_casino_opportunities(
    casino_content: str,
    crypto_content: str,
    *,
    target_domain: str = "",
    min_priority: float = 0.5,
) -> tuple[IndustryOpportunity, ...]:
    """Detect SEO opportunities at the crypto-casino intersection.

    Args:
        casino_content: Content from casino website.
        crypto_content: Content from cryptocurrency website.
        target_domain: Target domain being tracked.
        min_priority: Minimum priority score for opportunities.

    Returns:
        Tuple of IndustryOpportunity objects.
    """
    opportunities: list[IndustryOpportunity] = []

    casino_lower = casino_content.lower()
    crypto_lower = crypto_content.lower()

    if "bitcoin" not in casino_lower and "btc" not in casino_lower:
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-payment-methods",
                entities=(),
                intent=CasinoSearchIntent.PAYMENT_METHOD,
                priority=0.8,
                recommendation=_CRYPTO_PAYMENT_REC,
                impact=0.9,
                effort=0.6,
            )
        )

    if "ethereum" not in casino_lower and "eth" not in casino_lower:
        opportunities.append(
            IndustryOpportunity(
                topic="ethereum-payments",
                entities=(),
                intent=CasinoSearchIntent.PAYMENT_METHOD,
                priority=0.7,
                recommendation=_ETH_PAYMENT_REC,
                impact=0.8,
                effort=0.6,
            )
        )

    if "usdt" not in casino_lower and "usdc" not in crypto_lower:
        opportunities.append(
            IndustryOpportunity(
                topic="stablecoin-payments",
                entities=(),
                intent=CasinoSearchIntent.PAYMENT_METHOD,
                priority=0.7,
                recommendation=_STABLECOIN_REC,
                impact=0.7,
                effort=0.5,
            )
        )

    game_keywords = {"slot", "game", "jackpot", "live dealer"}
    found_game_keywords = {kw for kw in game_keywords if kw in casino_lower}
    if len(found_game_keywords) < 3:
        missing_keywords = game_keywords - found_game_keywords
        for kw in missing_keywords:
            opportunities.append(
                IndustryOpportunity(
                    topic=f"{kw}-coverage",
                    entities=(),
                    intent=CasinoSearchIntent.GAME_SEEKING,
                    priority=0.6,
                    recommendation=_GAME_SEEKING_REC.format(kw=kw),
                    impact=0.6,
                    effort=0.7,
                )
            )

    bonus_keywords = {"bonus", "promo", "welcome", "deposit bonus"}
    missing_bonus = {
        kw
        for kw in bonus_keywords
        if kw in crypto_lower
        for kw2 in bonus_keywords
        if kw2 in casino_lower
    }
    if not missing_bonus:
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-bonuses",
                entities=(),
                intent=CasinoSearchIntent.BONUS_SEEKING,
                priority=0.8,
                recommendation=_BONUS_REC,
                impact=0.8,
                effort=0.6,
            )
        )

    deposit_keywords = {"deposit", "withdrawal", "payment method", "wallet"}
    crypto_payment_content = any(kw in crypto_lower for kw in deposit_keywords)
    if not crypto_payment_content:
        opportunities.append(
            IndustryOpportunity(
                topic="crypto-payment-explanation",
                entities=(),
                intent=CryptoSearchIntent.PAYMENT_METHOD,
                priority=0.7,
                recommendation=_CRYPTO_EXPLANATION_REC,
                impact=0.7,
                effort=0.6,
            )
        )

    market_keywords = {"usa", "united states", "uk", "canada", "australia"}
    missing_markets = {kw for kw in market_keywords if kw not in casino_lower}
    for kw in missing_markets:
        if kw in crypto_lower:
            continue
        opportunities.append(
            IndustryOpportunity(
                topic=f"{kw}-availability",
                entities=(),
                intent=CasinoSearchIntent.GEO_REGULATORY,
                priority=0.6,
                recommendation=_MARKET_REC,
                impact=0.6,
                effort=0.7,
            )
        )

    topics = analyze_crypto_casino_intersections(
        casino_content, crypto_content, target_domain=target_domain
    )

    for topic in topics:
        missing = False
        for _entity in topic.entities:
            pass

        if not missing and topic.entity_count < 3:
            opportunities.append(
                IndustryOpportunity(
                    topic=topic.topic_label.lower().replace(" ", "_"),
                    entities=topic.entities,
                    intent=CasinoSearchIntent.INFORMATIONAL,
                    priority=0.5,
                    recommendation=_TOPIC_EXPANSION_REC.format(topic=topic.topic_label),
                    impact=0.6,
                    effort=0.7,
                )
            )

    opportunities.sort(key=lambda o: -o.priority)

    return tuple(opportunities)


def classify_crypto_casino_intent(keyword: str) -> CasinoSearchIntent | CryptoSearchIntent:
    """Classify search intent for crypto-casino related keywords.

    Args:
        keyword: Search query to classify.

    Returns:
        Appropriate search intent enum value.
    """
    if not keyword:
        return CasinoSearchIntent.OTHER

    keyword_lower = keyword.lower()

    crypto_casino_patterns = [
        "crypto casino",
        "bitcoin casino",
        "ethereum casino",
        "btc casino",
        "eth casino",
        "crypto gambling",
        "cryptocurrency casino",
        "bitcoin slots",
        "eth slots",
    ]

    game_seeking_patterns = [
        "game",
        "slot",
        "jackpot",
        "table game",
        "live dealer",
    ]

    bonus_seeking_patterns = [
        "bonus",
        "promo",
        "offer",
        "deal",
        "free spin",
    ]

    payment_patterns = [
        "deposit",
        "withdrawal",
        "payment method",
        "wallet",
    ]

    for pattern in crypto_casino_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.BONUS_SEEKING

    for pattern in game_seeking_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.GAME_SEEKING

    for pattern in bonus_seeking_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.BONUS_SEEKING

    for pattern in payment_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.PAYMENT_METHOD

    return CasinoSearchIntent.INFORMATIONAL
