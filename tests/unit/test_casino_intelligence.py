"""Unit tests for Casino Intelligence engine (Phase 9)."""

import pytest

from sie.domain.engines.search_casino import (
    analyze_casino_content,
    classify_casino_intent,
    detect_casino_content_gaps,
    detect_casino_entity_gaps,
    extract_casino_entities,
)
from sie.domain.models.industry import (
    CasinoAnalysisResult,
    CasinoEntity,
    CasinoEntityType,
    CasinoSearchIntent,
    CasinoTopic,
)


class TestCasinoEntityType:
    def test_all_members_present(self):
        assert CasinoEntityType.GAME.value == "game"
        assert CasinoEntityType.GAME_PROVIDER.value == "game_provider"
        assert CasinoEntityType.CASINO.value == "casino"
        assert CasinoEntityType.BONUS.value == "bonus"
        assert CasinoEntityType.PROMOTION.value == "promotion"
        assert CasinoEntityType.PAYMENT_METHOD.value == "payment_method"
        assert CasinoEntityType.CURRENCY.value == "currency"
        assert CasinoEntityType.COUNTRY.value == "country"
        assert CasinoEntityType.LICENSE.value == "license"
        assert CasinoEntityType.REGULATOR.value == "regulator"
        assert CasinoEntityType.JACKPOT.value == "jackpot"
        assert CasinoEntityType.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(CasinoEntityType, str)


class TestCasinoSearchIntent:
    def test_all_members_present(self):
        assert CasinoSearchIntent.NAVIGATIONAL.value == "navigational"
        assert CasinoSearchIntent.INFORMATIONAL.value == "informational"
        assert CasinoSearchIntent.COMMERCIAL_INVESTIGATION.value == "commercial_investigation"
        assert CasinoSearchIntent.TRANSACTIONAL.value == "transactional"
        assert CasinoSearchIntent.BONUS_SEEKING.value == "bonus_seeking"
        assert CasinoSearchIntent.GAME_SEEKING.value == "game_seeking"
        assert CasinoSearchIntent.PAYMENT_METHOD.value == "payment_method"
        assert CasinoSearchIntent.GEO_REGULATORY.value == "geo_regulatory"
        assert CasinoSearchIntent.COMPARISON.value == "comparison"
        assert CasinoSearchIntent.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(CasinoSearchIntent, str)


class TestCasinoEntity:
    def test_valid_entity(self):
        entity = CasinoEntity(name="Slot Game", entity_type=CasinoEntityType.GAME, frequency=5)
        assert entity.name == "Slot Game"
        assert entity.entity_type == CasinoEntityType.GAME
        assert entity.frequency == 5
        assert entity.confidence == 0.5

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            CasinoEntity(name="", entity_type=CasinoEntityType.GAME)

    def test_negative_frequency_rejected(self):
        with pytest.raises(ValueError, match="frequency must be >= 1"):
            CasinoEntity(name="Test", entity_type=CasinoEntityType.GAME, frequency=0)

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="confidence must be"):
            CasinoEntity(name="Test", entity_type=CasinoEntityType.GAME, confidence=1.5)


class TestCasinoTopic:
    def test_topic_with_entities(self):
        entity = CasinoEntity(name="Slots", entity_type=CasinoEntityType.GAME)
        topic = CasinoTopic(
            topic_label="Game Topic",
            entities=(entity,),
            relevance_score=0.8,
        )
        assert topic.topic_label == "Game Topic"
        assert len(topic.entities) == 1
        assert topic.entity_count == 1


class TestExtractCasinoEntities:
    def test_empty_text(self):
        result = extract_casino_entities("")
        assert result == ()

    def test_extract_with_game_name(self):
        # Must contain casino-related keywords to be extracted
        text = "Play the Fortune Wheel Slot game for huge prizes."
        result = extract_casino_entities(text)
        assert len(result) > 0
        # Should extract "Fortune Wheel Slot" as it contains "Slot"
        names = [e.name for e in result]
        assert any("Fortune Wheel Slot" in n for n in names)

    def test_extract_with_game_provider(self):
        text = "Games from NetEnt and Pragmatic are popular."
        result = extract_casino_entities(text)
        names = [e.name for e in result]
        assert "NetEnt" in names or "Pragmatic" in names

    def test_extract_with_currency(self):
        text = "Deposit with BTC or ETH for instant play."
        result = extract_casino_entities(text)
        names = [e.name for e in result]
        assert "BTC" in names or "ETH" in names

    def test_deterministic(self):
        text = "The Fortune Wheel Slot is a popular game."
        r1 = extract_casino_entities(text)
        r2 = extract_casino_entities(text)
        assert len(r1) == len(r2)
        for e1, e2 in zip(r1, r2, strict=False):
            assert e1.name == e2.name
            assert e1.frequency == e2.frequency

    def test_min_frequency_filter(self):
        text = (
            "Mega Slot released a new game. "
            "Mega Slot is known for quality. "
            "Beta Casino announced sports."
        )
        result = extract_casino_entities(text, min_frequency=2)
        texts = [e.name for e in result]
        # "Mega Slot" appears twice and contains "Slot" keyword
        assert any("Mega Slot" in t for t in texts)

    def test_domain_not_extracted(self):
        """Domains should not be extracted as casino entities."""
        text = "Visit example.com for the best casino online."
        result = extract_casino_entities(text)
        texts = [e.name for e in result]
        assert "example.com" not in texts


class TestClassifyCasinoIntent:
    def test_navigational_intent(self):
        assert classify_casino_intent("login casino") == CasinoSearchIntent.NAVIGATIONAL
        assert classify_casino_intent("register account") == CasinoSearchIntent.NAVIGATIONAL

    def test_bonus_seeking_intent(self):
        assert classify_casino_intent("free bonus") == CasinoSearchIntent.BONUS_SEEKING
        assert classify_casino_intent("cashback offer") == CasinoSearchIntent.BONUS_SEEKING

    def test_game_seeking_intent(self):
        assert classify_casino_intent("play slot games") == CasinoSearchIntent.GAME_SEEKING
        assert classify_casino_intent("live dealer") == CasinoSearchIntent.GAME_SEEKING

    def test_payment_method_intent(self):
        assert classify_casino_intent("bitcoin deposit") == CasinoSearchIntent.PAYMENT_METHOD
        assert classify_casino_intent("payment methods") == CasinoSearchIntent.PAYMENT_METHOD

    def test_comparison_intent(self):
        assert classify_casino_intent("best casino review") == CasinoSearchIntent.COMPARISON

    def test_empty_keyword(self):
        assert classify_casino_intent("") == CasinoSearchIntent.OTHER


class TestAnalyzeCasinoContent:
    def test_empty_content(self):
        result = analyze_casino_content("")
        assert result.total_entities == 0

    def test_with_entities(self):
        content = "Play Mega Slot games with huge bonuses and BTC deposits at our casino."
        result = analyze_casino_content(content)
        assert result.total_entities > 0
        # Should find entities by type
        assert "game" in result.entities_by_type or "currency" in result.entities_by_type

    def test_content_gaps(self):
        content = "Play Mega Slot games at our casino."
        result = analyze_casino_content(content)
        assert isinstance(result.content_gaps, tuple)


class TestDetectCasinoContentGaps:
    def test_no_gaps(self):
        topics = (
            CasinoTopic(topic_label="game"),
            CasinoTopic(topic_label="bonus"),
        )
        gaps = detect_casino_content_gaps(topics)
        assert isinstance(gaps, tuple)

    def test_with_gaps(self):
        topics = (CasinoTopic(topic_label="game"),)
        gaps = detect_casino_content_gaps(topics)
        assert len(gaps) > 0


class TestDetectCasinoEntityGaps:
    def test_no_gaps_with_all_types(self):
        entities = tuple(
            CasinoEntity(name=et.value.capitalize(), entity_type=et)
            for et in CasinoEntityType
            if et != CasinoEntityType.OTHER
        )
        gaps = detect_casino_entity_gaps(entities)
        assert len(gaps) == 0

    def test_with_gaps(self):
        entities = (CasinoEntity(name="Game", entity_type=CasinoEntityType.GAME),)
        gaps = detect_casino_entity_gaps(entities)
        assert len(gaps) > 0
        for gap in gaps:
            assert isinstance(gap, CasinoEntity)
            assert gap.confidence == 1.0


class TestCasinoAnalysisResult:
    def test_result_structure(self):
        result = CasinoAnalysisResult(
            total_entities=5,
            entities_by_type={"game": 3, "bonus": 2},
            topics=(),
            content_gaps=(),
            entity_gaps=(),
        )
        assert result.total_entities == 5
        assert result.entities_by_type["game"] == 3

    def test_deterministic(self):
        content = "Test casino game with bonuses."
        r1 = analyze_casino_content(content)
        r2 = analyze_casino_content(content)
        assert r1.total_entities == r2.total_entities
        assert r1.entities_by_type == r2.entities_by_type
