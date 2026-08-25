"""Cryptocurrency Intelligence Engine — deterministic crypto domain analysis.

Pure functions for extracting cryptocurrency entities, topics, search intent,
content gaps, and entity gaps from crypto-related content.

No I/O, no network, no LLM dependencies. All analysis is deterministic.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from sie.domain.models.industry import (
    CryptoAnalysisResult,
    CryptoEntity,
    CryptoEntityType,
    CryptoSearchIntent,
    CryptoTopic,
)

__all__ = [
    "analyze_crypto_content",
    "classify_crypto_intent",
    "detect_crypto_content_gaps",
    "detect_crypto_entity_gaps",
    "extract_crypto_entities",
]

_PATTERN_CRYPTO_NAME = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")
_PATTERN_DOMAIN = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b")
_PATTERN_CURRENCY_SYMBOL = re.compile(
    r"\b(BTC|ETH|USDT|USDC|TRX|SOL|XRP|ADA|DOT|BCH)\b", re.IGNORECASE
)
_PATTERN_CRYPTO_ADDRESS = re.compile(r"\b(0x[a-fA-F0-9]{40}|[13][a-km-zA-H1-9]{26,34})\b")
_PATTERN_BLOCKCHAIN = re.compile(
    r"\b(Ethereum|Ethereum Classic|Binance|Smart Chain|Polygon|Solana|"
    r"Cardano|Polkadot|Avalanche|Fantom)\b",
    re.IGNORECASE,
)
_PATTERN_ALLCAPS = re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,}){0,3})\b")

_MIN_ENTITY_LENGTH = 2
_MAX_ENTITY_LENGTH = 100
_MIN_FREQUENCY = 1

_CURRENCY_SYMBOLS = {
    "BTC": "coin",
    "ETH": "coin",
    "USDT": "stablecoin",
    "USDC": "stablecoin",
    "TRX": "coin",
    "SOL": "coin",
    "XRP": "token",
    "ADA": "token",
    "DOT": "token",
    "BCH": "coin",
}


def extract_crypto_entities(
    text: str,
    *,
    min_frequency: int = _MIN_FREQUENCY,
    max_entities: int = 200,
) -> tuple[CryptoEntity, ...]:
    """Extract cryptocurrency entities from text using deterministic patterns.

    Args:
        text: Content to analyze for crypto entities.
        min_frequency: Minimum occurrence count for entity inclusion.
        max_entities: Maximum number of entities to return.

    Returns:
        Tuple of CryptoEntity objects, sorted by frequency (descending).
    """
    if not text or not text.strip():
        return ()

    candidates: Counter[str] = Counter()

    for match in _PATTERN_CRYPTO_NAME.finditer(text):
        phrase = match.group(1).strip()
        if len(phrase) >= _MIN_ENTITY_LENGTH and len(phrase) <= _MAX_ENTITY_LENGTH:
            candidates[phrase] += 1

    for match in _PATTERN_DOMAIN.finditer(text):
        domain = match.group(1).strip()
        if len(domain) >= _MIN_ENTITY_LENGTH:
            candidates[domain] += 1

    for match in _PATTERN_CURRENCY_SYMBOL.finditer(text):
        symbol = match.group(1).strip().upper()
        candidates[symbol] += 1

    for match in _PATTERN_BLOCKCHAIN.finditer(text):
        blockchain = match.group(1).strip()
        candidates[blockchain] += 1

    entities: list[CryptoEntity] = []
    for entity_text, freq in candidates.most_common(max_entities):
        if freq < min_frequency:
            continue

        entity_type = _classify_crypto_entity(entity_text)
        confidence = _estimate_crypto_entity_confidence(entity_text, freq)

        entities.append(
            CryptoEntity(
                name=entity_text,
                entity_type=entity_type,
                frequency=freq,
                confidence=confidence,
            )
        )

    return tuple(entities)


def _classify_crypto_entity(text: str) -> CryptoEntityType:
    """Classify a text string as a cryptocurrency entity type."""
    text_upper = text.upper()
    text_lower = text.lower()

    if text_upper in _CURRENCY_SYMBOLS:
        mapped_type = _CURRENCY_SYMBOLS[text_upper]
        return CryptoEntityType.STABLECOIN if mapped_type == "stablecoin" else CryptoEntityType.COIN

    if text_upper.startswith("0x") or any(c in text for c in ["-", "."]):
        return CryptoEntityType.ADDRESS

    if any(word in text_lower for word in ["wallet", "private key", "mnemonic"]):
        return CryptoEntityType.WALLET

    if any(word in text_lower for word in ["exchange", "exchange rate", "swap", "trade"]):
        return CryptoEntityType.EXCHANGE

    if any(word in text_lower for word in ["network", "chain", "blockchain"]):
        return CryptoEntityType.NETWORK

    if any(word in text_lower for word in ["protocol", "protocol fee", "gas"]):
        return CryptoEntityType.PROTOCOL

    if any(word in text_lower for word in ["smart contract", "contract", "nft"]):
        return CryptoEntityType.SMART_CONTRACT

    if any(word in text_lower for word in ["block", "tx", "transaction", "confirm"]):
        return CryptoEntityType.TRANSACTION

    if any(word in text_lower for word in ["bridge", "cross-chain", "wrap"]):
        return CryptoEntityType.BRIDGE

    if "." in text and not text.startswith("www"):
        return CryptoEntityType.EXCHANGE

    return CryptoEntityType.OTHER


def _estimate_crypto_entity_confidence(text: str, frequency: int) -> float:
    """Estimate confidence for cryptocurrency entity detection."""
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

    if any(symbol in text.upper() for symbol in _CURRENCY_SYMBOLS):
        base += 0.2

    if text.startswith("0x"):
        base += 0.15

    return round(min(1.0, base), 2)


def classify_crypto_intent(keyword: str) -> CryptoSearchIntent:
    """Classify search intent for a cryptocurrency-related keyword.

    Args:
        keyword: Search query to classify.

    Returns:
        CryptoSearchIntent classification.
    """
    if not keyword:
        return CryptoSearchIntent.OTHER

    keyword_lower = keyword.lower()

    setup_patterns = [
        "how to set up",
        "setup wallet",
        "create wallet",
        "install wallet",
        "download wallet app",
        "create account wallet",
        "wallet setup",
    ]

    network_patterns = [
        "network",
        "chain",
        "blockchain",
        "gas",
        "confirmation",
        "confirmation time",
        "block time",
        "network fees",
    ]

    token_patterns = [
        "token",
        "altcoin",
        "alt coin",
        "crypto coin",
        "price",
        "price chart",
        "market cap",
    ]

    exchange_patterns = [
        "exchange",
        "swap",
        "trade on",
        "buy crypto",
        "sell crypto",
        "order on",
        "exchange platform",
    ]

    for pattern in setup_patterns:
        if pattern in keyword_lower:
            return CryptoSearchIntent.WALLET_SETUP

    for pattern in network_patterns:
        if pattern in keyword_lower:
            return CryptoSearchIntent.NETWORK_INFO

    for pattern in token_patterns:
        if pattern in keyword_lower:
            return CryptoSearchIntent.TOKEN_INFO

    for pattern in exchange_patterns:
        if pattern in keyword_lower:
            return CryptoSearchIntent.EXCHANGE

    if any(
        word in keyword_lower for word in ["deposit", "withdraw", "transfer", "send", "receive"]
    ):
        return CryptoSearchIntent.PAYMENT_METHOD

    return CryptoSearchIntent.INFORMATIONAL


def analyze_crypto_content(
    content: str,
    *,
    base_url: str = "",
) -> CryptoAnalysisResult:
    """Perform comprehensive cryptocurrency content analysis.

    Args:
        content: Content to analyze.
        base_url: Target domain URL for entity filtering.

    Returns:
        CryptoAnalysisResult with entities, topics, and gaps.
    """
    entities = extract_crypto_entities(content)

    topics = _cluster_crypto_topics(entities, content)

    content_gaps = _detect_crypto_content_gaps(topics)

    entity_gaps = _detect_crypto_entity_gaps(entities)

    entities_by_type: dict[str, int] = {}
    for entity in entities:
        entity_type = entity.entity_type.value
        entities_by_type[entity_type] = entities_by_type.get(entity_type, 0) + 1

    return CryptoAnalysisResult(
        total_entities=len(entities),
        entities_by_type=entities_by_type,
        topics=topics,
        content_gaps=content_gaps,
        entity_gaps=entity_gaps,
    )


def _cluster_crypto_topics(
    entities: tuple[CryptoEntity, ...],
    content: str,
) -> tuple[CryptoTopic, ...]:
    """Cluster cryptocurrency entities into topics based on type."""
    if not entities:
        return ()

    by_type: dict[CryptoEntityType, list[CryptoEntity]] = defaultdict(list)
    for entity in entities:
        by_type[entity.entity_type].append(entity)

    topics: list[CryptoTopic] = []
    for entity_type, type_entities in by_type.items():
        if type_entities:
            topic_label = f"{entity_type.value.replace('_', ' ').title()} Topic"
            total_freq = sum(e.frequency for e in type_entities)
            avg_freq = total_freq / len(type_entities)

            topics.append(
                CryptoTopic(
                    topic_label=topic_label,
                    entities=tuple(type_entities[:10]),
                    relevance_score=round(avg_freq / 10.0, 4) if avg_freq > 0 else 0.0,
                    keyword=entity_type.value.replace("_", " "),
                )
            )

    topics.sort(key=lambda t: -t.relevance_score)

    return tuple(topics)


def _detect_crypto_content_gaps(
    topics: tuple[CryptoTopic, ...],
) -> tuple[str, ...]:
    """Identify content gaps in cryptocurrency topics."""
    expected_topics = {
        "coin",
        "token",
        "network",
        "wallet",
        "exchange",
        "payment_method",
        "protocol",
        "stablecoin",
    }

    found_topics = {t.topic_label.lower().replace(" ", "_") for t in topics}

    gaps: set[str] = set()
    for expected in expected_topics:
        if expected not in found_topics:
            gaps.add(f"Missing coverage for {expected}")

    return tuple(sorted(gaps))


def _detect_crypto_entity_gaps(
    entities: tuple[CryptoEntity, ...],
) -> tuple[CryptoEntity, ...]:
    """Detect which cryptocurrency entity types are missing."""
    found_types = {e.entity_type for e in entities}

    missing_entities: list[CryptoEntity] = []
    for missing_type in CryptoEntityType:
        if missing_type not in found_types and missing_type != CryptoEntityType.OTHER:
            missing_entities.append(
                CryptoEntity(
                    name=f"Missing {missing_type.value}",
                    entity_type=missing_type,
                    frequency=1,
                    confidence=1.0,
                    context="Detected gap in crypto content coverage",
                )
            )

    missing_entities.sort(key=lambda e: e.entity_type.value)

    return tuple(missing_entities)


def detect_crypto_content_gaps(
    topics: tuple[CryptoTopic, ...],
) -> tuple[str, ...]:
    """Public wrapper for crypto content gap detection."""
    return _detect_crypto_content_gaps(topics)


def detect_crypto_entity_gaps(
    entities: tuple[CryptoEntity, ...],
) -> tuple[CryptoEntity, ...]:
    """Public wrapper for crypto entity gap detection."""
    return _detect_crypto_entity_gaps(entities)
