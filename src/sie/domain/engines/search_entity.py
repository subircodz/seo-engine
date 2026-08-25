"""Entity Intelligence engine — deterministic analysis (Phase 8).

Pure functions for entity extraction, entity visibility analysis, and
competitor entity gap detection.  No I/O, no network, no LLM.

Entity extraction uses deterministic heuristics:
- Capitalized multi-word phrases as entity candidates
- Known entity patterns (URLs, domains, quoted text)
- Frequency-based filtering to reduce noise
- Category classification by pattern matching

This is NOT a production NLP entity recognizer — it provides
deterministic, reproducible entity signals suitable for SEO analysis.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from sie.domain.models.search_entity import (
    EntityCategory,
    EntityDatasetResult,
    EntityGap,
    EntitySignal,
    EntityVisibilityResult,
)

__all__ = [
    "analyze_entity_visibility",
    "detect_entity_gaps",
    "extract_entities_from_content",
]


# ── Entity extraction heuristics ──────────────────────────────────────

# Pattern for capitalized multi-word phrases (2-4 words)
_CAPITALIZED_PHRASE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})\b")

# Pattern for domain-like entities
_DOMAIN_PATTERN = re.compile(r"\b([a-zA-Z0-9][a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b")

# Common English words to exclude from entity detection
_STOP_WORDS = frozenset(
    {
        "The",
        "This",
        "That",
        "These",
        "Those",
        "When",
        "Where",
        "What",
        "Which",
        "Who",
        "How",
        "But",
        "And",
        "For",
        "Are",
        "Not",
        "You",
        "All",
        "Can",
        "Had",
        "Her",
        "Was",
        "One",
        "Our",
        "Out",
        "Has",
        "His",
        "Its",
        "May",
        "New",
        "Now",
        "Old",
        "See",
        "Way",
        "Why",
        "Did",
        "Get",
        "Let",
        "Say",
        "She",
        "Too",
        "Use",
        "Also",
        "Been",
        "Call",
        "Come",
        "Each",
        "Even",
        "Find",
        "Give",
        "Good",
        "Have",
        "Here",
        "High",
        "Just",
        "Keep",
        "Last",
        "Long",
        "Look",
        "Made",
        "Make",
        "Many",
        "Most",
        "Much",
        "Must",
        "Only",
        "Over",
        "Such",
        "Take",
        "Than",
        "Them",
        "Then",
        "Very",
        "Well",
        "Were",
        "Will",
        "With",
        "Work",
        "Year",
        "About",
        "After",
        "Being",
        "Below",
        "Between",
        "Both",
        "Could",
        "Every",
        "First",
        "Found",
        "Going",
        "Got",
        "Great",
        "Into",
        "Know",
        "Least",
        "Like",
        "More",
        "Need",
        "Next",
        "Other",
        "Part",
        "Place",
        "Right",
        "Same",
        "Since",
        "Some",
        "Still",
        "Tell",
        "Think",
        "Time",
        "Under",
        "Used",
        "Want",
        "Water",
    }
)

# Entity categories by pattern
_PERSON_PATTERNS = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|CEO|CTO|Founder|Director)\.\s+")

_MIN_ENTITY_LENGTH = 2
_MAX_ENTITY_LENGTH = 100
_MIN_FREQUENCY = 1
_MAX_ENTITIES_PER_PAGE = 200


def extract_entities_from_content(
    text: str,
    *,
    min_frequency: int = _MIN_FREQUENCY,
    max_entities: int = _MAX_ENTITIES_PER_PAGE,
) -> tuple[EntitySignal, ...]:
    """Extract entity candidates from text using deterministic heuristics.

    Args:
        text: The text content to analyze.
        min_frequency: Minimum occurrence count to include an entity.
        max_entities: Maximum number of entities to return.

    Returns:
        Tuple of EntitySignal objects, sorted by frequency (descending),
        then alphabetically for ties.
    """
    if not text or not text.strip():
        return ()

    # Extract capitalized phrases
    candidates: Counter[str] = Counter()
    for match in _CAPITALIZED_PHRASE.finditer(text):
        phrase = match.group(1).strip()
        if (
            phrase in _STOP_WORDS
            or len(phrase) < _MIN_ENTITY_LENGTH
            or len(phrase) > _MAX_ENTITY_LENGTH
        ):
            continue
        # Skip single very common words
        if " " not in phrase and phrase in _STOP_WORDS:
            continue
        candidates[phrase] += 1

    # Extract domain-like entities
    for match in _DOMAIN_PATTERN.finditer(text):
        domain = match.group(1).strip()
        if len(domain) >= _MIN_ENTITY_LENGTH:
            candidates[domain] += 1

    # Filter and build entity signals
    entities: list[EntitySignal] = []
    for text_val, freq in candidates.most_common(max_entities):
        if freq < min_frequency:
            continue

        category = _classify_entity(text_val)
        confidence = _estimate_confidence(text_val, freq)

        entities.append(
            EntitySignal(
                text=text_val,
                category=category,
                frequency=freq,
                confidence=confidence,
            )
        )

    return tuple(entities)


def _classify_entity(text: str) -> EntityCategory:
    """Deterministic entity category classification."""
    if _PERSON_PATTERNS.search(text):
        return EntityCategory.PERSON

    # Domain-like → organization or brand
    if "." in text and not text.startswith("www"):
        return EntityCategory.ORGANIZATION

    # All-caps → brand/acronym
    if text.isupper() and len(text) >= 2:
        return EntityCategory.BRAND

    # Contains location indicators
    location_words = {"city", "county", "state", "country", "street", "road", "avenue"}
    text_lower = text.lower()
    if any(w in text_lower for w in location_words):
        return EntityCategory.LOCATION

    # Default: concept or organization based on length
    if len(text.split()) >= 3:
        return EntityCategory.ORGANIZATION

    return EntityCategory.CONCEPT


def _estimate_confidence(text: str, frequency: int) -> float:
    """Estimate entity detection confidence (0.0-1.0)."""
    base = 0.3

    # Multi-word phrases are more likely real entities
    word_count = len(text.split())
    if word_count >= 3:
        base += 0.2
    elif word_count >= 2:
        base += 0.1

    # Higher frequency → higher confidence
    if frequency >= 5:
        base += 0.2
    elif frequency >= 3:
        base += 0.1
    elif frequency >= 2:
        base += 0.05

    # Domain-like patterns are high confidence
    if "." in text:
        base += 0.15

    return round(min(1.0, base), 2)


def analyze_entity_visibility(
    observations: tuple[dict[str, object], ...],
    target_domain: str = "",
) -> EntityDatasetResult:
    """Analyze entity visibility across keyword-scoped observations.

    Each observation dict should contain:
    - 'keyword': str
    - 'content_text': str (page content to extract entities from)
    - 'target_entities': tuple[EntitySignal, ...] (optional, pre-extracted)
    - 'competitor_entities': tuple[EntitySignal, ...] (optional, pre-extracted)

    Returns per-keyword and dataset-level entity analysis.
    """
    if not observations:
        return EntityDatasetResult(dataset_id="")

    # Group by keyword
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for obs in observations:
        keyword = str(obs.get("keyword", ""))
        if keyword:
            grouped[keyword].append(obs)

    keyword_results: list[EntityVisibilityResult] = []
    all_entities: Counter[str] = Counter()
    target_mentions_total = 0
    coverage_scores: list[float] = []

    for keyword in sorted(grouped):
        obs_list = grouped[keyword]

        # Collect entities across observations for this keyword
        target_entities: list[EntitySignal] = []
        competitor_entities: list[EntitySignal] = []
        all_keyword_entities: Counter[str] = Counter()

        for obs in obs_list:
            # Use pre-extracted entities if provided
            pre_target = obs.get("target_entities")
            if pre_target and isinstance(pre_target, tuple):
                target_entities.extend(pre_target)

            pre_competitor = obs.get("competitor_entities")
            if pre_competitor and isinstance(pre_competitor, tuple):
                competitor_entities.extend(pre_competitor)

            # Extract from content if available
            content = str(obs.get("content_text", ""))
            if content and not pre_target:
                extracted = extract_entities_from_content(content)
                for e in extracted:
                    all_keyword_entities[e.text] += e.frequency
                    if target_domain and target_domain.lower() in e.text.lower():
                        target_entities.append(
                            EntitySignal(
                                text=e.text,
                                category=e.category,
                                frequency=e.frequency,
                                is_target=True,
                                domain=target_domain,
                                confidence=e.confidence,
                            )
                        )
                    else:
                        competitor_entities.append(e)

        # Deduplicate and sort
        target_dedup = _deduplicate_entities(target_entities)
        competitor_dedup = _deduplicate_entities(competitor_entities)

        # Find shared entities
        target_texts = {e.text for e in target_dedup}
        competitor_texts = {e.text for e in competitor_dedup}
        shared = tuple(sorted(target_texts & competitor_texts))

        # Coverage = target entities / total entities
        total_unique = len(target_texts | competitor_texts)
        coverage = len(target_texts) / total_unique if total_unique > 0 else 0.0

        target_mentions_total += sum(e.frequency for e in target_dedup)
        all_entities.update(all_keyword_entities)
        coverage_scores.append(coverage)

        keyword_results.append(
            EntityVisibilityResult(
                keyword=keyword,
                total_entities=total_unique,
                target_entities=tuple(target_dedup),
                competitor_entities=tuple(competitor_dedup),
                shared_entities=shared,
                entity_coverage=round(coverage, 4),
            )
        )

    overall_coverage = sum(coverage_scores) / len(coverage_scores) if coverage_scores else 0.0

    return EntityDatasetResult(
        dataset_id="",
        keyword_results=tuple(keyword_results),
        total_unique_entities=len(all_entities),
        target_entity_mentions=target_mentions_total,
        overall_coverage=round(overall_coverage, 4),
    )


def _deduplicate_entities(
    entities: list[EntitySignal],
) -> list[EntitySignal]:
    """Deduplicate entities by text, summing frequencies."""
    merged: dict[str, dict[str, object]] = {}
    for e in entities:
        key = e.text
        if key in merged:
            merged[key]["frequency"] = int(merged[key]["frequency"]) + e.frequency
            # Keep higher confidence
            if e.confidence > float(merged[key]["confidence"]):
                merged[key]["confidence"] = e.confidence
        else:
            merged[key] = {
                "text": e.text,
                "category": e.category,
                "frequency": e.frequency,
                "is_target": e.is_target,
                "domain": e.domain,
                "confidence": e.confidence,
            }

    result = []
    for data in merged.values():
        result.append(
            EntitySignal(
                text=str(data["text"]),
                category=data["category"],  # type: ignore[arg-type]
                frequency=int(data["frequency"]),
                is_target=bool(data["is_target"]),
                domain=str(data["domain"]),
                confidence=float(data["confidence"]),
            )
        )
    result.sort(key=lambda e: (-e.frequency, e.text))
    return result


def detect_entity_gaps(
    target_entities: tuple[EntitySignal, ...],
    competitor_entities: tuple[EntitySignal, ...],
    *,
    min_competitor_frequency: int = 2,
) -> tuple[EntityGap, ...]:
    """Detect entities present in competitor content but missing from target.

    Args:
        target_entities: Entities detected in target content.
        competitor_entities: Entities detected in competitor content.
        min_competitor_frequency: Minimum frequency threshold for
            competitor entities to be considered a gap.

    Returns:
        Tuple of EntityGap objects, sorted by competitor frequency (descending).
    """
    target_texts = {e.text.lower() for e in target_entities}

    # Aggregate competitor entity frequency
    comp_freq: Counter[str] = Counter()
    comp_domains: dict[str, list[str]] = defaultdict(list)
    comp_categories: dict[str, EntityCategory] = {}

    for e in competitor_entities:
        text_lower = e.text.lower()
        comp_freq[text_lower] += e.frequency
        if e.domain and (
            text_lower not in comp_domains or e.domain not in comp_domains[text_lower]
        ):
            comp_domains[text_lower].append(e.domain)
        comp_categories[text_lower] = e.category

    gaps: list[EntityGap] = []
    for text_lower, freq in comp_freq.most_common():
        if text_lower in target_texts:
            continue
        if freq < min_competitor_frequency:
            continue

        # Find the original-cased text
        original_text = text_lower
        for e in competitor_entities:
            if e.text.lower() == text_lower:
                original_text = e.text
                break

        category = comp_categories.get(text_lower, EntityCategory.OTHER)
        domains = tuple(comp_domains.get(text_lower, []))

        # Build recommendation
        if category == EntityCategory.BRAND:
            recommendation = (
                f"Create content mentioning competitor brand '{original_text}' "
                f"in comparison or review context."
            )
        elif category == EntityCategory.PRODUCT:
            recommendation = (
                f"Create content addressing '{original_text}' product category "
                f"or specific product comparison."
            )
        elif category == EntityCategory.ORGANIZATION:
            recommendation = (
                f"Build authority around '{original_text}' topic by creating "
                f"in-depth, well-structured content."
            )
        else:
            recommendation = (
                f"Create content covering '{original_text}' topic to match competitor coverage."
            )

        gaps.append(
            EntityGap(
                entity_text=original_text,
                entity_category=category,
                competitor_frequency=freq,
                competitor_domains=domains,
                recommended_action=recommendation,
            )
        )

    return tuple(gaps)
