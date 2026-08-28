"""Tests for universal evidence-based scoring contract."""

from __future__ import annotations

from sie.domain.services.site_analysis import (
    AnalysisMetric,
    CategoryScore,
    SemanticAlignmentResult,
)

# ════════════════════════════════════════════════════════════════════════════
# AnalysisMetric
# ════════════════════════════════════════════════════════════════════════════


class TestAnalysisMetric:
    def test_score_contribution_calculation(self):
        m = AnalysisMetric(
            metric_name="Test",
            category="content",
            metric_type="binary",
            expected=100.0,
            normalized_score=80.0,
            weight=25.0,
        )
        assert m.score_contribution == 20.0  # 25 * 80 / 100

    def test_zero_weight(self):
        m = AnalysisMetric(
            metric_name="Test",
            category="content",
            metric_type="binary",
            expected=100.0,
            normalized_score=50.0,
            weight=0.0,
        )
        assert m.score_contribution == 0.0

    def test_all_fields_optional_have_defaults(self):
        m = AnalysisMetric(
            metric_name="Test",
            category="content",
            metric_type="binary",
            expected=100.0,
            normalized_score=50.0,
            weight=10.0,
        )
        assert m.raw_value is None
        assert m.raw_unit is None
        assert m.evidence == ""
        assert m.evidence_quality == "UNAVAILABLE"
        assert m.confidence == "UNABLE TO VERIFY"
        assert m.affected_urls == []
        assert m.affected_keywords == []

    def test_normalized_score_range(self):
        for score in [0, 25, 50, 75, 100]:
            m = AnalysisMetric(
                metric_name="Test",
                category="content",
                metric_type="range",
                expected=100.0,
                normalized_score=float(score),
                weight=10.0,
            )
            assert 0 <= m.normalized_score <= 100


# ════════════════════════════════════════════════════════════════════════════
# CategoryScore
# ════════════════════════════════════════════════════════════════════════════


class TestCategoryScore:
    def test_assessed_score(self):
        cs = CategoryScore(
            category_name="Test",
            overall_score=75.0,
            score_status="ASSESSED",
            scoring_methodology="test",
            metrics=[],
            sample_size=10,
            data_coverage=1.0,
            confidence="HIGH",
        )
        assert cs.overall_score == 75.0
        assert cs.score_status == "ASSESSED"

    def test_not_assessed_score(self):
        cs = CategoryScore(
            category_name="GEO",
            overall_score=None,
            score_status="NOT ASSESSED",
            scoring_methodology="No data",
            metrics=[],
            sample_size=0,
            data_coverage=0.0,
            confidence="UNABLE TO VERIFY",
        )
        assert cs.overall_score is None
        assert cs.score_status == "NOT ASSESSED"

    def test_insufficient_data(self):
        cs = CategoryScore(
            category_name="AIO",
            overall_score=None,
            score_status="INSUFFICIENT DATA",
            scoring_methodology="Coverage below threshold",
            metrics=[],
            sample_size=10,
            data_coverage=0.3,
            confidence="UNABLE TO VERIFY",
        )
        assert cs.score_status == "INSUFFICIENT DATA"
        assert cs.data_coverage == 0.3


# ════════════════════════════════════════════════════════════════════════════
# Weight Validation
# ════════════════════════════════════════════════════════════════════════════


class TestWeightValidation:
    def test_content_weights_sum_to_100(self):
        """Content Quality weights must sum to exactly 100%."""
        weights = [12, 12, 10, 12, 6, 14, 8, 10, 8, 4, 4]
        assert sum(weights) == 100, f"Content weights sum to {sum(weights)}, expected 100"

    def test_ranking_weights_sum_to_100(self):
        """Ranking weights must sum to exactly 100%."""
        weights = [30, 30, 20, 10, 10]
        assert sum(weights) == 100, f"Ranking weights sum to {sum(weights)}, expected 100"

    def test_architecture_weights_sum_to_100(self):
        """Architecture weights must sum to exactly 100%."""
        weights = [25, 20, 20, 15, 20]
        assert sum(weights) == 100, f"Architecture weights sum to {sum(weights)}, expected 100"

    def test_aio_weights_sum_to_100(self):
        """AIO weights must sum to exactly 100%."""
        weights = [30, 50, 20]
        assert sum(weights) == 100, f"AIO weights sum to {sum(weights)}, expected 100"


# ════════════════════════════════════════════════════════════════════════════
# Gini Coefficient
# ════════════════════════════════════════════════════════════════════════════


class TestGiniCoefficient:
    def test_equal_distribution_gini_zero(self):
        """Equal values should produce Gini ~0."""
        from sie.domain.engines.link_graph import compute_gini

        values = (1.0, 1.0, 1.0, 1.0, 1.0)
        gini = compute_gini(values)
        assert gini == 0.0

    def test_uneven_distribution_positive_gini(self):
        """Uneven values should produce positive Gini."""
        from sie.domain.engines.link_graph import compute_gini

        values = (10.0, 1.0, 1.0, 1.0, 1.0)
        gini = compute_gini(values)
        assert 0 < gini < 1

    def test_insufficient_data_returns_none(self):
        """Less than 3 pages should return None for Gini."""
        from sie.domain.models.audit import LinkVelocity, SiteArchitectureReport

        report = SiteArchitectureReport(
            total_pages=2,
            total_internal_links=2,
            avg_links_per_page=1.0,
            orphans=(),
            dead_ends=(),
            max_depth=1,
            avg_depth=0.5,
            depth_distribution={0: 1, 1: 1},
            pagerank_top_10=(),
            pagerank_bottom_10=(),
            thin_connection_pages=(),
            link_velocity=LinkVelocity(1.0, {}),
        )
        assert report.pagerank_gini is None


# ════════════════════════════════════════════════════════════════════════════
# Coverage Thresholds
# ════════════════════════════════════════════════════════════════════════════


class TestCoverageThresholds:
    def test_high_coverage(self):
        cs = CategoryScore(
            category_name="Test",
            overall_score=80.0,
            score_status="ASSESSED",
            scoring_methodology="test",
            metrics=[],
            sample_size=20,
            data_coverage=0.9,
            confidence="HIGH",
        )
        assert cs.data_coverage >= 0.8

    def test_low_coverage_insufficient(self):
        cs = CategoryScore(
            category_name="AIO",
            overall_score=None,
            score_status="INSUFFICIENT DATA",
            scoring_methodology="Low coverage",
            metrics=[],
            sample_size=5,
            data_coverage=0.3,
            confidence="UNABLE TO VERIFY",
        )
        assert cs.data_coverage < 0.5
        assert cs.overall_score is None


# ════════════════════════════════════════════════════════════════════════════
# GEO NOT ASSESSED
# ════════════════════════════════════════════════════════════════════════════


class TestGEONotAssessed:
    def test_geo_has_no_numeric_score(self):
        """GEO must NOT ASSESSED with no numeric score."""
        cs = CategoryScore(
            category_name="Generative Engine Optimization (GEO)",
            overall_score=None,
            score_status="NOT ASSESSED",
            scoring_methodology="No live generative-engine observations were performed.",
            metrics=[],
            sample_size=0,
            data_coverage=0.0,
            confidence="UNABLE TO VERIFY",
            limitations=["Live generative-engine observations were not available."],
        )
        assert cs.overall_score is None
        assert cs.score_status == "NOT ASSESSED"
        assert len(cs.metrics) == 0

    def test_geo_no_synthetic_observations(self):
        """GEO must not have any synthetic observation data."""
        cs = CategoryScore(
            category_name="GEO",
            overall_score=None,
            score_status="NOT ASSESSED",
            scoring_methodology="test",
            metrics=[],
            sample_size=0,
            data_coverage=0.0,
            confidence="UNABLE TO VERIFY",
        )
        assert cs.sample_size == 0
        assert cs.data_coverage == 0.0


# ════════════════════════════════════════════════════════════════════════════
# SemanticAlignmentResult
# ════════════════════════════════════════════════════════════════════════════


class TestSemanticAlignment:
    def test_exact_match_high_score(self):
        result = SemanticAlignmentResult(
            keyword="online casino",
            exact_title_matches=3,
            partial_title_matches=5,
            alignment_score=90.0,
        )
        assert result.alignment_score == 90.0
        assert result.exact_title_matches == 3

    def test_no_match_zero_score(self):
        result = SemanticAlignmentResult(
            keyword="obscure term",
            exact_title_matches=0,
            partial_title_matches=0,
            alignment_score=0.0,
        )
        assert result.alignment_score == 0.0


# ════════════════════════════════════════════════════════════════════════════
# Scoring Formulas
# ════════════════════════════════════════════════════════════════════════════


class TestScoringFormulas:
    def test_category_score_calculation(self):
        """Verify score = sum(weight * normalized_score) / sum(weights)."""
        metrics = [
            AnalysisMetric("A", "test", "binary", 100.0, 80.0, 30.0),
            AnalysisMetric("B", "test", "binary", 100.0, 60.0, 70.0),
        ]
        total_weight = sum(m.weight for m in metrics)
        expected_score = sum(m.weight * m.normalized_score for m in metrics) / total_weight
        # (30*80 + 70*60) / 100 = (2400 + 4200) / 100 = 66.0
        assert expected_score == 66.0

    def test_ranking_score_formula(self):
        """Verify ranking score = Visibility * Coverage * 100."""
        # 10 keywords: 1 in top 3, 1 in 4-10, 0 in 11-20, 8 not found
        b1, b2 = 1, 1
        N = 10
        coverage = 1.0
        visibility = (b1 * 1.0 + b2 * 0.6) / N
        score = visibility * coverage * 100
        # (1.0 + 0.6) / 10 * 100 = 16.0
        assert score == 16.0
