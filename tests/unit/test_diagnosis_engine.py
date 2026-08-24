"""Unit tests for the SEO Diagnosis engine."""

from sie.domain.engines.diagnosis import (
    BrokenPageDiagnosis,
    DeadEndPageDiagnosis,
    DuplicateContentDiagnosis,
    DuplicateTitleDiagnosis,
    ExcessiveCrawlDepthDiagnosis,
    KeywordStuffingDiagnosis,
    MissingCanonicalDiagnosis,
    MissingH1Diagnosis,
    MissingMetaDescriptionDiagnosis,
    MissingStructuredDataDiagnosis,
    MissingTitleDiagnosis,
    MixedContentDiagnosis,
    MultipleH1Diagnosis,
    NoindexDiagnosis,
    OrphanPageDiagnosis,
    PoorImageAltCoverageDiagnosis,
    PoorReadabilityDiagnosis,
    StaleContentDiagnosis,
    ThinContentDiagnosis,
    WeakInternalLinkingDiagnosis,
    run_diagnosis,
)
from sie.domain.models.audit import (
    AuditFinding,
    SiteArchitectureReport,
    TechnicalAuditResult,
)
from sie.domain.models.content import (
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
from sie.domain.models.diagnosis import (
    DiagnosisCategory,
    DiagnosisPriority,
    DiagnosisSeverity,
)

# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════


def _finding(code: str, url: str = "https://example.com/page", **kwargs):
    return AuditFinding(
        rule_code=code,
        page_url=url,
        severity=kwargs.get("severity", "critical"),
        message=kwargs.get("message", f"Test {code}"),
        recommendation=kwargs.get("recommendation", "Fix it"),
        affected_elements=kwargs.get("affected_elements", ()),
    )


def _technical(*findings):
    findings = list(findings)
    by_sev = {}
    for f in findings:
        by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
    return TechnicalAuditResult(
        total_pages=len({f.page_url for f in findings}) or 1,
        total_issues=len(findings),
        critical_count=by_sev.get("critical", 0),
        warning_count=by_sev.get("warning", 0),
        info_count=by_sev.get("info", 0),
        findings=tuple(findings),
        summary_by_rule={},
        summary_by_severity=dict(by_sev),
        top_offending_pages=(),
    )


def _architecture(
    orphans=(),
    dead_ends=(),
    max_depth=3,
    avg_depth=1.5,
    total_pages=10,
    avg_links=5.0,
):
    return SiteArchitectureReport(
        total_pages=total_pages,
        total_internal_links=int(total_pages * avg_links),
        avg_links_per_page=avg_links,
        orphans=tuple(orphans),
        dead_ends=tuple(dead_ends),
        max_depth=max_depth,
        avg_depth=avg_depth,
        depth_distribution={0: 2, 1: 5, 2: 3},
        pagerank_top_10=(),
        pagerank_bottom_10=(),
        thin_connection_pages=(),
        link_velocity=None,  # type: ignore[arg-type]
    )


def _content_metrics(
    url="https://example.com/page",
    word_count=500,
    quality_tier=QualityTier.GOOD,
    thin_content=False,
    h1_count=1,
    total_images=3,
    images_without_alt=0,
    keyword_stuffing=0.01,
    flesch_ease=60.0,
    is_stale=False,
):
    return ContentMetrics(
        url=url,
        content_type=ContentType.ARTICLE,
        visible_text="word " * word_count,
        word_count=word_count,
        unique_word_count=word_count // 2,
        type_token_ratio=0.5,
        character_count=word_count * 5,
        paragraph_count=10,
        avg_words_per_sentence=15.0,
        avg_sentences_per_paragraph=3.0,
        stopword_ratio=0.4,
        html_to_text_ratio=0.3,
        readability=ReadabilityMetrics(
            flesch_reading_ease=flesch_ease,
            flesch_kincaid_grade=8.0,
            gunning_fog_index=10.0,
            smog_index=10.0,
            automated_readability_index=8.0,
            coleman_liau_index=8.0,
            lix=30.0,
            rix=2.0,
            word_count=word_count,
            sentence_count=30,
            syllable_count=word_count * 15,
        ),
        headings=HeadingAnalysis(
            h1_count=h1_count,
            h2_count=3,
            h3_count=2,
            h4_count=0,
            h5_count=0,
            h6_count=0,
            h1_texts=("Main Heading",),
            h2_texts=("Section 1", "Section 2", "Section 3"),
            h3_texts=("Sub 1", "Sub 2"),
            has_h1=h1_count > 0,
            h1_matches_title=True,
            heading_depth=3,
            heading_keyword_coverage=0.5,
        ),
        images=ImageAnalysis(
            total_images=total_images,
            images_with_alt=total_images - images_without_alt,
            images_without_alt=images_without_alt,
            images_with_empty_alt=0,
            decorative_images=0,
            alt_texts=(),
            missing_alt_percentage=(
                (images_without_alt / total_images * 100) if total_images > 0 else 0.0
            ),
            avg_alt_length=10.0,
            has_lazy_loading=False,
            has_webp=False,
        ),
        links=LinkAnalysis(
            internal_links=5,
            external_links=2,
            nofollow_links=0,
            internal_link_ratio=0.71,
            external_domains=1,
            anchor_texts=("link",),
            empty_anchors=0,
            generic_anchors=0,
            keyword_rich_anchors=0,
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
            published_date=None,
            modified_date=None,
            has_date_signals=False,
            days_since_published=None,
            days_since_modified=None,
            is_stale=is_stale,
            freshness_score=0.5,
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
            top_keywords=(("seo", 10, 0.02),),
            bigram_density=(),
            trigram_density=(),
            keyword_stuffing_score=keyword_stuffing,
        ),
        quality_score=0.7,
        quality_tier=quality_tier,
        thin_content=thin_content,
    )


# ════════════════════════════════════════════════════════════════════════════
# Missing Title Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestMissingTitleDiagnosis:
    def test_detects_missing_title(self):
        finding = _finding("TITLE_MISSING", url="https://example.com/no-title")
        tech = _technical(finding)
        issues = MissingTitleDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_TITLE_MISSING"
        assert issues[0].priority == DiagnosisPriority.P0
        assert issues[0].severity == DiagnosisSeverity.CRITICAL
        assert issues[0].affected_url == "https://example.com/no-title"
        assert issues[0].source_engine == "technical_seo"

    def test_no_issues_when_no_findings(self):
        issues = MissingTitleDiagnosis().evaluate(None, None, None)
        assert issues == ()

    def test_multiple_missing_titles(self):
        tech = _technical(
            _finding("TITLE_MISSING", url="https://example.com/a"),
            _finding("TITLE_MISSING", url="https://example.com/b"),
            _finding("TITLE_MISSING", url="https://example.com/c"),
        )
        issues = MissingTitleDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 3


# ════════════════════════════════════════════════════════════════════════════
# Duplicate Title Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestDuplicateTitleDiagnosis:
    def test_detects_duplicate_title(self):
        finding = _finding(
            "TITLE_DUPLICATE",
            url="https://example.com/a",
            affected_elements=("https://example.com/b", "https://example.com/c"),
        )
        tech = _technical(finding)
        issues = DuplicateTitleDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_TITLE_DUPLICATE"
        assert issues[0].category == DiagnosisCategory.META
        assert len(issues[0].evidence) == 3  # count + 2 duplicate URLs


# ════════════════════════════════════════════════════════════════════════════
# Missing Meta Description Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestMissingMetaDescriptionDiagnosis:
    def test_detects_missing_meta_desc(self):
        finding = _finding("META_DESC_MISSING", url="https://example.com/no-desc")
        tech = _technical(finding)
        issues = MissingMetaDescriptionDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_META_DESC_MISSING"
        assert "click-through rate" in issues[0].explanation


# ════════════════════════════════════════════════════════════════════════════
# Missing Canonical Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestMissingCanonicalDiagnosis:
    def test_detects_missing_canonical(self):
        finding = _finding("CANONICAL_MISSING", url="https://example.com/no-canonical")
        tech = _technical(finding)
        issues = MissingCanonicalDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_CANONICAL_MISSING"
        assert "canonical" in issues[0].explanation.lower()


# ════════════════════════════════════════════════════════════════════════════
# Broken Page Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestBrokenPageDiagnosis:
    def test_detects_404(self):
        finding = _finding("STATUS_404", url="https://example.com/missing")
        tech = _technical(finding)
        issues = BrokenPageDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_BROKEN_PAGE"
        assert issues[0].category == DiagnosisCategory.STATUS

    def test_detects_5xx(self):
        finding = _finding("STATUS_5XX", url="https://example.com/error")
        tech = _technical(finding)
        issues = BrokenPageDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_BROKEN_PAGE"

    def test_mixed_404_and_5xx(self):
        tech = _technical(
            _finding("STATUS_404", url="https://example.com/a"),
            _finding("STATUS_5XX", url="https://example.com/b"),
            _finding("STATUS_404", url="https://example.com/c"),
        )
        issues = BrokenPageDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 3


# ════════════════════════════════════════════════════════════════════════════
# Noindex Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestNoindexDiagnosis:
    def test_detects_noindex(self):
        finding = _finding("META_ROBOTS_NOINDEX", url="https://example.com/noindex")
        tech = _technical(finding)
        issues = NoindexDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].priority == DiagnosisPriority.P1
        assert issues[0].severity == DiagnosisSeverity.HIGH


# ════════════════════════════════════════════════════════════════════════════
# H1 Missing / Multiple Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestH1Diagnosis:
    def test_detects_missing_h1(self):
        finding = _finding("H1_MISSING", url="https://example.com/no-h1")
        tech = _technical(finding)
        issues = MissingH1Diagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_H1_MISSING"
        assert issues[0].category == DiagnosisCategory.STRUCTURE

    def test_detects_multiple_h1(self):
        finding = _finding("H1_MULTIPLE", url="https://example.com/multi-h1")
        tech = _technical(finding)
        issues = MultipleH1Diagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_H1_MULTIPLE"


# ════════════════════════════════════════════════════════════════════════════
# Mixed Content Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestMixedContentDiagnosis:
    def test_detects_mixed_content(self):
        finding = _finding("MIXED_CONTENT", url="https://example.com/mixed")
        tech = _technical(finding)
        issues = MixedContentDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].category == DiagnosisCategory.SECURITY


# ════════════════════════════════════════════════════════════════════════════
# Structured Data Missing Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestStructuredDataDiagnosis:
    def test_detects_missing_structured_data(self):
        finding = _finding("JSONLD_MISSING", url="https://example.com/no-jsonld")
        tech = _technical(finding)
        issues = MissingStructuredDataDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert issues[0].priority == DiagnosisPriority.P2


# ════════════════════════════════════════════════════════════════════════════
# Orphan Page Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestOrphanPageDiagnosis:
    def test_detects_orphans(self):
        arch = _architecture(orphans=("https://example.com/orphan1", "https://example.com/orphan2"))
        issues = OrphanPageDiagnosis().evaluate(None, arch, None)
        assert len(issues) == 2
        assert all(i.rule_code == "DX_ORPHAN_PAGE" for i in issues)
        assert all(i.priority == DiagnosisPriority.P1 for i in issues)
        urls = {i.affected_url for i in issues}
        assert "https://example.com/orphan1" in urls
        assert "https://example.com/orphan2" in urls

    def test_no_issues_without_architecture(self):
        issues = OrphanPageDiagnosis().evaluate(None, None, None)
        assert issues == ()

    def test_no_issues_when_no_orphans(self):
        arch = _architecture(orphans=())
        issues = OrphanPageDiagnosis().evaluate(None, arch, None)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Dead End Page Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestDeadEndPageDiagnosis:
    def test_detects_dead_ends(self):
        arch = _architecture(dead_ends=("https://example.com/dead1",))
        issues = DeadEndPageDiagnosis().evaluate(None, arch, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_DEAD_END_PAGE"
        assert issues[0].category == DiagnosisCategory.LINKS


# ════════════════════════════════════════════════════════════════════════════
# Excessive Depth Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestExcessiveDepthDiagnosis:
    def test_detects_excessive_depth(self):
        arch = _architecture(max_depth=8)
        issues = ExcessiveCrawlDepthDiagnosis().evaluate(None, arch, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_EXCESSIVE_DEPTH"
        assert issues[0].affected_url == "(site-wide)"

    def test_no_issue_when_depth_ok(self):
        arch = _architecture(max_depth=3)
        issues = ExcessiveCrawlDepthDiagnosis().evaluate(None, arch, None)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Weak Internal Linking Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestWeakInternalLinkingDiagnosis:
    def test_detects_weak_linking(self):
        arch = _architecture(total_pages=10, avg_links=1.5)
        issues = WeakInternalLinkingDiagnosis().evaluate(None, arch, None)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_WEAK_INTERNAL_LINKING"

    def test_no_issue_when_linking_ok(self):
        arch = _architecture(total_pages=10, avg_links=5.0)
        issues = WeakInternalLinkingDiagnosis().evaluate(None, arch, None)
        assert issues == ()

    def test_single_page_no_issue(self):
        arch = _architecture(total_pages=1, avg_links=0.0)
        issues = WeakInternalLinkingDiagnosis().evaluate(None, arch, None)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Image Alt Coverage Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestPoorImageAltCoverageDiagnosis:
    def test_detects_poor_alt_coverage(self):
        metrics = [
            _content_metrics(
                url="https://example.com/img-page",
                total_images=10,
                images_without_alt=8,
            )
        ]
        issues = PoorImageAltCoverageDiagnosis().evaluate(None, None, metrics)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_IMAGE_ALT_COVERAGE"
        assert issues[0].category == DiagnosisCategory.ACCESSIBILITY

    def test_no_issue_when_coverage_ok(self):
        metrics = [
            _content_metrics(
                url="https://example.com/good",
                total_images=10,
                images_without_alt=2,
            )
        ]
        issues = PoorImageAltCoverageDiagnosis().evaluate(None, None, metrics)
        assert issues == ()

    def test_no_issue_when_no_images(self):
        metrics = [
            _content_metrics(
                url="https://example.com/no-images",
                total_images=0,
                images_without_alt=0,
            )
        ]
        issues = PoorImageAltCoverageDiagnosis().evaluate(None, None, metrics)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Thin Content Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestThinContentDiagnosis:
    def test_detects_thin_content(self):
        metrics = [
            _content_metrics(
                url="https://example.com/thin",
                word_count=50,
                thin_content=True,
            )
        ]
        issues = ThinContentDiagnosis().evaluate(None, None, metrics)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_THIN_CONTENT"
        assert issues[0].priority == DiagnosisPriority.P1

    def test_no_issue_when_content_ok(self):
        metrics = [_content_metrics(word_count=1000)]
        issues = ThinContentDiagnosis().evaluate(None, None, metrics)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Keyword Stuffing Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestKeywordStuffingDiagnosis:
    def test_detects_keyword_stuffing(self):
        metrics = [
            _content_metrics(
                url="https://example.com/stuffed",
                keyword_stuffing=0.08,
            )
        ]
        issues = KeywordStuffingDiagnosis().evaluate(None, None, metrics)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_KEYWORD_STUFFING"

    def test_no_issue_when_density_ok(self):
        metrics = [_content_metrics(keyword_stuffing=0.02)]
        issues = KeywordStuffingDiagnosis().evaluate(None, None, metrics)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Readability Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestPoorReadabilityDiagnosis:
    def test_detects_poor_readability(self):
        metrics = [
            _content_metrics(
                url="https://example.com/hard",
                flesch_ease=15.0,
            )
        ]
        issues = PoorReadabilityDiagnosis().evaluate(None, None, metrics)
        assert len(issues) == 1
        assert issues[0].priority == DiagnosisPriority.P3

    def test_no_issue_when_readable(self):
        metrics = [_content_metrics(flesch_ease=60.0)]
        issues = PoorReadabilityDiagnosis().evaluate(None, None, metrics)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# Stale Content Diagnosis
# ════════════════════════════════════════════════════════════════════════════


class TestStaleContentDiagnosis:
    def test_detects_stale_content(self):
        metrics = [
            _content_metrics(
                url="https://example.com/stale",
                is_stale=True,
            )
        ]
        issues = StaleContentDiagnosis().evaluate(None, None, metrics)
        assert len(issues) == 1
        assert issues[0].rule_code == "DX_STALE_CONTENT"

    def test_no_issue_when_fresh(self):
        metrics = [_content_metrics(is_stale=False)]
        issues = StaleContentDiagnosis().evaluate(None, None, metrics)
        assert issues == ()


# ════════════════════════════════════════════════════════════════════════════
# run_diagnosis integration
# ════════════════════════════════════════════════════════════════════════════


class TestRunDiagnosis:
    def test_empty_inputs_produce_no_issues(self):
        result = run_diagnosis("test-run-1")
        assert result.total_issues == 0
        assert result.run_id == "test-run-1"

    def test_combines_technical_and_architecture_signals(self):
        tech = _technical(
            _finding("TITLE_MISSING", url="https://example.com/a"),
            _finding("H1_MISSING", url="https://example.com/a"),
            _finding("STATUS_404", url="https://example.com/b"),
        )
        arch = _architecture(
            orphans=("https://example.com/c",),
            dead_ends=("https://example.com/d",),
        )
        result = run_diagnosis("test-run-2", technical=tech, architecture=arch)
        assert result.total_issues >= 5  # 3 tech + 1 orphan + 1 dead end
        assert result.issues_by_priority.get("P0", 0) >= 3
        assert result.issues_by_priority.get("P1", 0) >= 1

    def test_priority_filtering(self):
        tech = _technical(
            _finding("TITLE_MISSING", url="https://example.com/a"),
            _finding("META_ROBOTS_NOINDEX", url="https://example.com/b"),
        )
        result = run_diagnosis("test-run-3", technical=tech, priorities={"P0"})
        assert result.total_issues == 1
        assert result.issues[0].rule_code == "DX_TITLE_MISSING"

    def test_content_metrics_integration(self):
        metrics = [
            _content_metrics(
                url="https://example.com/thin",
                word_count=50,
                thin_content=True,
            ),
            _content_metrics(
                url="https://example.com/stuffed",
                keyword_stuffing=0.08,
            ),
        ]
        result = run_diagnosis("test-run-4", content_metrics=metrics)
        assert result.total_issues >= 2
        codes = {i.rule_code for i in result.issues}
        assert "DX_THIN_CONTENT" in codes

    def test_top_affected_pages(self):
        tech = _technical(
            _finding("TITLE_MISSING", url="https://example.com/a"),
            _finding("H1_MISSING", url="https://example.com/a"),
            _finding("META_DESC_MISSING", url="https://example.com/a"),
            _finding("STATUS_404", url="https://example.com/b"),
        )
        result = run_diagnosis("test-run-5", technical=tech)
        assert len(result.top_affected_pages) > 0
        assert result.top_affected_pages[0] == "https://example.com/a"

    def test_issues_by_category(self):
        tech = _technical(
            _finding("TITLE_MISSING", url="https://example.com/a"),
            _finding("STATUS_404", url="https://example.com/b"),
        )
        arch = _architecture(orphans=("https://example.com/c",))
        result = run_diagnosis("test-run-6", technical=tech, architecture=arch)
        assert "meta" in result.issues_by_category
        assert "status" in result.issues_by_category
        assert "links" in result.issues_by_category


# ════════════════════════════════════════════════════════════════════════════
# Evidence validation
# ════════════════════════════════════════════════════════════════════════════


class TestDiagnosisEvidence:
    def test_issues_contain_evidence(self):
        finding = _finding("TITLE_MISSING", url="https://example.com/evidence")
        tech = _technical(finding)
        issues = MissingTitleDiagnosis().evaluate(tech, None, None)
        assert len(issues) == 1
        assert len(issues[0].evidence) >= 1
        assert issues[0].evidence[0].metric_name == "title_present"
        assert issues[0].evidence[0].metric_value is False

    def test_orphan_issues_contain_evidence(self):
        arch = _architecture(orphans=("https://example.com/orphan",))
        issues = OrphanPageDiagnosis().evaluate(None, arch, None)
        assert len(issues) == 1
        assert len(issues[0].evidence) >= 1
        assert issues[0].evidence[0].metric_name == "incoming_internal_links"
        assert issues[0].evidence[0].metric_value == 0


# ════════════════════════════════════════════════════════════════════════════
# Language convention checks
# ════════════════════════════════════════════════════════════════════════════


class TestLanguageConvention:
    """Verify diagnosis language uses measured phrasing, not ranking claims."""

    _RANKING_KEYWORDS = ("will drop", "will hurt ranking", "google penalty", "rank higher")

    def _check_rule_language(self, rule_cls, **kwargs):
        finding = _finding(
            rule_cls.code.replace("DX_", "").lower(),
            url="https://example.com/test",
        )
        # Build minimal inputs for the rule
        tech = _technical(finding) if rule_cls.source_engine == "technical_seo" else None
        arch = (
            _architecture(
                orphans=(finding.page_url,),
                dead_ends=(finding.page_url,),
            )
            if rule_cls.source_engine == "link_graph"
            else None
        )
        metrics = (
            [_content_metrics(url=finding.page_url)]
            if rule_cls.source_engine == "content_intelligence"
            else None
        )
        issues = rule_cls().evaluate(tech, arch, metrics)
        for issue in issues:
            for keyword in self._RANKING_KEYWORDS:
                assert keyword not in issue.explanation.lower(), (
                    f"{issue.rule_code} contains ranking claim: '{keyword}'"
                )
                assert keyword not in issue.recommendation.lower(), (
                    f"{issue.rule_code} recommendation contains ranking claim: '{keyword}'"
                )

    def test_all_rules_use_measured_language(self):
        all_rule_classes = [
            MissingTitleDiagnosis,
            DuplicateTitleDiagnosis,
            MissingMetaDescriptionDiagnosis,
            MissingCanonicalDiagnosis,
            BrokenPageDiagnosis,
            NoindexDiagnosis,
            MissingH1Diagnosis,
            MultipleH1Diagnosis,
            MixedContentDiagnosis,
            MissingStructuredDataDiagnosis,
            OrphanPageDiagnosis,
            DeadEndPageDiagnosis,
            ExcessiveCrawlDepthDiagnosis,
            WeakInternalLinkingDiagnosis,
            ThinContentDiagnosis,
            DuplicateContentDiagnosis,
            KeywordStuffingDiagnosis,
            PoorReadabilityDiagnosis,
            StaleContentDiagnosis,
            PoorImageAltCoverageDiagnosis,
        ]
        for rule_cls in all_rule_classes:
            self._check_rule_language(rule_cls)
