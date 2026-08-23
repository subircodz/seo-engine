"""Unit tests for Content Intelligence Engine."""

from __future__ import annotations

from sie.domain.engines.content_intelligence import (
    _analyze_freshness,
    _analyze_headings,
    _analyze_images,
    _analyze_keywords,
    _analyze_links,
    _analyze_multimedia,
    _analyze_readability,
    _analyze_structured_data,
    _calculate_quality_score,
    _classify_content_type,
    _clean_visible_text,
    _count_syllables,
    _extract_visible_text,
    _split_paragraphs,
    _split_sentences,
    _split_words,
    analyze_content,
    analyze_content_batch,
)
from sie.domain.models.audit import PageImage
from sie.domain.models.content import ContentAnalysisConfig, ContentType, QualityTier


class DummyPage:
    def __init__(self, **kwargs):
        defaults = dict(
            url="https://example.com/page",
            status_code=200,
            content_type="text/html",
            title="Test Page",
            meta_description="Test description",
            h1s=("Main Heading",),
            h2s=("Subheading 1", "Subheading 2"),
            h3s=("Sub-subheading",),
            images=(PageImage(src="/img1.jpg", alt="Image 1"), PageImage(src="/img2.jpg", alt="")),
            internal_links=("https://example.com/a", "https://example.com/b"),
            external_links=("https://other.com/c",),
            nofollow_links=(),
            jsonld_types=("Article",),
            canonical="https://example.com/page",
            canonicals=("https://example.com/page",),
            meta_robots="index,follow",
            hreflangs=(("en", "https://example.com/page"),),
            mixed_content=False,
            query_param_count=0,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def test_split_words():
    assert _split_words("Hello world") == ["hello", "world"]
    assert _split_words("Test-case with_underscore") == ["test", "case", "with", "underscore"]
    assert _split_words("") == []


def test_split_sentences():
    assert _split_sentences("Hello. World!") == ["Hello.", "World!"]
    assert _split_sentences("One sentence.") == ["One sentence."]
    assert _split_sentences("") == []


def test_split_paragraphs():
    text = "Para 1\n\nPara 2\n\nPara 3"
    assert _split_paragraphs(text) == ["Para 1", "Para 2", "Para 3"]


def test_clean_visible_text():
    assert _clean_visible_text("  hello   world  ") == "hello world"
    assert _clean_visible_text("test&test") == "test&test"  # html.unescape handles this


def test_count_syllables():
    assert _count_syllables("cat") == 1
    assert _count_syllables("hello") == 2
    assert _count_syllables("beautiful") == 3


def test_extract_visible_text():
    page = DummyPage()
    text = _extract_visible_text(page)
    assert "Test Page" in text
    assert "Test description" in text
    assert "Main Heading" in text
    assert "Subheading 1" in text


def test_analyze_readability():
    text = "This is a simple test sentence. Another sentence here. And a third one."
    config = ContentAnalysisConfig()
    metrics = _analyze_readability(text, config)

    assert metrics.word_count > 0
    assert metrics.sentence_count > 0
    assert metrics.syllable_count > 0
    assert metrics.flesch_reading_ease > 0
    assert metrics.flesch_kincaid_grade > 0


def test_analyze_headings():
    page = DummyPage()
    text = "Main Heading Subheading 1 Subheading 2 Sub-subheading"
    config = ContentAnalysisConfig()
    headings = _analyze_headings(page, text, config)

    assert headings.h1_count == 1
    assert headings.h2_count == 2
    assert headings.h3_count == 1
    assert headings.has_h1 is True
    assert headings.heading_depth == 3


def test_analyze_images():
    page = DummyPage()
    images = _analyze_images(page)

    assert images.total_images == 2
    assert images.images_with_alt == 1
    assert images.images_without_alt == 0
    assert images.images_with_empty_alt == 1
    assert images.missing_alt_percentage == 50.0


def test_analyze_links():
    page = DummyPage()
    links = _analyze_links(page)

    assert links.internal_links == 2
    assert links.external_links == 1
    assert links.nofollow_links == 0
    assert links.internal_link_ratio == 2 / 3


def test_analyze_structured_data():
    page = DummyPage()
    sd = _analyze_structured_data(page)

    assert sd.jsonld_types == ("Article",)
    assert sd.has_schema_org is True
    assert sd.schema_count == 1


def test_analyze_freshness():
    page = DummyPage()
    html = '<time datetime="2024-01-15">Jan 15, 2024</time>'
    freshness = _analyze_freshness(page, html)

    assert freshness.published_date is not None
    assert freshness.has_date_signals is True


def test_analyze_multimedia():
    page = DummyPage()
    html = '<video src="vid.mp4"></video><audio src="aud.mp3"></audio><iframe src="https://youtube.com/embed/123"></iframe>'
    mm = _analyze_multimedia(page, html)

    assert mm.has_video is True
    assert mm.has_audio is True
    assert mm.has_iframe_embeds == 1
    assert mm.video_count == 1
    assert mm.audio_count == 1


def test_analyze_keywords():
    text = "seo seo seo optimization content marketing marketing"
    config = ContentAnalysisConfig(max_keywords=10)
    kw = _analyze_keywords(text, config)

    assert len(kw.top_keywords) > 0
    assert kw.top_keywords[0][0] == "seo"
    assert kw.keyword_stuffing_score > 0


def test_classify_content_type():
    # Product page
    page = DummyPage(url="https://example.com/product/123")
    html = '<div class="product">Buy now! Price: $99</div>'
    assert _classify_content_type(page, "text", html) == ContentType.PRODUCT

    # Blog post
    page = DummyPage(url="https://example.com/blog/2024/01/post")
    assert _classify_content_type(page, "text", "") == ContentType.BLOG_POST

    # Home page
    page = DummyPage(url="https://example.com/")
    assert _classify_content_type(page, "text", "") == ContentType.HOME

    # Error page
    page = DummyPage(url="https://example.com/404", status_code=404)
    assert _classify_content_type(page, "text", "") == ContentType.ERROR


def test_calculate_quality_score():
    page = DummyPage()
    html = "<html><body>Test content</body></html>"
    config = ContentAnalysisConfig()

    metrics = analyze_content(page, html, config)
    score, tier, thin = _calculate_quality_score(metrics, config)

    assert 0 <= score <= 100
    assert tier in QualityTier
    assert isinstance(thin, bool)


def test_analyze_content():
    page = DummyPage()
    html = "<html><body><h1>Test</h1><p>This is a test page with some content.</p></body></html>"
    config = ContentAnalysisConfig()
    metrics = analyze_content(page, html, config)

    assert metrics.url == page.url
    assert metrics.word_count > 0
    assert metrics.content_type in ContentType
    assert metrics.quality_score >= 0
    assert metrics.quality_tier in QualityTier
    assert isinstance(metrics.thin_content, bool)


def test_analyze_content_batch():
    pages = [
        DummyPage(url="https://example.com/a"),
        DummyPage(url="https://example.com/b"),
    ]
    html_map = {
        "https://example.com/a": "<html><body><h1>A</h1><p>Content A</p></body></html>",
        "https://example.com/b": "<html><body><h1>B</h1><p>Content B</p></body></html>",
    }
    config = ContentAnalysisConfig()
    results = analyze_content_batch(pages, html_map, config)

    assert len(results) == 2
    assert results[0].url == "https://example.com/a"
    assert results[1].url == "https://example.com/b"
