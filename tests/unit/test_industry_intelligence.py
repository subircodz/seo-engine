"""Unit tests for Phase 10 Industry Intelligence Synthesis.

Tests industry-specific intelligence for:
- GENERAL (baseline SEO)
- CASINO (gaming/iGaming)
- CRYPTO (cryptocurrency)
- CRYPTO_CASINO (hybrid)

All tests verify deterministic output.
"""


from sie.domain.engines.industry_synthesis import (
    _analyze_competitor_intelligence,
    _analyze_entity_intelligence,
    _analyze_ranking_intelligence,
    _IndustryInputs,
    generate_industry_intelligence,
)
from sie.domain.models.industry import (
    IndustryIntelligenceResult,
    IndustryProfile,
    IndustryType,
)


class TestIndustryProfile:
    def test_valid_profile(self):
        profile = IndustryProfile(industry_type=IndustryType.CASINO)
        assert profile.industry_type == IndustryType.CASINO

    def test_profile_with_target_domain(self):
        profile = IndustryProfile(
            industry_type=IndustryType.CRYPTO,
            target_domain="example.com",
        )
        assert profile.target_domain == "example.com"


class TestGenerateIndustryIntelligence:
    def test_basic_generation(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(profile=profile)

        assert result.profile == profile
        assert isinstance(result, IndustryIntelligenceResult)

    def test_with_ranking_data(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(
            profile=profile,
            visibility_score=0.2,
            keywords_not_ranking=50,
            total_keywords=100,
        )

        assert len(result.findings) > 0
        assert any(f.category == "ranking" for f in result.findings)

    def test_deterministic_output(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO)
        result1 = generate_industry_intelligence(
            profile=profile,
            content="Bitcoin and Ethereum are popular cryptocurrencies.",
            visibility_score=0.5,
        )
        result2 = generate_industry_intelligence(
            profile=profile,
            content="Bitcoin and Ethereum are popular cryptocurrencies.",
            visibility_score=0.5,
        )

        assert result1.findings == result2.findings


class TestSynthesisFunctions:
    def test_analyze_ranking_intelligence_low_visibility(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(),
            visibility_score=0.2,
            keywords_not_ranking=30,
            total_keywords=50,
        )

        findings = _analyze_ranking_intelligence(inputs, IndustryType.GENERAL)
        assert len(findings) > 0
        assert findings[0].category == "ranking"

    def test_analyze_entity_intelligence_low_coverage(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(),
            entity_coverage=0.2,
            entity_gap_count=5,
        )

        findings = _analyze_entity_intelligence(inputs, IndustryType.GENERAL)
        assert any(f.category == "entity" for f in findings)

    def test_analyze_competitor_intelligence(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(),
            competitor_domains=("competitor1.com", "competitor2.com"),
        )

        findings = _analyze_competitor_intelligence(inputs, IndustryType.GENERAL)
        assert len(findings) > 0


class TestOpportunityScoring:
    def test_high_impact_low_effort_scores_high(self):
        from sie.domain.models.industry import IndustryOpportunityScorer

        score = IndustryOpportunityScorer.score(
            impact=0.9, coverage=0.8, intent_match=True, entity_gap=True, base_priority=0.8
        )
        assert score > 0.6

    def test_deterministic_scoring(self):
        from sie.domain.models.industry import IndustryOpportunityScorer

        score1 = IndustryOpportunityScorer.score(impact=0.7, base_priority=0.7)
        score2 = IndustryOpportunityScorer.score(impact=0.7, base_priority=0.7)
        assert score1 == score2

    def test_scoring_bounds(self):
        from sie.domain.models.industry import IndustryOpportunityScorer

        score = IndustryOpportunityScorer.score(impact=0.5, base_priority=0.5)
        assert 0.0 <= score <= 1.0


class TestNoHardcodedBrands:
    def test_no_power_win_in_outputs(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(
            profile=profile,
            content="power.win is a great casino. PowerWin offers bonuses.",
        )

        for f in result.findings:
            assert "power.win" not in f.title.lower()
            assert "powerwin" not in f.title.lower()

    def test_no_specific_urls_in_outputs(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(
            profile=profile,
            content="Visit http://example.com for more games.",
        )

        for f in result.findings:
            assert "example.com" not in f.title.lower()
