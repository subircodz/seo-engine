"""Content Intelligence Engine — deterministic content analysis.

Pure functions operating on PageDOM + visible text. No I/O, no network, no LLM.
"""

from __future__ import annotations

import contextlib
import math
import re
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlparse

from sie.domain.models.audit import PageDOM
from sie.domain.models.content import (
    ContentAnalysisConfig,
    ContentMetrics,
    ContentType,
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

_STOPWORDS_EN = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
        "i",
        "you",
        "your",
        "we",
        "they",
        "this",
        "these",
        "those",
        "am",
        "being",
        "have",
        "had",
        "do",
        "does",
        "did",
        "but",
        "or",
        "if",
        "then",
        "else",
        "when",
        "where",
        "why",
        "how",
        "all",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "just",
        "should",
        "now",
    }
)


_MONTH_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DATETIME_ATTR_RE = re.compile(r'datetime\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_TIME_TAG_RE = re.compile(r"<time[^>]*>([^<]+)</time>", re.IGNORECASE)
_PUBLISHED_RE = re.compile(
    r"(?:published|posted|created)\s*(?:on|at)?\s*[:]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)
_MODIFIED_RE = re.compile(
    r"(?:updated|modified|revised)\s*(?:on|at)?\s*[:]?\s*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\w+\s+\d{1,2},?\s+\d{4})",
    re.IGNORECASE,
)


def _get_stopwords(lang: str) -> frozenset[str]:
    if lang == "en":
        return _STOPWORDS_EN
    return frozenset()


def _count_syllables(word: str) -> int:
    word = word.lower()
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    matches = re.findall(r"[aeiouy]+", word)
    return max(1, len(matches))


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def _split_words(text: str) -> list[str]:
    return re.findall(
        r"\b[a-zA-Z][a-zA-Z'-]*[a-zA-Z]\b|\b[a-zA-Z]\b",
        text.lower().replace("-", " ").replace("_", " "),
    )


def _split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def _clean_visible_text(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_visible_text(page: PageDOM) -> str:
    parts = []
    if page.title:
        parts.append(page.title)
    if page.meta_description:
        parts.append(page.meta_description)
    parts.extend(page.h1s)
    parts.extend(page.h2s)
    parts.extend(page.h3s)
    return _clean_visible_text(" ".join(parts))


def _analyze_readability(text: str, config: ContentAnalysisConfig) -> ReadabilityMetrics:
    words = _split_words(text)
    sentences = _split_sentences(text)
    paragraphs = _split_paragraphs(text)

    word_count = len(words)
    sentence_count = max(1, len(sentences))
    _ = max(1, len(paragraphs))  # unused but kept for clarity

    syllable_count = sum(_count_syllables(w) for w in words)

    if word_count == 0 or sentence_count == 0:
        return ReadabilityMetrics(
            flesch_reading_ease=0.0,
            flesch_kincaid_grade=0.0,
            gunning_fog_index=0.0,
            smog_index=0.0,
            automated_readability_index=0.0,
            coleman_liau_index=0.0,
            lix=0.0,
            rix=0.0,
            word_count=0,
            sentence_count=0,
            syllable_count=0,
        )

    avg_words_per_sentence = word_count / sentence_count
    avg_syllables_per_word = syllable_count / word_count
    complex_words = sum(1 for w in words if _count_syllables(w) >= 3)

    flesch_reading_ease = 206.835 - 1.015 * avg_words_per_sentence - 84.6 * avg_syllables_per_word
    flesch_kincaid_grade = 0.39 * avg_words_per_sentence + 11.8 * avg_syllables_per_word - 15.59
    gunning_fog_index = 0.4 * (avg_words_per_sentence + 100 * complex_words / word_count)
    smog_index = 1.043 * math.sqrt(complex_words * 30 / sentence_count) + 3.1291
    automated_readability_index = (
        4.71 * (sum(len(w) for w in words) / word_count) + 0.5 * avg_words_per_sentence - 21.43
    )
    coleman_liau_index = (
        0.0588 * (sum(len(w) for w in words) / word_count * 100)
        - 0.296 * (sentence_count / word_count * 100)
        - 15.8
    )
    lix = avg_words_per_sentence + (complex_words * 100 / word_count)
    rix = complex_words / sentence_count

    return ReadabilityMetrics(
        flesch_reading_ease=round(flesch_reading_ease, 2),
        flesch_kincaid_grade=round(flesch_kincaid_grade, 2),
        gunning_fog_index=round(gunning_fog_index, 2),
        smog_index=round(smog_index, 2),
        automated_readability_index=round(automated_readability_index, 2),
        coleman_liau_index=round(coleman_liau_index, 2),
        lix=round(lix, 2),
        rix=round(rix, 2),
        word_count=word_count,
        sentence_count=sentence_count,
        syllable_count=syllable_count,
    )


def _analyze_headings(
    page: PageDOM, visible_text: str, config: ContentAnalysisConfig
) -> HeadingAnalysis:
    h1_texts = tuple(page.h1s)
    h2_texts = tuple(page.h2s)
    h3_texts = tuple(page.h3s)

    h1_count = len(h1_texts)
    h2_count = len(h2_texts)
    h3_count = len(page.h3s)
    h4_count = 0
    h5_count = 0
    h6_count = 0

    has_h1 = h1_count > 0
    h1_matches_title = False
    if page.title and h1_texts:
        h1_matches_title = page.title.lower().strip() == h1_texts[0].lower().strip()

    heading_depth = 1 if h1_count > 0 else 0
    if h2_count > 0:
        heading_depth = max(heading_depth, 2)
    if h3_count > 0:
        heading_depth = max(heading_depth, 3)

    words = set(_split_words(visible_text))
    heading_keywords = set()
    for h in h1_texts + h2_texts + h3_texts:
        heading_keywords.update(_split_words(h))
    heading_keyword_coverage = 0.0
    if words:
        heading_keyword_coverage = len(heading_keywords & words) / len(words)

    return HeadingAnalysis(
        h1_count=h1_count,
        h2_count=h2_count,
        h3_count=h3_count,
        h4_count=h4_count,
        h5_count=h5_count,
        h6_count=h6_count,
        h1_texts=h1_texts,
        h2_texts=h2_texts,
        h3_texts=h3_texts,
        has_h1=has_h1,
        h1_matches_title=h1_matches_title,
        heading_depth=heading_depth,
        heading_keyword_coverage=round(heading_keyword_coverage, 4),
    )


def _analyze_images(page: PageDOM) -> ImageAnalysis:
    images = page.images
    total = len(images)
    with_alt = sum(1 for img in images if img.alt and img.alt.strip())
    without_alt = sum(1 for img in images if img.alt is None)
    empty_alt = sum(1 for img in images if img.alt == "")
    decorative = sum(
        1
        for img in images
        if img.alt == "" and not img.src.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp"))
    )
    alt_texts = tuple(img.alt for img in images if img.alt)
    missing_alt_pct = 0.0
    if total > 0:
        missing_alt_pct = round((without_alt + empty_alt) / total * 100, 2)
    avg_alt_len = 0.0
    if alt_texts:
        avg_alt_len = round(sum(len(a) for a in alt_texts) / len(alt_texts), 2)

    has_lazy = False
    has_webp = any(img.src.endswith(".webp") for img in images)

    return ImageAnalysis(
        total_images=total,
        images_with_alt=with_alt,
        images_without_alt=without_alt,
        images_with_empty_alt=empty_alt,
        decorative_images=decorative,
        alt_texts=alt_texts,
        missing_alt_percentage=missing_alt_pct,
        avg_alt_length=avg_alt_len,
        has_lazy_loading=has_lazy,
        has_webp=has_webp,
    )


def _analyze_links(page: PageDOM) -> LinkAnalysis:
    internal = len(page.internal_links)
    external = len(page.external_links)
    nofollow = len(page.nofollow_links)
    total = internal + external
    internal_ratio = internal / total if total > 0 else 0.0

    domains = set()
    for url in page.external_links:
        with contextlib.suppress(Exception):
            domains.add(urlparse(url).netloc.lower())

    anchor_texts = tuple()
    empty_anchors = 0
    generic_anchors = 0
    keyword_rich = 0

    return LinkAnalysis(
        internal_links=internal,
        external_links=external,
        nofollow_links=nofollow,
        internal_link_ratio=internal_ratio,
        external_domains=len(domains),
        anchor_texts=anchor_texts,
        empty_anchors=empty_anchors,
        generic_anchors=generic_anchors,
        keyword_rich_anchors=keyword_rich,
        anchor_diversity=0.0,
    )


def _analyze_structured_data(page: PageDOM) -> StructuredDataAnalysis:
    jsonld = page.jsonld_types
    has_schema = any(
        "schema.org" in t
        or t.startswith(
            (
                "Article",
                "Product",
                "BlogPosting",
                "NewsArticle",
                "WebPage",
                "Organization",
                "Person",
                "BreadcrumbList",
            )
        )
        for t in jsonld
    )
    return StructuredDataAnalysis(
        jsonld_types=jsonld,
        microdata_types=(),
        rdfa_types=(),
        has_schema_org=has_schema,
        schema_count=len(jsonld),
        validation_errors=(),
    )


def _parse_date(date_str: str) -> datetime | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _analyze_freshness(page: PageDOM, html: str) -> FreshnessAnalysis:
    published = None
    modified = None

    for match in _DATETIME_ATTR_RE.findall(html):
        dt = _parse_date(match)
        if dt and published is None:
            published = dt
        elif dt and modified is None:
            modified = dt

    for match in _TIME_TAG_RE.findall(html):
        dt = _parse_date(match)
        if dt and published is None:
            published = dt

    for match in _PUBLISHED_RE.findall(html):
        dt = _parse_date(match)
        if dt and published is None:
            published = dt

    for match in _MODIFIED_RE.findall(html):
        dt = _parse_date(match)
        if dt and modified is None:
            modified = dt

    now = datetime.now(UTC)
    days_pub = (now - published).days if published else None
    days_mod = (now - modified).days if modified else None

    is_stale = False
    if (days_mod is not None and days_mod > 365) or (days_pub is not None and days_pub > 730):
        is_stale = True

    freshness_score = 1.0
    if days_mod is not None:
        freshness_score = max(0.0, 1.0 - days_mod / 730)
    elif days_pub is not None:
        freshness_score = max(0.0, 1.0 - days_pub / 730)

    return FreshnessAnalysis(
        published_date=published,
        modified_date=modified,
        has_date_signals=published is not None or modified is not None,
        days_since_published=days_pub,
        days_since_modified=days_mod,
        is_stale=is_stale,
        freshness_score=round(freshness_score, 4),
    )


def _analyze_multimedia(page: PageDOM, html: str) -> MultimediaAnalysis:
    has_video = bool(
        re.search(r"<video|<source[^>]*video|youtube\.com|vimeo\.com", html, re.IGNORECASE)
    )
    has_audio = bool(
        re.search(r"<audio|<source[^>]*audio|soundcloud\.com|spotify\.com", html, re.IGNORECASE)
    )
    iframes = re.findall(r'<iframe[^>]*src\s*=\s*["\']([^"\']+)["\']', html, re.IGNORECASE)
    has_pdf = bool(re.search(r'\.pdf["\'>\s]', html, re.IGNORECASE))
    video_count = len(re.findall(r"<video\b", html, re.IGNORECASE))
    audio_count = len(re.findall(r"<audio\b", html, re.IGNORECASE))
    embed_domains = tuple(urlparse(src).netloc.lower() for src in iframes if src)

    return MultimediaAnalysis(
        has_video=has_video,
        has_audio=has_audio,
        has_iframe_embeds=len(iframes),
        has_pdf_links=1 if has_pdf else 0,
        has_image_galleries=False,
        video_count=video_count,
        audio_count=audio_count,
        embed_domains=embed_domains,
    )


def _analyze_keywords(text: str, config: ContentAnalysisConfig) -> KeywordDensity:
    words = _split_words(text)
    stopwords = _get_stopwords(config.stopwords_language)
    filtered = [w for w in words if w not in stopwords and len(w) > 2]

    word_freq = Counter(filtered)
    total = len(filtered)
    top_keywords = tuple(
        (w, c, round(c / total, 4)) for w, c in word_freq.most_common(config.max_keywords)
    )

    bigrams = Counter()
    for i in range(len(filtered) - 1):
        bigrams[f"{filtered[i]} {filtered[i + 1]}"] += 1
    bigram_density = tuple(
        (k, v, round(v / max(1, total - 1), 4)) for k, v in bigrams.most_common(20)
    )

    trigrams = Counter()
    for i in range(len(filtered) - 2):
        trigrams[f"{filtered[i]} {filtered[i + 1]} {filtered[i + 2]}"] += 1
    trigram_density = tuple(
        (k, v, round(v / max(1, total - 2), 4)) for k, v in trigrams.most_common(10)
    )

    keyword_stuffing = 0.0
    if top_keywords:
        keyword_stuffing = top_keywords[0][2]

    return KeywordDensity(
        top_keywords=top_keywords,
        bigram_density=bigram_density,
        trigram_density=trigram_density,
        keyword_stuffing_score=round(keyword_stuffing, 4),
    )


def _classify_content_type(page: PageDOM, visible_text: str, html: str) -> ContentType:
    url_path = urlparse(page.url).path.lower()

    if re.search(r"/(product|item|p|shop)/\d", url_path) or re.search(
        r"product|buy now|add to cart|price", html, re.IGNORECASE
    ):
        return ContentType.PRODUCT

    if re.search(r"/(category|cat|c|collection|shop)/", url_path):
        return ContentType.CATEGORY

    if re.search(r"/(blog|post|article)/\d", url_path) or re.search(r"/\d{4}/\d{2}/", url_path):
        return ContentType.BLOG_POST

    if re.search(r"/news/", url_path) or "newsarticle" in str(page.jsonld_types).lower():
        return ContentType.NEWS

    if re.search(r"/docs?/|/documentation|/guide|/tutorial|/api/", url_path):
        return ContentType.DOCUMENTATION

    if re.search(r"/forum|/community|/discussion|/thread/", url_path):
        return ContentType.FORUM

    if re.search(r"/contact", url_path):
        return ContentType.CONTACT

    if re.search(r"/about", url_path):
        return ContentType.ABOUT

    if url_path in ("/", "/home", "/index") or page.url.rstrip("/").endswith(
        (".com", ".org", ".net", ".io")
    ):
        return ContentType.HOME

    if re.search(r"/search", url_path):
        return ContentType.SEARCH

    if re.search(r"/tag|/topic/", url_path):
        return ContentType.TAG

    if re.search(r"/author|/writer/", url_path):
        return ContentType.AUTHOR

    if page.status_code >= 400:
        return ContentType.ERROR

    if page.h1s and len(visible_text) > 500:
        return ContentType.ARTICLE

    return ContentType.LANDING


def _calculate_quality_score(
    metrics: ContentMetrics,
    config: ContentAnalysisConfig,
) -> tuple[float, QualityTier, bool]:
    score = 50.0

    if metrics.word_count >= config.min_word_count:
        score += 15
    elif metrics.word_count >= config.thin_content_threshold:
        score += 5

    if metrics.readability.flesch_reading_ease >= 60:
        score += 10
    elif metrics.readability.flesch_reading_ease >= 30:
        score += 5

    if metrics.headings.has_h1:
        score += 5
    if metrics.headings.heading_depth >= 3:
        score += 5

    if metrics.images.missing_alt_percentage == 0 and metrics.images.total_images > 0:
        score += 5
    elif metrics.images.missing_alt_percentage < 20:
        score += 3

    if metrics.links.internal_links >= 3:
        score += 5
    elif metrics.links.internal_links >= 1:
        score += 2

    if metrics.structured_data.has_schema_org:
        score += 10

    if metrics.freshness.freshness_score > 0.5:
        score += 5

    if metrics.multimedia.has_video or metrics.multimedia.has_audio:
        score += 5

    if metrics.keywords.keyword_stuffing_score > config.keyword_stuffing_threshold:
        score -= 15

    if metrics.html_to_text_ratio < 0.1:
        score -= 10

    score = max(0.0, min(100.0, score))

    if score >= 85:
        tier = QualityTier.EXCELLENT
    elif score >= 70:
        tier = QualityTier.GOOD
    elif score >= 50:
        tier = QualityTier.FAIR
    elif score >= 30:
        tier = QualityTier.POOR
    else:
        tier = QualityTier.THIN

    thin = metrics.word_count < config.thin_content_threshold

    return round(score, 2), tier, thin


def analyze_content(
    page: PageDOM,
    html: str,
    config: ContentAnalysisConfig | None = None,
) -> ContentMetrics:
    """Main entry point: analyze a single page's content."""
    config = config or ContentAnalysisConfig()
    visible_text = _extract_visible_text(page)
    words = _split_words(visible_text)
    unique_words = set(words)

    word_count = len(words)
    unique_word_count = len(unique_words)
    type_token_ratio = unique_word_count / word_count if word_count > 0 else 0.0
    char_count = len(visible_text)
    paragraphs = _split_paragraphs(visible_text)
    paragraph_count = len(paragraphs)
    sentences = _split_sentences(visible_text)
    avg_words_per_sentence = word_count / len(sentences) if sentences else 0.0
    avg_sentences_per_paragraph = len(sentences) / paragraph_count if paragraph_count > 0 else 0.0

    stopwords = _get_stopwords(config.stopwords_language)
    stopword_count = sum(1 for w in words if w in stopwords)
    stopword_ratio = stopword_count / word_count if word_count > 0 else 0.0

    html_size = len(html)
    html_to_text_ratio = char_count / html_size if html_size > 0 else 0.0

    readability = _analyze_readability(visible_text, config)
    headings = _analyze_headings(page, visible_text, config)
    images = _analyze_images(page)
    links = _analyze_links(page)
    structured_data = _analyze_structured_data(page)
    freshness = _analyze_freshness(page, html)
    multimedia = _analyze_multimedia(page, html)
    keywords = _analyze_keywords(visible_text, config)

    content_type = _classify_content_type(page, visible_text, html)

    quality_score_tuple = _calculate_quality_score(
        ContentMetrics(
            url=page.url,
            content_type=content_type,
            visible_text=visible_text,
            word_count=word_count,
            unique_word_count=unique_word_count,
            type_token_ratio=round(type_token_ratio, 4),
            character_count=char_count,
            paragraph_count=paragraph_count,
            avg_words_per_sentence=round(avg_words_per_sentence, 2),
            avg_sentences_per_paragraph=round(avg_sentences_per_paragraph, 2),
            stopword_ratio=round(stopword_ratio, 4),
            html_to_text_ratio=round(html_to_text_ratio, 4),
            readability=readability,
            headings=headings,
            images=images,
            links=links,
            structured_data=structured_data,
            freshness=freshness,
            multimedia=multimedia,
            keywords=keywords,
            quality_score=0.0,
            quality_tier=QualityTier.THIN,
            thin_content=False,
        ),
        config,
    )

    return ContentMetrics(
        url=page.url,
        content_type=content_type,
        visible_text=visible_text,
        word_count=word_count,
        unique_word_count=unique_word_count,
        type_token_ratio=round(type_token_ratio, 4),
        character_count=char_count,
        paragraph_count=paragraph_count,
        avg_words_per_sentence=round(avg_words_per_sentence, 2),
        avg_sentences_per_paragraph=round(avg_sentences_per_paragraph, 2),
        stopword_ratio=round(stopword_ratio, 4),
        html_to_text_ratio=round(html_to_text_ratio, 4),
        readability=readability,
        headings=headings,
        images=images,
        links=links,
        structured_data=structured_data,
        freshness=freshness,
        multimedia=multimedia,
        keywords=keywords,
        quality_score=quality_score_tuple[0],
        quality_tier=quality_score_tuple[1],
        thin_content=quality_score_tuple[2],
    )


def analyze_content_batch(
    pages: list[PageDOM],
    html_map: Mapping[str, str],
    config: ContentAnalysisConfig | None = None,
) -> list[ContentMetrics]:
    """Analyze multiple pages."""
    config = config or ContentAnalysisConfig()
    results = []
    for page in pages:
        html = html_map.get(page.url, "")
        results.append(analyze_content(page, html, config))
    return results
