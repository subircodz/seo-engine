"""Casino Intelligence Engine — deterministic casino domain analysis.

Pure functions for extracting casino entities, topics, search intent,
content gaps, and entity gaps from casino-related content.

No I/O, no network, no LLM dependencies. All analysis is deterministic.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from sie.domain.models.industry import (
    CasinoAnalysisResult,
    CasinoEntity,
    CasinoEntityType,
    CasinoSearchIntent,
    CasinoTopic,
)

__all__ = [
    "analyze_casino_content",
    "classify_casino_intent",
    "detect_casino_content_gaps",
    "detect_casino_entity_gaps",
    "extract_casino_entities",
]

# Casino-specific game name patterns - only match known casino game terms
_PATTERN_GAME_NAME = re.compile(
    r"\b("
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}"
    r"(?:\s+(?:Slot|Game|Jackpot|Roulette|Blackjack|Baccarat|Poker|Craps|Keno|Bingo))?"
    r")\b"
)
_PATTERN_DOMAIN = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b")
_PATTERN_CURRENCY = re.compile(
    r"\b(btc|BTC|eth|ETH|usdt|USDT|usdc|USDC|trxbank|sol|SOL)\b", re.IGNORECASE
)
_PATTERN_GAME_PROVIDER = re.compile(
    r"\b(NetEnt|Pragmatic|Play\'n\sGo|Yggdrasil|Microgaming|Quickspin|EVO|RTP)\b", re.IGNORECASE
)

# Known casino game keywords for more precise matching
_CASINO_GAME_KEYWORDS = frozenset({
    "slot", "slots", "jackpot", "roulette", "blackjack", "baccarat", "poker",
    "craps", "keno", "bingo", "video poker", "live dealer", "table game",
    "progressive", "megaways", "hold and win", "free spins", "bonus game",
})

_MIN_ENTITY_LENGTH = 2
_MAX_ENTITY_LENGTH = 100
_MIN_FREQUENCY = 1


def extract_casino_entities(
    text: str,
    *,
    min_frequency: int = _MIN_FREQUENCY,
    max_entities: int = 200,
) -> tuple[CasinoEntity, ...]:
    """Extract casino-specific entities from text using deterministic patterns.

    Args:
        text: Content to analyze for casino entities.
        min_frequency: Minimum occurrence count for entity inclusion.
        max_entities: Maximum number of entities to return.

    Returns:
        Tuple of CasinoEntity objects, sorted by frequency (descending).
    """
    if not text or not text.strip():
        return ()

    candidates: Counter[str] = Counter()

    # Extract casino game names - only keep those with casino-related keywords
    for match in _PATTERN_GAME_NAME.finditer(text):
        phrase = match.group(1).strip()
        if len(phrase) >= _MIN_ENTITY_LENGTH and len(phrase) <= _MAX_ENTITY_LENGTH:
            phrase_lower = phrase.lower()
            # Only count as casino game if it contains casino-related keywords
            if any(kw in phrase_lower for kw in _CASINO_GAME_KEYWORDS):
                candidates[phrase] += 1

    # Extract known game providers
    for match in _PATTERN_GAME_PROVIDER.finditer(text):
        provider = match.group(1).strip()
        if len(provider) >= _MIN_ENTITY_LENGTH:
            candidates[provider] += 1

    # Extract currency mentions
    for match in _PATTERN_CURRENCY.finditer(text):
        currency = match.group(1).strip().upper()
        if len(currency) >= _MIN_ENTITY_LENGTH:
            candidates[currency] += 1

    entities: list[CasinoEntity] = []
    for entity_text, freq in candidates.most_common(max_entities):
        if freq < min_frequency:
            continue

        entity_type = _classify_casino_entity(entity_text)
        confidence = _estimate_casino_entity_confidence(entity_text, freq)

        entities.append(
            CasinoEntity(
                name=entity_text,
                entity_type=entity_type,
                frequency=freq,
                confidence=confidence,
            )
        )

    return tuple(entities)


def _classify_casino_entity(text: str) -> CasinoEntityType:
    """Classify a text string as a casino entity type."""
    text_lower = text.lower()

    if any(word in text_lower for word in ["bonus", "promo", "offer", "deal"]):
        return CasinoEntityType.BONUS
    if any(word in text_lower for word in ["game", "slot", "wheel", "multiplier"]):
        return CasinoEntityType.GAME
    if any(word in text_lower for word in ["provider", "studio", "developer", "software"]):
        return CasinoEntityType.GAME_PROVIDER
    if any(word in text_lower for word in ["license", "licensee", "jurisdiction"]):
        return CasinoEntityType.LICENSE
    if any(word in text_lower for word in ["regulator", "authority", "commission"]):
        return CasinoEntityType.REGULATOR
    if any(word in text_lower for word in ["jackpot", "progressive", "prize"]):
        return CasinoEntityType.JACKPOT
    if any(word in text_lower for word in ["country", "region", "territory", "territory"]):
        return CasinoEntityType.COUNTRY
    if any(word in text_lower for word in ["deposit", "cashier", "banking", "payment"]):
        return CasinoEntityType.DEPOSIT
    if any(word in text_lower for word in ["withdrawal", "payout", "request", "bonus"]):
        return CasinoEntityType.WITHDRAWAL
    # Removed: domain classification (". in text") - domains are not casino entities
    # Currency codes (BTC, ETH, etc.) are handled by _PATTERN_CURRENCY
    return CasinoEntityType.OTHER


def _estimate_casino_entity_confidence(text: str, frequency: int) -> float:
    """Estimate confidence for casino entity detection."""
    base = 0.3

    word_count = len(text.split())
    if word_count >= 3:
        base += 0.2
    elif word_count >= 2:
        base += 0.1

    if frequency >= 5:
        base += 0.2
    elif frequency >= 3:
        base += 0.1

    # Removed: "." in text boost - domains are not casino entities
    # Game providers and known casino terms get implicit confidence from pattern matching

    return round(min(1.0, base), 2)


def classify_casino_intent(keyword: str) -> CasinoSearchIntent:
    """Classify search intent for a casino-related keyword.

    Args:
        keyword: Search query to classify.

    Returns:
        CasinoSearchIntent classification.
    """
    if not keyword:
        return CasinoSearchIntent.OTHER

    keyword_lower = keyword.lower()

    navigational_patterns = [
        "login",
        "register",
        "signup",
        "account",
        "dashboard",
        "portal",
        "profile",
    ]

    bonus_patterns = [
        "bonus",
        "promo",
        "offer",
        "no deposit",
        "free spin",
        "wagering",
        "bonus code",
    ]

    game_patterns = [
        "game",
        "slot",
        "jackpot",
        "table game",
        "live dealer",
        "blackjack",
        "roulette",
        "baccarat",
        "poker",
        "craps",
        "dice",
        "keno",
        "video poker",
        "live casino",
    ]

    payment_patterns = [
        "deposit",
        "withdrawal",
        "payment method",
        "crypto",
        "bitcoin",
        "ethereum",
        "wallet",
        "banking",
    ]

    comparison_patterns = [
        "review",
        "compare",
        "best",
        "top",
        "vs",
        "versus",
        "rating",
        "ranking",
        "test",
    ]

    for pattern in navigational_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.NAVIGATIONAL

    for pattern in bonus_patterns:
        if pattern in keyword_lower:
            if "code" in keyword_lower or "claim" in keyword_lower:
                return CasinoSearchIntent.BONUS_SEEKING
            return CasinoSearchIntent.BONUS_SEEKING

    for pattern in game_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.GAME_SEEKING

    for pattern in payment_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.PAYMENT_METHOD

    for pattern in comparison_patterns:
        if pattern in keyword_lower:
            return CasinoSearchIntent.COMPARISON

    if any(word in keyword_lower for word in ["best", "top", "guide", "strategy"]):
        return CasinoSearchIntent.INFORMATIONAL

    return CasinoSearchIntent.INFORMATIONAL


def analyze_casino_content(
    content: str,
    *,
    base_url: str = "",
) -> CasinoAnalysisResult:
    """Perform comprehensive casino content analysis.

    Args:
        content: Content to analyze.
        base_url: Target domain URL for entity filtering.

    Returns:
        CasinoAnalysisResult with entities, topics, and gaps.
    """
    entities = extract_casino_entities(content)

    topics = _cluster_casino_topics(entities, content)

    content_gaps = _detect_casino_content_gaps(topics)

    entity_gaps = _detect_casino_entity_gaps(entities)

    entities_by_type: dict[str, int] = {}
    for entity in entities:
        entity_type = entity.entity_type.value
        entities_by_type[entity_type] = entities_by_type.get(entity_type, 0) + 1

    return CasinoAnalysisResult(
        total_entities=len(entities),
        entities_by_type=entities_by_type,
        topics=topics,
        content_gaps=content_gaps,
        entity_gaps=entity_gaps,
    )


def _cluster_casino_topics(
    entities: tuple[CasinoEntity, ...],
    content: str,
) -> tuple[CasinoTopic, ...]:
    """Cluster casino entities into topics based on context and type."""
    if not entities:
        return ()

    by_type: dict[CasinoEntityType, list[CasinoEntity]] = defaultdict(list)
    for entity in entities:
        by_type[entity.entity_type].append(entity)

    topics: list[CasinoTopic] = []
    for entity_type, type_entities in by_type.items():
        if type_entities:
            topic_label = f"{entity_type.value.replace('_', ' ').title()} Topic"
            total_freq = sum(e.frequency for e in type_entities)
            avg_freq = total_freq / len(type_entities)

            topics.append(
                CasinoTopic(
                    topic_label=topic_label,
                    entities=tuple(type_entities[:10]),
                    relevance_score=round(avg_freq / 10.0, 4) if avg_freq > 0 else 0.0,
                    keyword=entity_type.value.replace("_", " "),
                )
            )

    topics.sort(key=lambda t: -t.relevance_score)

    return tuple(topics)


def _detect_casino_content_gaps(
    topics: tuple[CasinoTopic, ...],
) -> tuple[str, ...]:
    """Identify content gaps in casino topics."""
    expected_topics = {
        "game",
        "game_provider",
        "bonus",
        "payment_method",
        "license",
        "regulator",
        "country",
        "currency",
    }

    found_topics = {t.topic_label.lower().replace(" ", "_") for t in topics}

    gaps: set[str] = set()
    for expected in expected_topics:
        if expected not in found_topics:
            gaps.add(f"Missing coverage for {expected}")

    return tuple(sorted(gaps))


def _detect_casino_entity_gaps(
    entities: tuple[CasinoEntity, ...],
) -> tuple[CasinoEntity, ...]:
    """Detect which entity types are missing."""
    found_types = {e.entity_type for e in entities}

    missing_entities: list[CasinoEntity] = []
    for missing_type in CasinoEntityType:
        if missing_type not in found_types and missing_type != CasinoEntityType.OTHER:
            missing_entities.append(
                CasinoEntity(
                    name=f"Missing {missing_type.value}",
                    entity_type=missing_type,
                    frequency=1,
                    confidence=1.0,
                    context="Detected gap in content coverage",
                )
            )

    missing_entities.sort(key=lambda e: e.entity_type.value)

    return tuple(missing_entities)


def detect_casino_content_gaps(
    topics: tuple[CasinoTopic, ...],
) -> tuple[str, ...]:
    """Public wrapper for casino content gap detection."""
    return _detect_casino_content_gaps(topics)


def detect_casino_entity_gaps(
    entities: tuple[CasinoEntity, ...],
) -> tuple[CasinoEntity, ...]:
    """Public wrapper for casino entity gap detection."""
    return _detect_casino_entity_gaps(entities)
