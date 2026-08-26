"""Tests for site analysis API serialization and PDF endpoint behavior."""

from __future__ import annotations

from sie.api.routes.site_analysis import (
    SiteAnalyzeResponse,
    _serialize_breakdown,
    _serialize_metric,
)
from sie.domain.services.site_analysis import (
    AnalysisMetric,
    CategoryScore,
)

# ════════════════════════════════════════════════════════════════════════════
# Test AnalysisMetric Serialization
# ════════════════════════════════════════════════════════════════════════════


class TestSerializeMetric:
    def test_full_metric(self):
        m = AnalysisMetric(
            metric_name="Title Quality",
            category="content",
            metric_type="binary",
            expected=100.0,
            normalized_score=75.0,
            weight=12.0,
            raw_value=45,
            raw_unit="pages",
            raw_evidence="45/60 pages pass",
            normalization_method="Binary per page",
            status="NEEDS IMPROVEMENT",
            evidence="75% of pages pass title check",
            evidence_quality="OBSERVED",
            affected_urls=["/about", "/contact"],
            affected_keywords=["test kw"],
            why_it_matters="Titles affect CTR",
            remediation="Write unique titles",
        )
        result = _serialize_metric(m)
        assert result["metric_name"] == "Title Quality"
        assert result["category"] == "content"
        assert result["weight"] == 12.0
        assert result["normalized_score"] == 75.0
        assert result["status"] == "NEEDS IMPROVEMENT"
        assert result["affected_urls"] == ["/about", "/contact"]
        assert result["confidence"] == "UNABLE TO VERIFY"

    def test_minimal_metric(self):
        m = AnalysisMetric(
            metric_name="SSL",
            category="technical",
            metric_type="binary",
            expected=100.0,
            normalized_score=100.0,
            weight=15.0,
        )
        result = _serialize_metric(m)
        assert result["metric_name"] == "SSL"
        assert result["raw_value"] is None
        assert result["evidence"] == ""
        assert result["why_it_matters"] == ""


# ════════════════════════════════════════════════════════════════════════════
# Test CategoryScore Serialization
# ════════════════════════════════════════════════════════════════════════════


class TestSerializeBreakdown:
    def test_assessed_breakdown(self):
        breakdown = CategoryScore(
            category_name="Content Quality",
            overall_score=65.0,
            score_status="ASSESSED",
            scoring_methodology="Based on word count analysis",
            metrics=[
                AnalysisMetric(
                    metric_name="Word Count",
                    category="content",
                    metric_type="percentage",
                    expected=800.0,
                    normalized_score=60.0,
                    weight=25.0,
                )
            ],
            sample_size=50,
            data_coverage=1.0,
            confidence="HIGH",
            confidence_factors=["All pages analyzed"],
            limitations=[],
            evidence_quality_summary="OBSERVED",
        )
        result = _serialize_breakdown(breakdown)
        assert result["category_name"] == "Content Quality"
        assert result["overall_score"] == 65.0
        assert result["score_status"] == "ASSESSED"
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["metric_name"] == "Word Count"
        assert result["sample_size"] == 50

    def test_not_assessed_breakdown(self):
        breakdown = CategoryScore(
            category_name="GEO",
            overall_score=None,
            score_status="NOT ASSESSED",
            scoring_methodology="No live queries performed",
            metrics=[],
            sample_size=0,
            data_coverage=0.0,
            confidence="UNABLE TO VERIFY",
            limitations=["No generative engine queries available"],
        )
        result = _serialize_breakdown(breakdown)
        assert result["overall_score"] is None
        assert result["score_status"] == "NOT ASSESSED"
        assert result["metrics"] == []
        assert "No generative engine queries available" in result["limitations"]

    def test_insufficient_data_breakdown(self):
        breakdown = CategoryScore(
            category_name="Rankings",
            overall_score=None,
            score_status="INSUFFICIENT DATA",
            scoring_methodology="Need more keywords",
            metrics=[],
            sample_size=2,
            data_coverage=0.1,
            confidence="LOW",
        )
        result = _serialize_breakdown(breakdown)
        assert result["score_status"] == "INSUFFICIENT DATA"
        assert result["data_coverage"] == 0.1

    def test_none_breakdown(self):
        result = _serialize_breakdown(None)
        assert result is None


# ════════════════════════════════════════════════════════════════════════════
# Test SiteAnalyzeResponse Model
# ════════════════════════════════════════════════════════════════════════════


class TestSiteAnalyzeResponse:
    def test_response_includes_breakdown_fields(self):
        response = SiteAnalyzeResponse(
            domain="test.com",
            analyzed_at="2026-08-26T12:00:00",
            crawl_run_id="abc123",
            overall_score=65.0,
            technical_score=70.0,
            content_score=60.0,
            ranking_score=50.0,
            architecture_score=80.0,
            aio_score=40.0,
            geo_score=0.0,
            recommendations=[],
            content_breakdown={
                "category_name": "Content Quality",
                "overall_score": 60.0,
                "score_status": "ASSESSED",
                "scoring_methodology": "Test",
                "metrics": [],
                "sample_size": 50,
                "data_coverage": 1.0,
                "confidence": "HIGH",
                "confidence_factors": [],
                "limitations": [],
                "evidence_quality_summary": "OBSERVED",
                "data_source": "",
                "observation_date": None,
            },
            geo_breakdown={
                "category_name": "GEO",
                "overall_score": None,
                "score_status": "NOT ASSESSED",
                "scoring_methodology": "Not assessed",
                "metrics": [],
                "sample_size": 0,
                "data_coverage": 0.0,
                "confidence": "UNABLE TO VERIFY",
                "confidence_factors": [],
                "limitations": [],
                "evidence_quality_summary": "UNAVAILABLE",
                "data_source": "",
                "observation_date": None,
            },
        )
        assert response.content_breakdown is not None
        assert response.content_breakdown["overall_score"] == 60.0
        assert response.geo_breakdown is not None
        assert response.geo_breakdown["overall_score"] is None
        assert response.ranking_breakdown is None
        assert response.architecture_breakdown is None
        assert response.aio_breakdown is None


# ════════════════════════════════════════════════════════════════════════════
# Test JSON Serialization Roundtrip
# ════════════════════════════════════════════════════════════════════════════


class TestJSONRoundtrip:
    def test_breakdown_survives_json(self):
        import json
        breakdown = CategoryScore(
            category_name="Content Quality",
            overall_score=65.5,
            score_status="ASSESSED",
            scoring_methodology="Test",
            metrics=[
                AnalysisMetric(
                    metric_name="Title Quality",
                    category="content",
                    metric_type="binary",
                    expected=100.0,
                    normalized_score=75.0,
                    weight=12.0,
                )
            ],
            sample_size=50,
            data_coverage=1.0,
            confidence="HIGH",
        )
        serialized = _serialize_breakdown(breakdown)
        json_str = json.dumps(serialized)
        deserialized = json.loads(json_str)
        assert deserialized["category_name"] == "Content Quality"
        assert deserialized["overall_score"] == 65.5
        assert len(deserialized["metrics"]) == 1
        assert deserialized["metrics"][0]["weight"] == 12.0
