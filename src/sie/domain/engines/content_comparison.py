"""Content Comparison Engine — pairwise similarity + duplicate detection.

Deterministic algorithms: Jaccard, cosine, shingles. No I/O.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from sie.domain.models.content import (
    ContentComparison,
    ContentMetrics,
    DuplicateStatus,
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z']+\b", text.lower())


def _shingle_set(text: str, k: int = 3) -> frozenset[str]:
    words = _tokenize(text)
    if len(words) < k:
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(" ".join(words[i : i + k]) for i in range(len(words) - k + 1))


def jaccard_similarity(set_a: set[str], set_b: set[str]) -> float:
    """|A ∩ B| / |A U B|."""
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def cosine_similarity(counter_a: Counter[str], counter_b: Counter[str]) -> float:
    """Cosine similarity of term-frequency vectors."""
    dot = sum(counter_a[t] * counter_b.get(t, 0) for t in counter_a)
    norm_a = math.sqrt(sum(v * v for v in counter_a.values()))
    norm_b = math.sqrt(sum(v * v for v in counter_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _structural_similarity(a: ContentMetrics, b: ContentMetrics) -> float:
    """Compare structural signals: headings, images, links."""
    scores = []

    def ratio(x: int, y: int) -> float:
        m = max(x, y)
        if m == 0:
            return 1.0
        return min(x, y) / m

    scores.append(
        ratio(
            a.headings.h1_count + a.headings.h2_count + a.headings.h3_count,
            b.headings.h1_count + b.headings.h2_count + b.headings.h3_count,
        )
    )
    scores.append(ratio(a.images.total_images, b.images.total_images))
    scores.append(
        ratio(
            a.links.internal_links + a.links.external_links,
            b.links.internal_links + b.links.external_links,
        )
    )
    scores.append(ratio(a.paragraph_count, b.paragraph_count))
    scores.append(ratio(len(a.structured_data.jsonld_types), len(b.structured_data.jsonld_types)))
    if a.content_type == b.content_type:
        scores.append(1.0)
    else:
        scores.append(0.5)
    return sum(scores) / len(scores)


def compare_content(
    metrics_a: ContentMetrics,
    metrics_b: ContentMetrics,
    *,
    exact_threshold: float = 0.95,
    near_threshold: float = 0.70,
) -> ContentComparison:
    """Compare two pages' content metrics deterministically."""
    text_a = metrics_a.visible_text
    text_b = metrics_b.visible_text

    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)

    shingles_a = set(_shingle_set(text_a))
    shingles_b = set(_shingle_set(text_b))

    jaccard = jaccard_similarity(shingles_a, shingles_b)

    tf_a = Counter(tokens_a)
    tf_b = Counter(tokens_b)
    cosine = cosine_similarity(tf_a, tf_b)

    word_overlap_count = len(set(tokens_a) & set(tokens_b))
    total_unique = len(set(tokens_a) | set(tokens_b))
    word_overlap_ratio = word_overlap_count / total_unique if total_unique > 0 else 0.0

    structural = _structural_similarity(metrics_a, metrics_b)

    similarity = 0.4 * jaccard + 0.4 * cosine + 0.2 * structural

    if similarity >= exact_threshold:
        status = DuplicateStatus.EXACT_DUPLICATE
    elif similarity >= near_threshold:
        status = DuplicateStatus.NEAR_DUPLICATE
    else:
        status = DuplicateStatus.UNIQUE

    return ContentComparison(
        url_a=metrics_a.url,
        url_b=metrics_b.url,
        similarity_score=round(similarity, 4),
        jaccard_similarity=round(jaccard, 4),
        cosine_similarity=round(cosine, 4),
        word_overlap_count=word_overlap_count,
        word_overlap_ratio=round(word_overlap_ratio, 4),
        structural_similarity=round(structural, 4),
        duplicate_status=status,
    )


def find_duplicate_groups(
    metrics_list: list[ContentMetrics],
    *,
    near_threshold: float = 0.70,
    exact_threshold: float = 0.95,
) -> list[list[str]]:
    """Group pages by duplicate status using union-find over pairwise comparisons.

    Deterministic ordering: input order is preserved within groups; groups are
    sorted by their first member's URL.
    """
    n = len(metrics_list)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    for i in range(n):
        for j in range(i + 1, n):
            cmp = compare_content(
                metrics_list[i],
                metrics_list[j],
                exact_threshold=exact_threshold,
                near_threshold=near_threshold,
            )
            if cmp.duplicate_status != DuplicateStatus.UNIQUE:
                union(i, j)

    groups: dict[int, list[str]] = {}
    for idx, metrics in enumerate(metrics_list):
        root = find(idx)
        groups.setdefault(root, []).append(metrics.url)

    result = [sorted(g) for g in groups.values() if len(g) > 1]
    result.sort(key=lambda g: g[0])
    return result
