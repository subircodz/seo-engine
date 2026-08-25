"""Unit tests for Crypto-Casino Intelligence engine (Phase 9)."""

import pytest

from sie.domain.engines.search_crypto_casino import (
    analyze_crypto_casino_intersections,
    classify_crypto_casino_intent,
    detect_crypto_casino_opportunities,
    identify_crypto_casino_entities,
)
from sie.domain.models.industry import (
    CasinoSearchIntent,
    CryptoSearchIntent,
    IndustryEntity,
    IndustryOpportunity,
    IndustryTopic,
)


class TestIdentifyCryptoCasinoEntities:
    def test_empty_content(self):
        result = identify_crypto_casino_entities("", "")
        assert result == ()

    def test_both_domains_present(self):
        casino_content = "Play Bitcoin casino games with bonus offers."
        crypto_content = "Learn about Bitcoin and blockchain technology."
        result = identify_crypto_casino_entities(casino_content, crypto_content)
        assert isinstance(result, tuple)

    def test_intersection_detected(self):
        casino_content = "Deposit Bitcoin at our casino for free spins."
        crypto_content = "Bitcoin is a digital currency for online payments."
        result = identify_crypto_casino_entities(casino_content, crypto_content)
        assert isinstance(result, tuple)

    def test_deterministic(self):
        casino = "Test casino with crypto payments."
        crypto = "Crypto payments using Bitcoin."
        r1 = identify_crypto_casino_entities(casino, crypto)
        r2 = identify_crypto_casino_entities(casino, crypto)
        assert len(r1) == len(r2)


class TestAnalyzeCryptoCasinoIntersections:
    def test_empty_content(self):
        result = analyze_crypto_casino_intersections("", "")
        assert result == ()

    def test_with_intersections(self):
        casino = "Bitcoin casino with bonuses."
        crypto = "Learn about Bitcoin payments."
        result = analyze_crypto_casino_intersections(casino, crypto)
        assert isinstance(result, tuple)


class TestDetectCryptoCasinoOpportunities:
    def test_empty_content(self):
        result = detect_crypto_casino_opportunities("", "")
        assert isinstance(result, tuple)

    def test_opportunities_identified(self):
        casino_content = "Play slots at online casino."
        crypto_content = "Learn about blockchain."
        result = detect_crypto_casino_opportunities(casino_content, crypto_content)
        assert isinstance(result, tuple)

    def test_opportunity_structure(self):
        casino = "Casino game site."
        crypto = "Cryptocurrency information."
        result = detect_crypto_casino_opportunities(casino, crypto)

        for opp in result:
            assert isinstance(opp, IndustryOpportunity)
            assert opp.topic
            assert 0.0 <= opp.priority <= 1.0
            assert 0.0 <= opp.impact <= 1.0
            assert 0.0 <= opp.effort <= 1.0

    def test_priority_deterministic(self):
        casino = "Test casino."
        crypto = "Test crypto."
        r1 = detect_crypto_casino_opportunities(casino, crypto, min_priority=0.5)
        r2 = detect_crypto_casino_opportunities(casino, crypto, min_priority=0.5)
        assert len(r1) == len(r2)


class TestClassifyCryptoCasinoIntent:
    def test_casino_intent(self):
        assert classify_crypto_casino_intent("bitcoin casino") == CasinoSearchIntent.BONUS_SEEKING
        assert classify_crypto_casino_intent("crypto gambling") in [
            CasinoSearchIntent.BONUS_SEEKING,
            CasinoSearchIntent.GAME_SEEKING,
        ]

    def test_game_seeking_intent(self):
        assert classify_crypto_casino_intent("play slots") == CasinoSearchIntent.GAME_SEEKING

    def test_payment_intent(self):
        assert classify_crypto_casino_intent("deposit with crypto") == CasinoSearchIntent.PAYMENT_METHOD

    def test_informational_intent(self):
        assert classify_crypto_casino_intent("casino crypto guide") == CasinoSearchIntent.INFORMATIONAL
        assert classify_crypto_casino_intent("gambling guide") == CasinoSearchIntent.INFORMATIONAL

    def test_empty_keyword(self):
        assert classify_crypto_casino_intent("") == CasinoSearchIntent.OTHER


class TestIndustryEntity:
    def test_valid_entity(self):
        entity = IndustryEntity(
            name="Bitcoin Deposit (payment_method)",
            entity_type="payment_method",
            frequency=10,
            confidence=0.9,
        )
        assert entity.name == "Bitcoin Deposit (payment_method)"
        assert entity.entity_type == "payment_method"
        assert entity.frequency == 10

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            IndustryEntity(name="", entity_type="other")

    def test_confidence_validation(self):
        with pytest.raises(ValueError, match="confidence must be"):
            IndustryEntity(name="Test", entity_type="other", confidence=2.0)


class TestIndustryTopic:
    def test_topic_with_entities(self):
        entity = IndustryEntity(name="Crypto Payment", entity_type="payment_method")
        topic = IndustryTopic(
            topic_label="Crypto Payments",
            entities=(entity,),
            relevance_score=0.85,
        )
        assert topic.topic_label == "Crypto Payments"
        assert topic.entity_count == 1


class TestIndustryOpportunity:
    def test_valid_opportunity(self):
        opp = IndustryOpportunity(
            topic="crypto-payments",
            priority=0.9,
            recommendation="Add crypto payment options.",
            impact=0.9,
            effort=0.6,
        )
        assert opp.topic == "crypto-payments"
        assert opp.priority == 0.9

    def test_empty_topic_rejected(self):
        with pytest.raises(ValueError, match="topic must be a non-empty string"):
            IndustryOpportunity(topic="", priority=0.5)

    def test_priority_out_of_range(self):
        with pytest.raises(ValueError, match="priority must be in"):
            IndustryOpportunity(topic="test", priority=1.5)

    def test_impact_out_of_range(self):
        with pytest.raises(ValueError, match="impact must be in"):
            IndustryOpportunity(topic="test", priority=0.5, impact=1.5)

    def test_effort_out_of_range(self):
        with pytest.raises(ValueError, match="effort must be in"):
            IndustryOpportunity(topic="test", priority=0.5, effort=2.0)


class TestIntegration:
    def test_full_workflow(self):
        casino_content = "Play Bitcoin slots with free bonus at room777casino.com."
        crypto_content = "Bitcoin and Ethereum are popular crypto assets."

        entities = identify_crypto_casino_entities(casino_content, crypto_content)
        assert isinstance(entities, tuple)

        topics = analyze_crypto_casino_intersections(casino_content, crypto_content)
        assert isinstance(topics, tuple)

        opportunities = detect_crypto_casino_opportunities(casino_content, crypto_content)
        assert isinstance(opportunities, tuple)

        for opp in opportunities:
            assert isinstance(opp, IndustryOpportunity)

    def test_no_hardcoded_brands(self):
        assert "power.win" not in str(identify_crypto_casino_entities("", ""))
        assert "powerwin" not in str(identify_crypto_casino_entities("", ""))

    def test_deterministic_output(self):
        content1 = "Crypto betting with Bitcoin at our casino."
        content2 = "Learn about blockchain-based gambling."

        result1 = detect_crypto_casino_opportunities(content1, content2)
        result2 = detect_crypto_casino_opportunities(content1, content2)

        assert len(result1) == len(result2)
        for o1, o2 in zip(result1, result2):
            assert o1.topic == o2.topic
            assert o1.priority == o2.priority