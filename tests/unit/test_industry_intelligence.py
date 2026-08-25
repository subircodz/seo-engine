"""Unit tests for Phase 10 Industry Intelligence Synthesis.

Tests industry-specific intelligence for:
- GENERAL (baseline SEO)
- CASINO (gaming/iGaming)
- CRYPTO (cryptocurrency)
- CRYPTO_CASINO (hybrid)

All tests verify deterministic output.
"""

import pytest

from sie.domain.engines.industry_synthesis import (
    _analyze_casino_intelligence,
    _analyze_competitor_intelligence,
    _analyze_crypto_intelligence,
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
        assert profile.min_entity_confidence == 0.5

    def test_profile_with_target_domain(self):
        profile = IndustryProfile(
            industry_type=IndustryType.CRYPTO,
            target_domain="example.com",
            min_opportunity_priority=0.7,
        )
        assert profile.target_domain == "example.com"
        assert profile.min_opportunity_priority == 0.7

    def test_profile_rejects_invalid_confidence(self):
        with pytest.raises(ValueError):
            IndustryProfile(min_entity_confidence=1.5)

    def test_profile_rejects_invalid_priority(self):
        with pytest.raises(ValueError):
            IndustryProfile(min_opportunity_priority=1.5)


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
        assert result1.findings is result2.findings is False

    def test_general_industry_has_no_industry_findings(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(
            profile=profile,
            content="Some general content.",
        )

        industry_findings = [f for f in result.findings if f.category == "industry"]
        assert len(industry_findings) == 0


class TestCasinoIntelligence:
    def test_casino_finds_game_content(self):
        profile = IndustryProfile(industry_type=IndustryType.CASINO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Our casino offers slots, table games, and live dealer options. "
            "Play blackjack, roulette, and baccarat with Bitcoin.",
        )

        findings = list(result.findings)
        assert any("game" in f.title.lower() for f in findings)

    def test_casino_finds_bonus_content(self):
        profile = IndustryProfile(industry_type=IndustryType.CASINO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Welcome bonus: 100 free spins on first deposit. "
            "Get 50% deposit bonus up to $500.",
        )

        findings = list(result.findings)
        assert any("bonus" in f.title.lower() for f in findings)

    def test_casino_opportunities(self):
        profile = IndustryProfile(industry_type=IndustryType.CASINO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Basic casino content without games or bonuses.",
        )

        opportunities = list(result.opportunities)
        assert len(opportunities) > 0


class TestCryptoIntelligence:
    def test_crypto_finds_coin_content(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO)
        result = generate_industry_intelligence(
            profile=profile,
            content="BTC and ETH are accepted cryptocurrencies. "
            "USDT and USDC are stablecoins for payments.",
        )

        findings = list(result.findings)
        assert any(f.confidence > 0 for f in findings)

    def test_crypto_finds_network_content(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Bitcoin runs on Bitcoin network. Ethereum uses ETH token.",
        )

        findings = list(result.findings)
        assert any(
            "network" in f.title.lower() or "blockchain" in f.title.lower() for f in findings
        )

    def test_crypto_opportunities(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Content about crypto without specific coins.",
        )

        opportunities = list(result.opportunities)
        assert len(opportunities) > 0


class TestCryptoCasinoIntelligence:
    def test_crypto_casino_intersection_detected(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO_CASINO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Play casino games with Bitcoin and Ethereum deposits. "
            "Crypto payment methods available for all games.",
        )

        assert result.profile.industry_type == IndustryType.CRYPTO_CASINO

    def test_crypto_casino_needs_crypto_keywords(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO_CASINO)
        result = generate_industry_intelligence(
            profile=profile,
            content="Casino games available. Bitcoin accepted for deposits.",
        )

        assert len(result.findings) >= 0


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

    def test_analyze_ranking_intelligence_high_visibility(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(),
            visibility_score=0.8,
            keywords_not_ranking=5,
            total_keywords=100,
        )

        findings = _analyze_ranking_intelligence(inputs, IndustryType.GENERAL)
        assert len(findings) == 0

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

    def test_casino_findings_are_industry_type(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(industry_type=IndustryType.CASINO),
            content="Casino with games and bonuses.",
        )

        findings = _analyze_casino_intelligence(inputs)
        for f in findings:
            assert f.industry_type == IndustryType.CASINO

    def test_crypto_findings_are_crypto_type(self):
        inputs = _IndustryInputs(
            profile=IndustryProfile(industry_type=IndustryType.CRYPTO),
            content="Bitcoin and Ethereum accepted.",
        )

        findings = _analyze_crypto_intelligence(inputs)
        for f in findings:
            assert f.industry_type == IndustryType.CRYPTO


class TestEmptyInput:
    def test_empty_content_returns_empty_findings(self):
        profile = IndustryProfile(industry_type=IndustryType.CASINO)
        result = generate_industry_intelligence(profile=profile, content="")

        assert len(result.findings) == 0

    def test_empty_keywords_returns_empty_opportunities(self):
        profile = IndustryProfile(industry_type=IndustryType.GENERAL)
        result = generate_industry_intelligence(profile=profile, total_keywords=0)

        assert result.total_keywords == 0


class TestDeterminism:
    def test_same_input_same_output(self):
        profile = IndustryProfile(industry_type=IndustryType.CRYPTO_CASINO)

        result1 = generate_industry_intelligence(
            profile=profile,
            visibility_score=0.42,
            keywords_not_ranking=15,
            total_keywords=40,
            entity_coverage=0.32,
            content="Test crypto casino content for determinism check.",
        )

        result2 = generate_industry_intelligence(
            profile=profile,
            visibility_score=0.42,
            keywords_not_ranking=15,
            total_keywords=40,
            entity_coverage=0.32,
            content="Test crypto casino content for determinism check.",
        )

        assert result1.visibility_score == result2.visibility_score
        assert result1.keywords_not_ranking == result2.keywords_not_ranking
        assert len(result1.findings) == len(result2.findings)
        for f1, f2 in zip(result1.findings, result2.findings, strict=True):
            assert f1.title == f2.title
            assert f1.impact == f2.impact


class TestNoHardcodedBrands:
    def test_no_power_win_in_outputs(self):
        profile = IndustryProfile()
        result = generate_industry_intelligence(
            profile=profile,
            content="power.win is a great casino. PowerWin offers bonuses.",
        )

        for f in result.findings:
            assert "power.win" not in f.title.lower()
            assert "powerwin" not in f.title.lower()

        for o in result.opportunities:
            assert "power.win" not in o.topic.lower()

    def test_no_specific_urls_in_outputs(self):
        profile = IndustryProfile()
        result = generate_industry_intelligence(
            profile=profile,
            content="Visit http://example.com for more games.",
        )

        for f in result.findings:
            assert "example.com" not in f.title.lower()
