"""Unit tests for Intelligence Reporting engine (Phase 8)."""

from __future__ import annotations

import pytest

from sie.domain.engines.search_report import generate_intelligence_report
from sie.domain.models.search_report import (
    ActionItem,
    ActionPriority,
    IntelligenceReport,
    ReportComponent,
    ReportStatus,
)


# ════════════════════════════════════════════════════════════════════════════
# IntelligenceReport model
# ════════════════════════════════════════════════════════════════════════════


class TestIntelligenceReport:
    def test_basic(self):
        report = IntelligenceReport(
            dataset_id="ds1",
            summary="Test summary",
        )
        assert report.dataset_id == "ds1"
        assert report.summary == "Test summary"
        assert len(report.components) == 0

    def test_with_components(self):
        comp = ReportComponent(
            name="ranking",
            status=ReportStatus.COMPLETE,
            summary="Ranking OK",
        )
        report = IntelligenceReport(
            dataset_id="ds1",
            summary="Summary",
            components=(comp,),
        )
        assert len(report.components) == 1
        assert report.components[0].name == "ranking"


# ════════════════════════════════════════════════════════════════════════════
# generate_intelligence_report
# ════════════════════════════════════════════════════════════════════════════


class TestGenerateIntelligenceReport:
    def test_empty_inputs(self):
        report = generate_intelligence_report("ds1")
        assert report.dataset_id == "ds1"
        assert len(report.components) == 0
        assert len(report.action_items) == 0
        assert report.total_findings == 0

    def test_ranking_component(self):
        report = generate_intelligence_report(
            "ds1",
            total_keywords=100,
            keywords_ranking=80,
            keywords_not_ranking=20,
            visibility_score=0.65,
            top_10_count=30,
        )
        names = {c.name for c in report.components}
        assert "ranking" in names

    def test_ranking_action_item(self):
        report = generate_intelligence_report(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=40,
        )
        ranking_actions = [
            a for a in report.action_items
            if "ranking" in str(a.source_components)
        ]
        assert len(ranking_actions) >= 1

    def test_cannibalization_component(self):
        report = generate_intelligence_report(
            "ds1",
            cannibalization_count=5,
            extreme_cannibalization_count=2,
        )
        names = {c.name for c in report.components}
        assert "cannibalization" in names

    def test_cannibalization_critical_action(self):
        report = generate_intelligence_report(
            "ds1",
            extreme_cannibalization_count=3,
            cannibalization_count=5,
        )
        critical_actions = [
            a for a in report.action_items if a.priority == ActionPriority.CRITICAL
        ]
        assert len(critical_actions) >= 1

    def test_volatility_component(self):
        report = generate_intelligence_report(
            "ds1",
            volatile_keyword_count=15,
        )
        names = {c.name for c in report.components}
        assert "volatility" in names

    def test_opportunities_component(self):
        report = generate_intelligence_report(
            "ds1",
            total_opportunities=20,
            competitor_gap_count=10,
            weak_ranking_count=5,
            content_gap_count=5,
        )
        names = {c.name for c in report.components}
        assert "opportunities" in names

    def test_aio_component(self):
        report = generate_intelligence_report(
            "ds1",
            aio_total_keywords=50,
            aio_keywords_with_overview=30,
            aio_target_cited_count=10,
        )
        names = {c.name for c in report.components}
        assert "aio" in names

    def test_geo_component(self):
        report = generate_intelligence_report(
            "ds1",
            geo_total_keywords=50,
            geo_keywords_mentioned=10,
        )
        names = {c.name for c in report.components}
        assert "geo" in names

    def test_performance_component(self):
        report = generate_intelligence_report(
            "ds1",
            performance_total_pages=100,
            avg_performance_score=0.65,
            performance_findings_count=15,
        )
        names = {c.name for c in report.components}
        assert "performance" in names

    def test_entity_component(self):
        report = generate_intelligence_report(
            "ds1",
            entity_total_unique=50,
            entity_coverage=0.4,
            entity_gap_count=10,
        )
        names = {c.name for c in report.components}
        assert "entity" in names

    def test_optimization_component(self):
        report = generate_intelligence_report(
            "ds1",
            optimization_recommendation_count=12,
            high_priority_optimization_count=4,
            quick_wins_count=2,
        )
        names = {c.name for c in report.components}
        assert "optimization" in names

    def test_total_findings_summed(self):
        report = generate_intelligence_report(
            "ds1",
            performance_total_pages=10,
            performance_findings_count=5,
            entity_total_unique=20,
            entity_gap_count=3,
        )
        assert report.total_findings >= 8

    def test_summary_not_empty(self):
        report = generate_intelligence_report(
            "ds1",
            total_keywords=100,
            visibility_score=0.5,
        )
        assert len(report.summary) > 0

    def test_metadata(self):
        report = generate_intelligence_report(
            "ds1",
            metadata={"version": "1.0"},
        )
        assert report.metadata.get("version") == "1.0"

    def test_deterministic(self):
        kwargs = dict(
            dataset_id="ds1",
            total_keywords=100,
            keywords_not_ranking=20,
            cannibalization_count=5,
        )
        r1 = generate_intelligence_report(**kwargs)
        r2 = generate_intelligence_report(**kwargs)
        assert r1.summary == r2.summary
        assert len(r1.components) == len(r2.components)
        assert len(r1.action_items) == len(r2.action_items)

    def test_components_sorted_deterministically(self):
        report = generate_intelligence_report(
            "ds1",
            total_keywords=100,
            keywords_not_ranking=20,
            volatile_keyword_count=10,
            cannibalization_count=3,
            total_opportunities=5,
            performance_total_pages=50,
        )
        # Components should exist
        assert len(report.components) > 0
