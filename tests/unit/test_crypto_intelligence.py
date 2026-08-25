"""Unit tests for Cryptocurrency Intelligence engine (Phase 9)."""

import pytest

from sie.domain.engines.search_crypto import (
    analyze_crypto_content,
    classify_crypto_intent,
    detect_crypto_content_gaps,
    detect_crypto_entity_gaps,
    extract_crypto_entities,
)
from sie.domain.models.industry import (
    CryptoAnalysisResult,
    CryptoEntity,
    CryptoEntityType,
    CryptoSearchIntent,
    CryptoTopic,
)


class TestCryptoEntityType:
    def test_all_members_present(self):
        assert CryptoEntityType.COIN.value == "coin"
        assert CryptoEntityType.TOKEN.value == "token"
        assert CryptoEntityType.BLOCKCHAIN.value == "blockchain"
        assert CryptoEntityType.NETWORK.value == "network"
        assert CryptoEntityType.WALLET.value == "wallet"
        assert CryptoEntityType.EXCHANGE.value == "exchange"
        assert CryptoEntityType.PAYMENT_METHOD.value == "payment_method"
        assert CryptoEntityType.STABLECOIN.value == "stablecoin"
        assert CryptoEntityType.PROTOCOL.value == "protocol"
        assert CryptoEntityType.SMART_CONTRACT.value == "smart_contract"
        assert CryptoEntityType.ADDRESS.value == "address"
        assert CryptoEntityType.TRANSACTION.value == "transaction"
        assert CryptoEntityType.BLOCK.value == "block"
        assert CryptoEntityType.FEE.value == "fee"
        assert CryptoEntityType.CONFIRMATION.value == "confirmation"
        assert CryptoEntityType.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(CryptoEntityType, str)


class TestCryptoSearchIntent:
    def test_all_members_present(self):
        assert CryptoSearchIntent.INFORMATIONAL.value == "informational"
        assert CryptoSearchIntent.TRANSACTIONAL.value == "transactional"
        assert CryptoSearchIntent.PAYMENT_METHOD.value == "payment_method"
        assert CryptoSearchIntent.WALLET_SETUP.value == "wallet_setup"
        assert CryptoSearchIntent.NETWORK_INFO.value == "network_info"
        assert CryptoSearchIntent.TOKEN_INFO.value == "token_info"
        assert CryptoSearchIntent.EXCHANGE.value == "exchange"
        assert CryptoSearchIntent.OTHER.value == "other"

    def test_is_str_enum(self):
        assert issubclass(CryptoSearchIntent, str)


class TestCryptoEntity:
    def test_valid_entity(self):
        entity = CryptoEntity(name="BTC", entity_type=CryptoEntityType.COIN, frequency=10)
        assert entity.name == "BTC"
        assert entity.entity_type == CryptoEntityType.COIN
        assert entity.frequency == 10
        assert entity.confidence == 0.5

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name must be a non-empty string"):
            CryptoEntity(name="", entity_type=CryptoEntityType.COIN)

    def test_negative_frequency_rejected(self):
        with pytest.raises(ValueError, match="frequency must be >= 1"):
            CryptoEntity(name="Test", entity_type=CryptoEntityType.COIN, frequency=0)

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="confidence must be"):
            CryptoEntity(name="Test", entity_type=CryptoEntityType.COIN, confidence=1.5)


class TestCryptoTopic:
    def test_topic_with_entities(self):
        entity = CryptoEntity(name="Bitcoin", entity_type=CryptoEntityType.COIN)
        topic = CryptoTopic(
            topic_label="Coin Topic",
            entities=(entity,),
            relevance_score=0.9,
        )
        assert topic.topic_label == "Coin Topic"
        assert len(topic.entities) == 1
        assert topic.entity_count == 1


class TestExtractCryptoEntities:
    def test_empty_text(self):
        result = extract_crypto_entities("")
        assert result == ()

    def test_extract_with_crypto_name(self):
        text = "Bitcoin is a leading cryptocurrency with Ethereum as a major competitor."
        result = extract_crypto_entities(text)
        assert len(result) > 0

    def test_extract_with_coin_symbols(self):
        text = "Trade BTC ETH USDT for the best crypto rates."
        result = extract_crypto_entities(text)
        assert isinstance(result, tuple)

    def test_deterministic(self):
        text = "The Ethereum network powers smart contracts."
        r1 = extract_crypto_entities(text)
        r2 = extract_crypto_entities(text)
        assert len(r1) == len(r2)
        for e1, e2 in zip(r1, r2, strict=False):
            assert e1.name == e2.name
            assert e1.frequency == e2.frequency

    def test_min_frequency_filter(self):
        text = "BTC BTC BTC Bitcoin is popular. ETH ETH is another coin. "
        result = extract_crypto_entities(text, min_frequency=3)
        texts = [e.name for e in result]
        assert any("BTC" in t for t in texts)


class TestClassifyCryptoIntent:
    def test_wallet_setup_intent(self):
        assert classify_crypto_intent("wallet setup") == CryptoSearchIntent.WALLET_SETUP
        assert classify_crypto_intent("create wallet now") == CryptoSearchIntent.WALLET_SETUP

    def test_network_info_intent(self):
        assert classify_crypto_intent("bitcoin network fee") == CryptoSearchIntent.NETWORK_INFO
        assert classify_crypto_intent("ethereum gas") == CryptoSearchIntent.NETWORK_INFO

    def test_token_info_intent(self):
        assert classify_crypto_intent("bitcoin price chart") == CryptoSearchIntent.TOKEN_INFO
        assert classify_crypto_intent("altcoin info") == CryptoSearchIntent.TOKEN_INFO

    def test_exchange_intent(self):
        assert classify_crypto_intent("exchange platform") == CryptoSearchIntent.EXCHANGE
        assert classify_crypto_intent("crypto swap") == CryptoSearchIntent.EXCHANGE

    def test_payment_method_intent(self):
        assert classify_crypto_intent("make deposit") == CryptoSearchIntent.PAYMENT_METHOD
        assert classify_crypto_intent("receive payment") == CryptoSearchIntent.PAYMENT_METHOD

    def test_empty_keyword(self):
        assert classify_crypto_intent("") == CryptoSearchIntent.OTHER


class TestAnalyzeCryptoContent:
    def test_empty_content(self):
        result = analyze_crypto_content("")
        assert result.total_entities == 0

    def test_with_entities(self):
        content = "BTC and ETH are popular cryptocurrencies on the Ethereum network."
        result = analyze_crypto_content(content)
        assert result.total_entities > 0

    def test_crypto_specific_analysis(self):
        content = "Bitcoin mining combines blockchain technology with proof-of-work."
        result = analyze_crypto_content(content)
        assert isinstance(result.entities_by_type, dict)


class TestDetectCryptoContentGaps:
    def test_no_gaps(self):
        topics = (
            CryptoTopic(topic_label="coin"),
            CryptoTopic(topic_label="token"),
        )
        gaps = detect_crypto_content_gaps(topics)
        assert isinstance(gaps, tuple)

    def test_with_gaps(self):
        topics = (CryptoTopic(topic_label="coin"),)
        gaps = detect_crypto_content_gaps(topics)
        assert len(gaps) > 0


class TestDetectCryptoEntityGaps:
    def test_no_gaps_with_all_types(self):
        entities = tuple(
            CryptoEntity(name=et.value, entity_type=et)
            for et in CryptoEntityType
            if et != CryptoEntityType.OTHER
        )
        gaps = detect_crypto_entity_gaps(entities)
        assert len(gaps) == 0

    def test_with_gaps(self):
        entities = (CryptoEntity(name="BTC", entity_type=CryptoEntityType.COIN),)
        gaps = detect_crypto_entity_gaps(entities)
        assert len(gaps) > 0
        for gap in gaps:
            assert isinstance(gap, CryptoEntity)
            assert gap.confidence == 1.0


class TestCryptoAnalysisResult:
    def test_result_structure(self):
        result = CryptoAnalysisResult(
            total_entities=8,
            entities_by_type={"coin": 5, "token": 3},
            topics=(),
            content_gaps=(),
            entity_gaps=(),
        )
        assert result.total_entities == 8
        assert result.entities_by_type["coin"] == 5

    def test_deterministic(self):
        content = "Test cryptocurrency with BTC and ETH."
        r1 = analyze_crypto_content(content)
        r2 = analyze_crypto_content(content)
        assert r1.total_entities == r2.total_entities
        assert r1.entities_by_type == r2.entities_by_type
