"""Unit tests for Content Comparison Engine."""

from __future__ import annotations

from datetime import UTC, datetime

from sie.domain.engines.content_comparison import (
    _structural_similarity,
    compare_content,
    cosine_similarity,
    find_duplicate_groups,
    jaccard_similarity,
)
from sie.domain.models.content import (
    ContentComparison,
    ContentMetrics,
    ContentType,
    DuplicateStatus,
    FreshnessAnalysis,
    HeadingAnalysis,
    ImageAnalysis,
    KeywordDensity,
    LinkAnalysis,
    MultimediaAnalysis,
    QualityTier,
    ReadabilityMetrics,
    StructuredDataAnalysis,
)


def _base_metrics(url: str, text: str) -> ContentMetrics:
    return ContentMetrics(
        url=url,
        content_type=ContentType.ARTICLE,
        visible_text=text,
        word_count=len(text.split()),
        unique_word_count=len(set(text.split())),
        type_token_ratio=0.5,
        character_count=len(text),
        paragraph_count=1,
        avg_words_per_sentence=10.0,
        avg_sentences_per_paragraph=2.0,
        stopword_ratio=0.3,
        html_to_text_ratio=0.5,
        readability=ReadabilityMetrics(
            flesch_reading_ease=60.0,
            flesch_kincaid_grade=8.0,
            gunning_fog_index=10.0,
            smog_index=9.0,
            automated_readability_index=8.0,
            coleman_liau_index=9.0,
            lix=40.0,
            rix=3.0,
            word_count=100,
            sentence_count=10,
            syllable_count=150,
        ),
        headings=HeadingAnalysis(
            h1_count=1,
            h2_count=2,
            h3_count=1,
            h4_count=0,
            h5_count=0,
            h6_count=0,
            h1_texts=("Heading",),
            h2_texts=("Sub1", "Sub2"),
            h3_texts=("Subsub",),
            has_h1=True,
            h1_matches_title=False,
            heading_depth=3,
            heading_keyword_coverage=0.5,
        ),
        images=ImageAnalysis(
            total_images=2,
            images_with_alt=2,
            images_without_alt=0,
            images_with_empty_alt=0,
            decorative_images=0,
            alt_texts=("alt1", "alt2"),
            missing_alt_percentage=0.0,
            avg_alt_length=5.0,
            has_lazy_loading=False,
            has_webp=False,
        ),
        links=LinkAnalysis(
            internal_links=3,
            external_links=1,
            nofollow_links=0,
            internal_link_ratio=0.75,
            external_domains=1,
            anchor_texts=("link1", "link2"),
            empty_anchors=0,
            generic_anchors=0,
            keyword_rich_anchors=1,
            anchor_diversity=0.5,
        ),
        structured_data=StructuredDataAnalysis(
            jsonld_types=("Article",),
            microdata_types=(),
            rdfa_types=(),
            has_schema_org=True,
            schema_count=1,
            validation_errors=(),
        ),
        freshness=FreshnessAnalysis(
            published_date=datetime.now(UTC),
            modified_date=datetime.now(UTC),
            has_date_signals=True,
            days_since_published=10,
            days_since_modified=5,
            is_stale=False,
            freshness_score=0.9,
        ),
        multimedia=MultimediaAnalysis(
            has_video=False,
            has_audio=False,
            has_iframe_embeds=0,
            has_pdf_links=0,
            has_image_galleries=False,
            video_count=0,
            audio_count=0,
            embed_domains=(),
        ),
        keywords=KeywordDensity(
            top_keywords=(("seo", 5, 0.05), ("content", 3, 0.03)),
            bigram_density=(("seo content", 2, 0.02),),
            trigram_density=(),
            keyword_stuffing_score=0.05,
        ),
        quality_score=75.0,
        quality_tier=QualityTier.GOOD,
        thin_content=False,
    )


def test_jaccard_similarity():
    # Identical sets
    assert jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    # No overlap
    assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    # Partial overlap
    assert jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"}) == 0.5

    # Empty sets
    assert jaccard_similarity(set(), set()) == 0.0


def test_cosine_similarity():
    from collections import Counter

    # Identical
    a = Counter(["a", "b", "c"])
    b = Counter(["a", "b", "c"])
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-10

    # No overlap
    a = Counter(["a", "b"])
    b = Counter(["c", "d"])
    assert cosine_similarity(a, b) == 0.0

    # Partial
    a = Counter(["a", "a", "b"])
    b = Counter(["a", "b", "b"])
    # dot = 1*1 + 1*1 = 2
    # norm_a = sqrt(2), norm_b = sqrt(2)
    # cos = 2/2 = 1.0 - wait, a has "a":2, "b":1; b has "a":1, "b":2
    # dot = 2*1 + 1*2 = 4
    # norm_a = sqrt(4+1) = sqrt(5), norm_b = sqrt(1+4) = sqrt(5)
    # cos = 4/5 = 0.8
    assert abs(cosine_similarity(a, b) - 0.8) < 0.01


def test_structural_similarity():
    a = _base_metrics("https://a.com", "text a")
    b = _base_metrics("https://b.com", "text b")

    # Same structure
    score = _structural_similarity(a, b)
    assert score > 0.8

    # Different content type - need to create new instance since ContentMetrics is frozen
    b = _base_metrics("https://b.com", "text b")
    b_diff_type = ContentMetrics(
        url=b.url,
        content_type=ContentType.PRODUCT,
        visible_text=b.visible_text,
        word_count=b.word_count,
        unique_word_count=b.unique_word_count,
        type_token_ratio=b.type_token_ratio,
        character_count=b.character_count,
        paragraph_count=b.paragraph_count,
        avg_words_per_sentence=b.avg_words_per_sentence,
        avg_sentences_per_paragraph=b.avg_sentences_per_paragraph,
        stopword_ratio=b.stopword_ratio,
        html_to_text_ratio=b.html_to_text_ratio,
        readability=b.readability,
        headings=b.headings,
        images=b.images,
        links=b.links,
        structured_data=b.structured_data,
        freshness=b.freshness,
        multimedia=b.multimedia,
        keywords=b.keywords,
        quality_score=b.quality_score,
        quality_tier=b.quality_tier,
        thin_content=b.thin_content,
        extracted_at=b.extracted_at,
    )
    score = _structural_similarity(a, b_diff_type)
    assert score < 1.0


def test_compare_content_identical():
    text = "seo content optimization seo content optimization seo content optimization"
    a = _base_metrics("https://a.com", text)
    b = _base_metrics("https://b.com", text)

    result = compare_content(a, b, exact_threshold=0.95, near_threshold=0.70)

    assert result.url_a == a.url
    assert result.url_b == b.url
    assert result.similarity_score > 0.9
    assert result.duplicate_status == DuplicateStatus.EXACT_DUPLICATE


def test_compare_content_different():
    a = _base_metrics("https://a.com", "seo optimization techniques for better ranking")
    b = _base_metrics("https://b.com", "cooking recipes for delicious pasta dishes")

    result = compare_content(a, b, exact_threshold=0.95, near_threshold=0.70)

    assert result.similarity_score < 0.5
    assert result.duplicate_status == DuplicateStatus.UNIQUE


def test_compare_content_near_duplicate():
    a = _base_metrics("https://a.com", "seo content optimization guide for beginners")
    b = _base_metrics("https://b.com", "seo content optimization guide for advanced users")

    result = compare_content(a, b, exact_threshold=0.95, near_threshold=0.50)

    # Should be near duplicate (high overlap but not identical)
    assert 0.5 < result.similarity_score < 0.95
    assert result.duplicate_status == DuplicateStatus.NEAR_DUPLICATE


def test_find_duplicate_groups():
    metrics = [
        _base_metrics("https://a.com", "seo content optimization guide"),
        _base_metrics("https://b.com", "seo content optimization guide"),
        _base_metrics("https://c.com", "completely different topic here"),
        _base_metrics("https://d.com", "seo content optimization tips"),
    ]

    groups = find_duplicate_groups(metrics, near_threshold=0.60, exact_threshold=0.95)

    # a and b should be exact duplicates
    # d should be near duplicate with a/b
    # c should be unique
    assert len(groups) == 1
    assert len(groups[0]) >= 2
    assert "https://a.com" in groups[0]
    assert "https://b.com" in groups[0]


def test_compare_content_returns_all_fields():
    a = _base_metrics("https://a.com", "test content")
    b = _base_metrics("https://b.com", "test content")

    result = compare_content(a, b)

    assert isinstance(result, ContentComparison)
    assert result.url_a == "https://a.com"
    assert result.url_b == "https://b.com"
    assert 0 <= result.similarity_score <= 1
    assert 0 <= result.jaccard_similarity <= 1
    assert 0 <= result.cosine_similarity <= 1
    assert result.word_overlap_count >= 0
    assert 0 <= result.word_overlap_ratio <= 1
    assert 0 <= result.structural_similarity <= 1
    assert result.duplicate_status in DuplicateStatus
