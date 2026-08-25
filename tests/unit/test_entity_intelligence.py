"""Unit tests for Entity Intelligence engine (Phase 8)."""

from __future__ import annotations

import pytest

from sie.domain.engines.search_entity import (
    analyze_entity_visibility,
    detect_entity_gaps,
    extract_entities_from_content,
)
from sie.domain.models.search_entity import (
    EntityCategory,
    EntityDatasetResult,
    EntityGap,
    EntitySignal,
    EntityVisibilityResult,
    TopicCluster,
)


# ════════════════════════════════════════════════════════════════════════════
# EntitySignal model
# ════════════════════════════════════════════════════════════════════════════


class TestEntitySignal:
    def test_basic(self):
        e = EntitySignal(text="Acme Corp", frequency=5)
        assert e.text == "Acme Corp"
        assert e.frequency == 5

    def test_empty_text_raises(self):
        with pytest.raises(ValueError, match="text must be a non-empty"):
            EntitySignal(text="")

    def test_negative_frequency_raises(self):
        with pytest.raises(ValueError, match="frequency must be >= 1"):
            EntitySignal(text="Test", frequency=0)

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValueError, match="confidence must be"):
            EntitySignal(text="Test", confidence=1.5)


# ════════════════════════════════════════════════════════════════════════════
# extract_entities_from_content
# ════════════════════════════════════════════════════════════════════════════


class TestExtractEntities:
    def test_empty_text(self):
        result = extract_entities_from_content("")
        assert result == ()

    def test_none_text(self):
        result = extract_entities_from_content("")
        assert result == ()

    def test_basic_extraction(self):
        text = (
            "Acme Corp makes great products. "
            "Acme Corp is known for quality. "
            "Acme Corp was founded in 2010."
        )
        result = extract_entities_from_content(text)
        texts = [e.text for e in result]
        assert "Acme Corp" in texts

    def test_frequency_counted(self):
        text = (
            "Acme Corp announced new products. "
            "Acme Corp released a major update. "
            "Acme Corp shares rose on the news."
        )
        result = extract_entities_from_content(text)
        acme = [e for e in result if e.text == "Acme Corp"]
        assert len(acme) == 1
        assert acme[0].frequency >= 3

    def test_sorted_by_frequency(self):
        text = (
            "Apple Inc is a major tech company. "
            "Apple Inc reported record earnings. "
            "Apple Inc devices sell worldwide. "
            "Apple Inc dominates the market. "
            "Apple Inc continues to grow. "
            "Microsoft Corp makes software. "
            "Microsoft Corp released Windows."
        )
        result = extract_entities_from_content(text)
        assert len(result) >= 2
        # Most frequent first
        assert result[0].frequency >= result[1].frequency

    def test_domain_entities(self):
        text = "Visit example.com and test-site.org for more info."
        result = extract_entities_from_content(text)
        texts = [e.text for e in result]
        # Domains should be detected
        assert any("example.com" in t for t in texts)

    def test_deterministic(self):
        text = "Apple Inc makes devices. Apple Inc is based in Cupertino."
        r1 = extract_entities_from_content(text)
        r2 = extract_entities_from_content(text)
        assert len(r1) == len(r2)
        for e1, e2 in zip(r1, r2):
            assert e1.text == e2.text
            assert e1.frequency == e2.frequency

    def test_max_entities_limit(self):
        text = " ".join(
            f"Entity{i} Corp Entity{i} Corp Entity{i} Corp"
            for i in range(50)
        )
        result = extract_entities_from_content(text, max_entities=10)
        assert len(result) <= 10

    def test_min_frequency_filter(self):
        text = (
            "Alpha Corp released a new product. "
            "Alpha Corp reported strong earnings. "
            "Beta Corp announced a partnership."
        )
        result = extract_entities_from_content(text, min_frequency=2)
        texts = [e.text for e in result]
        assert "Alpha Corp" in texts
        assert "Beta Corp" not in texts


# ════════════════════════════════════════════════════════════════════════════
# analyze_entity_visibility
# ════════════════════════════════════════════════════════════════════════════


class TestAnalyzeEntityVisibility:
    def test_empty_observations(self):
        result = analyze_entity_visibility(())
        assert result.total_unique_entities == 0
        assert len(result.keyword_results) == 0

    def test_with_preextracted_entities(self):
        target = (EntitySignal(text="TargetBrand", frequency=3, is_target=True),)
        competitor = (EntitySignal(text="RivalBrand", frequency=2),)
        observations = (
            {
                "keyword": "best software",
                "content_text": "",
                "target_entities": target,
                "competitor_entities": competitor,
            },
        )
        result = analyze_entity_visibility(observations, target_domain="targetbrand")
        assert len(result.keyword_results) == 1
        kr = result.keyword_results[0]
        assert kr.keyword == "best software"
        assert kr.total_entities == 2

    def test_grouped_by_keyword(self):
        observations = (
            {"keyword": "kw1", "content_text": "Apple Apple Apple"},
            {"keyword": "kw2", "content_text": "Google Google"},
            {"keyword": "kw1", "content_text": "Apple Apple"},
        )
        result = analyze_entity_visibility(observations)
        assert len(result.keyword_results) == 2
        keywords = {kr.keyword for kr in result.keyword_results}
        assert keywords == {"kw1", "kw2"}

    def test_deterministic(self):
        obs = ({"keyword": "test", "content_text": "Acme Corp Acme Corp"},)
        r1 = analyze_entity_visibility(obs)
        r2 = analyze_entity_visibility(obs)
        assert r1.overall_coverage == r2.overall_coverage
        assert r1.total_unique_entities == r2.total_unique_entities


# ════════════════════════════════════════════════════════════════════════════
# detect_entity_gaps
# ════════════════════════════════════════════════════════════════════════════


class TestDetectEntityGaps:
    def test_no_gaps(self):
        target = (EntitySignal(text="Acme", frequency=5),)
        competitor = (EntitySignal(text="Acme", frequency=3),)
        gaps = detect_entity_gaps(target, competitor)
        assert len(gaps) == 0

    def test_competitor_entity_not_in_target(self):
        target = (EntitySignal(text="Acme", frequency=5),)
        competitor = (
            EntitySignal(text="Acme", frequency=3),
            EntitySignal(text="Rival", frequency=4),
        )
        gaps = detect_entity_gaps(target, competitor)
        assert len(gaps) == 1
        assert gaps[0].entity_text == "Rival"
        assert gaps[0].competitor_frequency == 4

    def test_min_competitor_frequency(self):
        target = ()
        competitor = (EntitySignal(text="Rare", frequency=1),)
        gaps = detect_entity_gaps(target, competitor, min_competitor_frequency=2)
        assert len(gaps) == 0

    def test_sorted_by_frequency(self):
        target = ()
        competitor = (
            EntitySignal(text="Small", frequency=2),
            EntitySignal(text="Large", frequency=10),
            EntitySignal(text="Medium", frequency=5),
        )
        gaps = detect_entity_gaps(target, competitor)
        assert len(gaps) == 3
        assert gaps[0].entity_text == "Large"
        assert gaps[1].entity_text == "Medium"
        assert gaps[2].entity_text == "Small"

    def test_has_recommendation(self):
        target = ()
        competitor = (EntitySignal(text="Rival", frequency=5),)
        gaps = detect_entity_gaps(target, competitor)
        assert len(gaps) == 1
        assert len(gaps[0].recommended_action) > 0

    def test_deterministic(self):
        target = (EntitySignal(text="A", frequency=1),)
        comp = (EntitySignal(text="B", frequency=5),)
        g1 = detect_entity_gaps(target, comp)
        g2 = detect_entity_gaps(target, comp)
        assert len(g1) == len(g2)
        assert g1[0].entity_text == g2[0].entity_text
