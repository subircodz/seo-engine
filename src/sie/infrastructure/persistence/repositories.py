"""SQLAlchemy implementations of the crawl persistence ports."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sie.domain.models.content import (
    ContentComparison,
    ContentMetrics,
    ContentQualityReport,
    QualityTier,
)
from sie.domain.models.crawl import (
    CrawlPageRecord,
    CrawlRunRecord,
    CrawlStatus,
)
from sie.infrastructure.models.content_orm import (
    ContentComparisonRow,
    ContentMetricsRow,
    ContentQualityReportRow,
)
from sie.infrastructure.models.crawl_orm import CrawlPageRow, CrawlRunRow


def _naive(aware: datetime) -> datetime:
    return aware.astimezone(UTC).replace(tzinfo=None)


def _to_aware(naive: datetime | None) -> datetime | None:
    if naive is None:
        return None
    return naive.replace(tzinfo=UTC)


def _serialize_serp_features(features: tuple) -> list[dict] | None:
    """Serialize SERP features tuple to JSON-serializable list of dicts."""
    if not features:
        return None
    result = []
    for f in features:
        feature_dict = {
            "feature_type": f.feature_type.value,
            "position": f.position,
            "title": f.title,
            "url": f.url,
            "domain": f.domain,
            "metadata": dict(f.metadata) if f.metadata else {},
        }
        result.append(feature_dict)
    return result


def _deserialize_serp_features(data: list[dict] | None) -> tuple:
    """Deserialize JSON list of dicts back to SERP features tuple."""
    from sie.domain.models.search_serp import SearchSERPFeature, SERPFeatureType

    if not data:
        return ()
    features = []
    for item in data:
        feature = SearchSERPFeature(
            feature_type=SERPFeatureType(item["feature_type"]),
            position=item.get("position"),
            title=item.get("title"),
            url=item.get("url"),
            _metadata=tuple(item.get("metadata", {}).items()) if item.get("metadata") else (),
        )
        features.append(feature)
    return tuple(features)


class SqlAlchemyCrawlRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_run(self, run: CrawlRunRecord) -> None:
        async with self._sf() as session:
            session.add(
                CrawlRunRow(
                    id=run.id,
                    target_url=run.target_url,
                    status=run.status.value,
                    started_at=_naive(run.started_at),
                    policy_snapshot=dict(run.policy_snapshot),
                    total_pages=run.total_pages,
                    error_count=run.error_count,
                )
            )
            await session.commit()

    async def finish_run(
        self,
        run_id: str,
        *,
        status: CrawlStatus,
        completed_at: datetime,
        error: str | None = None,
        total_pages: int = 0,
        error_count: int = 0,
    ) -> None:
        async with self._sf() as session:
            row = await session.get(CrawlRunRow, run_id)
            if row is None:
                return
            row.status = status.value
            row.completed_at = _naive(completed_at)
            row.error = error
            row.total_pages = total_pages
            row.error_count = error_count
            await session.commit()

    async def get_run(self, run_id: str) -> CrawlRunRecord | None:
        async with self._sf() as session:
            row = await session.get(CrawlRunRow, run_id)
            if row is None:
                return None
            return CrawlRunRecord(
                id=row.id,
                target_url=row.target_url,
                status=CrawlStatus(row.status),
                started_at=_to_aware(row.started_at),
                completed_at=_to_aware(row.completed_at),
                policy_snapshot=row.policy_snapshot or {},
                error=row.error,
                total_pages=row.total_pages or 0,
                error_count=row.error_count or 0,
            )

    async def add_page(self, run_id: str, page: CrawlPageRecord) -> None:
        async with self._sf() as session:
            session.add(
                CrawlPageRow(
                    run_id=run_id,
                    url=page.url,
                    status_code=page.status_code,
                    fetched_at=_naive(page.fetched_at) if page.fetched_at is not None else None,
                    error_message=page.error_message,
                    html_size=page.html_size,
                    content_type=page.content_type,
                    depth=page.depth,
                    parent_url=page.parent_url,
                )
            )
            await session.commit()

    async def list_pages(
        self, run_id: str, *, limit: int, offset: int
    ) -> tuple[int, list[CrawlPageRecord]]:
        async with self._sf() as session:
            total = (
                await session.execute(
                    select(func.count())
                    .select_from(CrawlPageRow)
                    .where(CrawlPageRow.run_id == run_id)
                )
            ).scalar_one()
            rows = (
                (
                    await session.execute(
                        select(CrawlPageRow)
                        .where(CrawlPageRow.run_id == run_id)
                        .order_by(CrawlPageRow.id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return total, [self._page_record(r) for r in rows]

    @staticmethod
    def _page_record(row: CrawlPageRow) -> CrawlPageRecord:
        return CrawlPageRecord(
            url=row.url,
            status_code=row.status_code,
            fetched_at=_to_aware(row.fetched_at),
            html_size=row.html_size,
            error_message=row.error_message,
            content_type=row.content_type,
            depth=row.depth,
            parent_url=row.parent_url,
        )

    async def list_runs(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[int, list[CrawlRunRecord]]:
        async with self._sf() as session:
            total = (
                await session.execute(select(func.count()).select_from(CrawlRunRow))
            ).scalar_one()
            rows = (
                await session.execute(
                    select(CrawlRunRow)
                    .order_by(CrawlRunRow.started_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).scalars()
            return total, [self._run_record(r) for r in rows]

    @staticmethod
    def _run_record(row: CrawlRunRow) -> CrawlRunRecord:
        return CrawlRunRecord(
            id=row.id,
            target_url=row.target_url,
            status=CrawlStatus(row.status),
            started_at=_to_aware(row.started_at) or row.started_at.replace(tzinfo=UTC),
            completed_at=_to_aware(row.completed_at),
            policy_snapshot=row.policy_snapshot or {},
            error=row.error,
            total_pages=row.total_pages or 0,
            error_count=row.error_count or 0,
        )

    # ── Content Intelligence Persistence ────────────────────────────────────────

    async def save_content_metrics(self, run_id: str, metrics: list[ContentMetrics]) -> None:
        async with self._sf() as session:
            for m in metrics:
                session.add(
                    ContentMetricsRow(
                        run_id=run_id,
                        url=m.url,
                        content_type=m.content_type.value,
                        visible_text=m.visible_text,
                        word_count=m.word_count,
                        unique_word_count=m.unique_word_count,
                        type_token_ratio=m.type_token_ratio,
                        character_count=m.character_count,
                        paragraph_count=m.paragraph_count,
                        avg_words_per_sentence=m.avg_words_per_sentence,
                        avg_sentences_per_paragraph=m.avg_sentences_per_paragraph,
                        stopword_ratio=m.stopword_ratio,
                        html_to_text_ratio=m.html_to_text_ratio,
                        readability=self._readability_to_dict(m.readability),
                        headings=self._headings_to_dict(m.headings),
                        images=self._images_to_dict(m.images),
                        links=self._links_to_dict(m.links),
                        structured_data=self._structured_data_to_dict(m.structured_data),
                        freshness=self._freshness_to_dict(m.freshness),
                        multimedia=self._multimedia_to_dict(m.multimedia),
                        keywords=self._keywords_to_dict(m.keywords),
                        quality_score=m.quality_score,
                        quality_tier=m.quality_tier.value,
                        thin_content=m.thin_content,
                        extracted_at=m.extracted_at.replace(tzinfo=None)
                        if m.extracted_at.tzinfo
                        else m.extracted_at,
                    )
                )
            await session.commit()

    async def get_content_metrics(self, run_id: str) -> list[ContentMetrics]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(ContentMetricsRow)
                        .where(ContentMetricsRow.run_id == run_id)
                        .order_by(ContentMetricsRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [self._metrics_from_row(r) for r in rows]

    async def save_content_comparisons(
        self, run_id: str, comparisons: list[ContentComparison]
    ) -> None:
        async with self._sf() as session:
            for c in comparisons:
                session.add(
                    ContentComparisonRow(
                        run_id=run_id,
                        url_a=c.url_a,
                        url_b=c.url_b,
                        similarity_score=c.similarity_score,
                        jaccard_similarity=c.jaccard_similarity,
                        cosine_similarity=c.cosine_similarity,
                        word_overlap_count=c.word_overlap_count,
                        word_overlap_ratio=c.word_overlap_ratio,
                        structural_similarity=c.structural_similarity,
                        duplicate_status=c.duplicate_status.value,
                        compared_at=c.compared_at.replace(tzinfo=None)
                        if c.compared_at.tzinfo
                        else c.compared_at,
                    )
                )
            await session.commit()

    async def get_content_comparisons(self, run_id: str) -> list[ContentComparison]:
        async with self._sf() as session:
            rows = (
                (
                    await session.execute(
                        select(ContentComparisonRow)
                        .where(ContentComparisonRow.run_id == run_id)
                        .order_by(ContentComparisonRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [self._comparison_from_row(r) for r in rows]

    async def save_quality_report(self, run_id: str, report: ContentQualityReport) -> None:
        async with self._sf() as session:
            existing = await session.get(ContentQualityReportRow, run_id)
            if existing:
                existing.total_pages = report.total_pages
                existing.analyzed_pages = report.analyzed_pages
                existing.avg_quality_score = report.avg_quality_score
                existing.quality_distribution = dict(report.quality_distribution)
                existing.thin_content_pages = list(report.thin_content_pages)
                existing.duplicate_groups = [list(g) for g in report.duplicate_groups]
                existing.top_issues = list(report.top_issues)
                existing.generated_at = _naive(report.generated_at)
            else:
                session.add(
                    ContentQualityReportRow(
                        run_id=run_id,
                        total_pages=report.total_pages,
                        analyzed_pages=report.analyzed_pages,
                        avg_quality_score=report.avg_quality_score,
                        quality_distribution=dict(report.quality_distribution),
                        thin_content_pages=list(report.thin_content_pages),
                        duplicate_groups=[list(g) for g in report.duplicate_groups],
                        top_issues=list(report.top_issues),
                        generated_at=_naive(report.generated_at),
                    )
                )
            await session.commit()

    async def get_quality_report(self, run_id: str) -> ContentQualityReport | None:
        async with self._sf() as session:
            row = await session.get(ContentQualityReportRow, run_id)
            if row is None:
                return None
            return ContentQualityReport(
                run_id=row.run_id,
                total_pages=row.total_pages,
                analyzed_pages=row.analyzed_pages,
                avg_quality_score=row.avg_quality_score,
                quality_distribution={
                    QualityTier(k): v for k, v in row.quality_distribution.items()
                },
                thin_content_pages=tuple(row.thin_content_pages),
                duplicate_groups=tuple(tuple(g) for g in row.duplicate_groups),
                top_issues=tuple(tuple(i) for i in row.top_issues),
                generated_at=row.generated_at.replace(tzinfo=UTC),
            )

    # ── Helpers for serialization ──────────────────────────────────────────────

    def _readability_to_dict(self, r) -> dict:
        return {
            "flesch_reading_ease": r.flesch_reading_ease,
            "flesch_kincaid_grade": r.flesch_kincaid_grade,
            "gunning_fog_index": r.gunning_fog_index,
            "smog_index": r.smog_index,
            "automated_readability_index": r.automated_readability_index,
            "coleman_liau_index": r.coleman_liau_index,
            "lix": r.lix,
            "rix": r.rix,
            "word_count": r.word_count,
            "sentence_count": r.sentence_count,
            "syllable_count": r.syllable_count,
        }

    def _headings_to_dict(self, h) -> dict:
        return {
            "h1_count": h.h1_count,
            "h2_count": h.h2_count,
            "h3_count": h.h3_count,
            "h4_count": h.h4_count,
            "h5_count": h.h5_count,
            "h6_count": h.h6_count,
            "h1_texts": list(h.h1_texts),
            "h2_texts": list(h.h2_texts),
            "h3_texts": list(h.h3_texts),
            "has_h1": h.has_h1,
            "h1_matches_title": h.h1_matches_title,
            "heading_depth": h.heading_depth,
            "heading_keyword_coverage": h.heading_keyword_coverage,
        }

    def _images_to_dict(self, i) -> dict:
        return {
            "total_images": i.total_images,
            "images_with_alt": i.images_with_alt,
            "images_without_alt": i.images_without_alt,
            "images_with_empty_alt": i.images_with_empty_alt,
            "decorative_images": i.decorative_images,
            "alt_texts": list(i.alt_texts),
            "missing_alt_percentage": i.missing_alt_percentage,
            "avg_alt_length": i.avg_alt_length,
            "has_lazy_loading": i.has_lazy_loading,
            "has_webp": i.has_webp,
        }

    def _links_to_dict(self, links) -> dict:
        return {
            "internal_links": links.internal_links,
            "external_links": links.external_links,
            "nofollow_links": links.nofollow_links,
            "internal_link_ratio": links.internal_link_ratio,
            "external_domains": links.external_domains,
            "anchor_texts": list(links.anchor_texts),
            "empty_anchors": links.empty_anchors,
            "generic_anchors": links.generic_anchors,
            "keyword_rich_anchors": links.keyword_rich_anchors,
            "anchor_diversity": links.anchor_diversity,
        }

    def _structured_data_to_dict(self, s) -> dict:
        return {
            "jsonld_types": list(s.jsonld_types),
            "microdata_types": list(s.microdata_types),
            "rdfa_types": list(s.rdfa_types),
            "has_schema_org": s.has_schema_org,
            "schema_count": s.schema_count,
            "validation_errors": list(s.validation_errors),
        }

    def _freshness_to_dict(self, f) -> dict:
        return {
            "published_date": f.published_date.isoformat() if f.published_date else None,
            "modified_date": f.modified_date.isoformat() if f.modified_date else None,
            "has_date_signals": f.has_date_signals,
            "days_since_published": f.days_since_published,
            "days_since_modified": f.days_since_modified,
            "is_stale": f.is_stale,
            "freshness_score": f.freshness_score,
        }

    def _multimedia_to_dict(self, m) -> dict:
        return {
            "has_video": m.has_video,
            "has_audio": m.has_audio,
            "has_iframe_embeds": m.has_iframe_embeds,
            "has_pdf_links": m.has_pdf_links,
            "has_image_galleries": m.has_image_galleries,
            "video_count": m.video_count,
            "audio_count": m.audio_count,
            "embed_domains": list(m.embed_domains),
        }

    def _keywords_to_dict(self, k) -> dict:
        return {
            "top_keywords": [[w, c, d] for w, c, d in k.top_keywords],
            "bigram_density": [[w, c, d] for w, c, d in k.bigram_density],
            "trigram_density": [[w, c, d] for w, c, d in k.trigram_density],
            "keyword_stuffing_score": k.keyword_stuffing_score,
        }

    def _metrics_from_row(self, row: ContentMetricsRow) -> ContentMetrics:
        from sie.domain.models.content import (
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

        return ContentMetrics(
            url=row.url,
            content_type=ContentType(row.content_type),
            visible_text=row.visible_text or "",
            word_count=row.word_count,
            unique_word_count=row.unique_word_count,
            type_token_ratio=row.type_token_ratio,
            character_count=row.character_count,
            paragraph_count=row.paragraph_count,
            avg_words_per_sentence=row.avg_words_per_sentence,
            avg_sentences_per_paragraph=row.avg_sentences_per_paragraph,
            stopword_ratio=row.stopword_ratio,
            html_to_text_ratio=row.html_to_text_ratio,
            readability=ReadabilityMetrics(**row.readability),
            headings=HeadingAnalysis(**row.headings),
            images=ImageAnalysis(**row.images),
            links=LinkAnalysis(**row.links),
            structured_data=StructuredDataAnalysis(**row.structured_data),
            freshness=FreshnessAnalysis(
                published_date=row.freshness.get("published_date")
                and datetime.fromisoformat(row.freshness["published_date"]),
                modified_date=row.freshness.get("modified_date")
                and datetime.fromisoformat(row.freshness["modified_date"]),
                has_date_signals=row.freshness["has_date_signals"],
                days_since_published=row.freshness.get("days_since_published"),
                days_since_modified=row.freshness.get("days_since_modified"),
                is_stale=row.freshness["is_stale"],
                freshness_score=row.freshness["freshness_score"],
            ),
            multimedia=MultimediaAnalysis(**row.multimedia),
            keywords=KeywordDensity(
                top_keywords=tuple(tuple(x) for x in row.keywords["top_keywords"]),
                bigram_density=tuple(tuple(x) for x in row.keywords["bigram_density"]),
                trigram_density=tuple(tuple(x) for x in row.keywords["trigram_density"]),
                keyword_stuffing_score=row.keywords["keyword_stuffing_score"],
            ),
            quality_score=row.quality_score,
            quality_tier=QualityTier(row.quality_tier),
            thin_content=bool(row.thin_content),
            extracted_at=row.extracted_at.replace(tzinfo=UTC),
        )

    def _comparison_from_row(self, row: ContentComparisonRow) -> ContentComparison:
        from sie.domain.models.content import DuplicateStatus

        return ContentComparison(
            url_a=row.url_a,
            url_b=row.url_b,
            similarity_score=row.similarity_score,
            jaccard_similarity=row.jaccard_similarity,
            cosine_similarity=row.cosine_similarity,
            word_overlap_count=row.word_overlap_count,
            word_overlap_ratio=row.word_overlap_ratio,
            structural_similarity=row.structural_similarity,
            duplicate_status=DuplicateStatus(row.duplicate_status),
            compared_at=row.compared_at.replace(tzinfo=UTC),
        )

    # ── Diagnosis persistence ────────────────────────────────────────────────

    async def save_diagnosis_result(self, run_id: str, result) -> None:
        from sie.infrastructure.models.diagnosis_orm import DiagnosisResultRow

        issues_data = [
            {
                "rule_code": i.rule_code,
                "category": i.category.value,
                "severity": i.severity.value,
                "priority": i.priority.value,
                "affected_url": i.affected_url,
                "explanation": i.explanation,
                "recommendation": i.recommendation,
                "evidence": [
                    {
                        "metric_name": e.metric_name,
                        "metric_value": e.metric_value,
                        "threshold": e.threshold,
                        "description": e.description,
                        "source_url": e.source_url,
                    }
                    for e in i.evidence
                ],
                "confidence": i.confidence,
                "source_engine": i.source_engine,
                "detected_at": i.detected_at.isoformat(),
            }
            for i in result.issues
        ]

        async with self._sf() as session:
            session.add(
                DiagnosisResultRow(
                    run_id=run_id,
                    total_issues=result.total_issues,
                    issues_by_priority=result.issues_by_priority,
                    issues_by_severity=result.issues_by_severity,
                    issues_by_category=result.issues_by_category,
                    issues=issues_data,
                    top_affected_pages=list(result.top_affected_pages),
                    generated_at=_naive(result.generated_at),
                )
            )
            await session.commit()

    async def get_diagnosis_result(self, run_id: str):
        from sie.domain.models.diagnosis import (
            DiagnosisCategory,
            DiagnosisEvidence,
            DiagnosisIssue,
            DiagnosisPriority,
            DiagnosisResult,
            DiagnosisSeverity,
        )
        from sie.infrastructure.models.diagnosis_orm import DiagnosisResultRow

        async with self._sf() as session:
            stmt = select(DiagnosisResultRow).where(DiagnosisResultRow.run_id == run_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

        issues = tuple(
            DiagnosisIssue(
                rule_code=d["rule_code"],
                category=DiagnosisCategory(d["category"]),
                severity=DiagnosisSeverity(d["severity"]),
                priority=DiagnosisPriority(d["priority"]),
                affected_url=d["affected_url"],
                explanation=d["explanation"],
                recommendation=d["recommendation"],
                evidence=tuple(
                    DiagnosisEvidence(
                        metric_name=e["metric_name"],
                        metric_value=e.get("metric_value"),
                        threshold=e.get("threshold"),
                        description=e.get("description", ""),
                        source_url=e.get("source_url", ""),
                    )
                    for e in d.get("evidence", [])
                ),
                confidence=d.get("confidence", 1.0),
                source_engine=d.get("source_engine", ""),
            )
            for d in row.issues
        )

        return DiagnosisResult(
            run_id=row.run_id,
            total_issues=row.total_issues,
            issues_by_priority=row.issues_by_priority,
            issues_by_severity=row.issues_by_severity,
            issues_by_category=row.issues_by_category,
            issues=issues,
            top_affected_pages=tuple(row.top_affected_pages),
            generated_at=_to_aware(row.generated_at) or row.generated_at.replace(tzinfo=UTC),
        )

    # ── Intelligence Report persistence (Phase 5C) ─────────────────────────

    async def save_intelligence_report(self, run_id: str, report) -> None:
        from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow

        async with self._sf() as session:
            session.add(
                IntelligenceReportRow(
                    intelligence_id=report.intelligence_id,
                    run_id=run_id,
                    diagnosis_run_id=report.diagnosis_run_id,
                    prompt_version=report.prompt_version,
                    model_name=report.model_name,
                    provider=report.provider,
                    summary=report.summary,
                    overall_assessment=report.overall_assessment,
                    root_causes=[
                        {
                            "title": rc.title,
                            "evidence": list(rc.evidence),
                            "confidence": rc.confidence,
                        }
                        for rc in report.root_causes
                    ],
                    top_issues=[
                        {
                            "issue_code": ti.issue_code,
                            "title": ti.title,
                            "interpretation": ti.interpretation,
                            "impact": ti.impact,
                            "confidence": ti.confidence,
                            "affected_url_count": ti.affected_url_count,
                        }
                        for ti in report.top_issues
                    ],
                    quick_wins=[
                        {
                            "action": qw.action,
                            "reason": qw.reason,
                            "priority": qw.priority,
                            "difficulty": qw.difficulty,
                        }
                        for qw in report.quick_wins
                    ],
                    action_plan=[
                        {
                            "order": ap.order,
                            "action": ap.action,
                            "reason": ap.reason,
                            "priority": ap.priority,
                            "difficulty": ap.difficulty,
                            "dependencies": list(ap.dependencies),
                        }
                        for ap in report.action_plan
                    ],
                    raw_response=report.raw_response,
                    generated_at=_naive(report.generated_at),
                )
            )
            await session.commit()

    async def get_intelligence_report(self, intelligence_id: str):
        from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow

        async with self._sf() as session:
            stmt = select(IntelligenceReportRow).where(
                IntelligenceReportRow.intelligence_id == intelligence_id
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

        return self._report_from_row(row)

    async def get_intelligence_report_by_run_id(self, run_id: str):
        from sie.infrastructure.models.intelligence_orm import IntelligenceReportRow

        async with self._sf() as session:
            stmt = (
                select(IntelligenceReportRow)
                .where(IntelligenceReportRow.run_id == run_id)
                .order_by(IntelligenceReportRow.generated_at.desc())
                .limit(1)
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None

        return self._report_from_row(row)

    @staticmethod
    def _report_from_row(row):
        from sie.domain.models.intelligence import (
            ActionPlanItem,
            IntelligenceReport,
            QuickWin,
            RootCause,
            TopIssue,
        )

        root_causes = tuple(
            RootCause(
                title=rc["title"],
                evidence=tuple(rc.get("evidence", [])),
                confidence=rc.get("confidence", 0.5),
            )
            for rc in row.root_causes
        )

        top_issues = tuple(
            TopIssue(
                issue_code=ti["issue_code"],
                title=ti["title"],
                interpretation=ti["interpretation"],
                impact=ti["impact"],
                confidence=ti.get("confidence", 0.5),
                affected_url_count=ti.get("affected_url_count", 0),
            )
            for ti in row.top_issues
        )

        quick_wins = tuple(
            QuickWin(
                action=qw["action"],
                reason=qw["reason"],
                priority=qw.get("priority", "P2"),
                difficulty=qw.get("difficulty", "medium"),
            )
            for qw in row.quick_wins
        )

        action_plan = tuple(
            ActionPlanItem(
                order=ap["order"],
                action=ap["action"],
                reason=ap["reason"],
                priority=ap.get("priority", "P2"),
                difficulty=ap.get("difficulty", "medium"),
                dependencies=tuple(ap.get("dependencies", [])),
            )
            for ap in row.action_plan
        )

        return IntelligenceReport(
            intelligence_id=row.intelligence_id,
            run_id=row.run_id,
            diagnosis_run_id=row.diagnosis_run_id,
            prompt_version=row.prompt_version,
            model_name=row.model_name,
            provider=row.provider,
            summary=row.summary,
            overall_assessment=row.overall_assessment,
            root_causes=root_causes,
            top_issues=top_issues,
            quick_wins=quick_wins,
            action_plan=action_plan,
            raw_response=row.raw_response,
            generated_at=_to_aware(row.generated_at) or row.generated_at.replace(tzinfo=UTC),
        )

    # ── Search Datasets persistence (Phase 6E) ─────────────────────────────

    async def save_search_dataset(
        self,
        dataset,
        *,
        keywords=(),
        observations=(),
        competitor_rankings=(),
    ) -> None:
        from sie.infrastructure.models.search_orm import (
            SearchCompetitorRankingRow,
            SearchDatasetRow,
            SearchKeywordRow,
            SearchRankingObservationRow,
        )

        async with self._sf() as session:
            session.add(
                SearchDatasetRow(
                    id=dataset.dataset_id,
                    name=dataset.name,
                    source=dataset.source,
                    created_at=_naive(dataset.created_at),
                    total_keywords=len(keywords),
                    total_observations=len(observations),
                )
            )
            for kw in keywords:
                session.add(
                    SearchKeywordRow(
                        dataset_id=dataset.dataset_id,
                        keyword=kw.keyword,
                        normalized_keyword=kw.normalized_keyword or kw.keyword,
                        search_intent=kw.search_intent.value,
                    )
                )
            for obs in observations:
                serp_features_data = (
                    _serialize_serp_features(obs.serp_features)
                    if hasattr(obs, "serp_features")
                    else None
                )
                session.add(
                    SearchRankingObservationRow(
                        dataset_id=dataset.dataset_id,
                        keyword=obs.keyword,
                        target_url=obs.target_url,
                        position=obs.position,
                        source=obs.source,
                        search_engine=obs.search_engine,
                        country=obs.country,
                        language=obs.language,
                        device=obs.device.value,
                        observed_at=_naive(obs.observed_at),
                        serp_features=serp_features_data,
                    )
                )
            for comp in competitor_rankings:
                session.add(
                    SearchCompetitorRankingRow(
                        dataset_id=dataset.dataset_id,
                        keyword=comp.keyword,
                        competitor_domain=comp.competitor_domain,
                        competitor_url=comp.competitor_url,
                        position=comp.position,
                        observed_at=_naive(comp.observed_at),
                    )
                )
            await session.commit()

    async def get_search_dataset(self, dataset_id: str):
        from sqlalchemy.orm import selectinload

        from sie.domain.models.search import (
            CompetitorRanking,
            RankingObservation,
            SearchDataset,
            SearchDevice,
            SearchIntent,
            SearchKeyword,
        )
        from sie.domain.models.search_validation import SearchDatasetContent
        from sie.infrastructure.models.search_orm import SearchDatasetRow

        async with self._sf() as session:
            stmt = (
                select(SearchDatasetRow)
                .where(SearchDatasetRow.id == dataset_id)
                .options(
                    selectinload(SearchDatasetRow.keywords),
                    selectinload(SearchDatasetRow.observations),
                    selectinload(SearchDatasetRow.competitor_rankings),
                )
            )
            ds_row = (await session.execute(stmt)).scalar_one_or_none()
            if ds_row is None:
                return None

            keywords = tuple(
                SearchKeyword(
                    keyword=kw_row.keyword,
                    normalized_keyword=kw_row.normalized_keyword,
                    search_intent=SearchIntent(kw_row.search_intent),
                )
                for kw_row in ds_row.keywords
            )
            observations = tuple(
                RankingObservation(
                    keyword=o_row.keyword,
                    target_url=o_row.target_url,
                    position=o_row.position,
                    source=o_row.source,
                    search_engine=o_row.search_engine,
                    country=o_row.country,
                    language=o_row.language,
                    device=SearchDevice(o_row.device),
                    observed_at=_to_aware(o_row.observed_at)
                    or o_row.observed_at.replace(tzinfo=UTC),
                    serp_features=_deserialize_serp_features(o_row.serp_features),
                )
                for o_row in ds_row.observations
            )
            competitor_rankings = tuple(
                CompetitorRanking(
                    keyword=c_row.keyword,
                    competitor_domain=c_row.competitor_domain,
                    competitor_url=c_row.competitor_url,
                    position=c_row.position,
                    observed_at=_to_aware(c_row.observed_at)
                    or c_row.observed_at.replace(tzinfo=UTC),
                )
                for c_row in ds_row.competitor_rankings
            )

        dataset = SearchDataset(
            dataset_id=ds_row.id,
            name=ds_row.name,
            source=ds_row.source,
            created_at=_to_aware(ds_row.created_at) or ds_row.created_at.replace(tzinfo=UTC),
            total_keywords=len(keywords),
            total_observations=len(observations),
        )
        return dataset, SearchDatasetContent(
            keywords=keywords,
            observations=observations,
            competitor_rankings=competitor_rankings,
        )

    async def list_search_datasets(self, *, limit: int = 50, offset: int = 0):
        from sie.domain.models.search import SearchDataset
        from sie.infrastructure.models.search_orm import SearchDatasetRow

        async with self._sf() as session:
            total = (await session.execute(select(func.count(SearchDatasetRow.id)))).scalar_one()
            stmt = (
                select(SearchDatasetRow)
                .order_by(SearchDatasetRow.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).scalars().all()

        datasets = [
            SearchDataset(
                dataset_id=r.id,
                name=r.name,
                source=r.source,
                created_at=_to_aware(r.created_at) or r.created_at.replace(tzinfo=UTC),
                total_keywords=r.total_keywords,
                total_observations=r.total_observations,
            )
            for r in rows
        ]
        return total, datasets

    async def delete_search_dataset(self, dataset_id: str) -> bool:
        from sie.infrastructure.models.search_orm import SearchDatasetRow

        async with self._sf() as session:
            stmt = select(SearchDatasetRow).where(SearchDatasetRow.id == dataset_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # ── Search Observations persistence (Phase 6I) ─────────────────────────

    async def save_search_observations(self, dataset_id, observations):
        from sie.infrastructure.models.search_orm import SearchRankingObservationRow

        async with self._sf() as session:
            for obs in observations:
                session.add(
                    SearchRankingObservationRow(
                        dataset_id=dataset_id,
                        keyword=obs.keyword,
                        target_url=obs.target_url,
                        position=obs.position,
                        source=obs.source,
                        search_engine=obs.search_engine,
                        country=obs.country,
                        language=obs.language,
                        device=obs.device.value,
                        observed_at=_naive(obs.observed_at),
                    )
                )
            await session.commit()
        return len(observations)

    async def list_search_observations(self, dataset_id, *, limit=50, offset=0):
        from sie.domain.models.search import RankingObservation, SearchDevice
        from sie.infrastructure.models.search_orm import SearchRankingObservationRow

        async with self._sf() as session:
            count_stmt = select(func.count(SearchRankingObservationRow.id)).where(
                SearchRankingObservationRow.dataset_id == dataset_id
            )
            total = (await session.execute(count_stmt)).scalar_one()

            stmt = (
                select(SearchRankingObservationRow)
                .where(SearchRankingObservationRow.dataset_id == dataset_id)
                .order_by(SearchRankingObservationRow.id)
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).scalars().all()

        observations = [
            RankingObservation(
                keyword=r.keyword,
                target_url=r.target_url,
                position=r.position,
                source=r.source,
                search_engine=r.search_engine,
                country=r.country,
                language=r.language,
                device=SearchDevice(r.device),
                observed_at=_to_aware(r.observed_at) or r.observed_at.replace(tzinfo=UTC),
            )
            for r in rows
        ]
        return total, observations

    # ── AIO observation persistence ─────────────────────────────────────

    async def save_aio_observations(
        self, dataset_id: str, observations: tuple
    ) -> int:
        """Save AIO observations for a dataset. Returns count saved."""
        from sie.infrastructure.models.search_aio_geo_orm import AIOverviewObservationRow

        async with self._sf() as session:
            for obs in observations:
                citations_data = None
                if obs.citations:
                    citations_data = [
                        {
                            "domain": c.domain,
                            "url": c.url,
                            "position": c.position,
                            "source_type": c.source_type.value,
                            "title": c.title,
                        }
                        for c in obs.citations
                    ]

                session.add(
                    AIOverviewObservationRow(
                        dataset_id=dataset_id,
                        keyword=obs.keyword,
                        ai_type=obs.ai_type.value,
                        present=obs.present,
                        target_cited=obs.target_cited,
                        target_domain=obs.target_domain,
                        citation_count=obs.citation_count,
                        citations=citations_data,
                        competitor_cited_domains=list(obs.competitor_cited_domains)
                        if obs.competitor_cited_domains
                        else None,
                        observed_at=_naive(obs.observed_at),
                        source=obs.source,
                    )
                )
            await session.commit()
        return len(observations)

    async def list_aio_observations(
        self, dataset_id: str, *, limit: int = 50, offset: int = 0
    ):
        """List AIO observations for a dataset."""
        from sie.domain.models.search_aio import (
            AIOCitation,
            AIOverviewObservation,
            AIOverviewType,
            CitationSource,
        )
        from sie.infrastructure.models.search_aio_geo_orm import AIOverviewObservationRow

        async with self._sf() as session:
            count_stmt = select(func.count(AIOverviewObservationRow.id)).where(
                AIOverviewObservationRow.dataset_id == dataset_id
            )
            total = (await session.execute(count_stmt)).scalar_one()

            stmt = (
                select(AIOverviewObservationRow)
                .where(AIOverviewObservationRow.dataset_id == dataset_id)
                .order_by(AIOverviewObservationRow.id)
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).scalars().all()

        observations = []
        for r in rows:
            citations = ()
            if r.citations:
                citations = tuple(
                    AIOCitation(
                        domain=c["domain"],
                        url=c.get("url", ""),
                        position=c.get("position", 0),
                        source_type=CitationSource(c.get("source_type", "web_page")),
                        title=c.get("title", ""),
                    )
                    for c in r.citations
                )

            observations.append(
                AIOverviewObservation(
                    keyword=r.keyword,
                    ai_type=AIOverviewType(r.ai_type),
                    present=bool(r.present),
                    target_cited=bool(r.target_cited),
                    target_domain=r.target_domain,
                    citation_count=r.citation_count,
                    citations=citations,
                    competitor_cited_domains=tuple(r.competitor_cited_domains)
                    if r.competitor_cited_domains
                    else (),
                    observed_at=_to_aware(r.observed_at) or r.observed_at.replace(tzinfo=UTC),
                    source=r.source,
                )
            )
        return total, observations

    # ── GEO observation persistence ─────────────────────────────────────

    async def save_geo_observations(
        self, dataset_id: str, observations: tuple
    ) -> int:
        """Save GEO observations for a dataset. Returns count saved."""
        from sie.infrastructure.models.search_aio_geo_orm import GEOObservationRow

        async with self._sf() as session:
            for obs in observations:
                entity_data = None
                if obs.entity_mentions:
                    entity_data = [
                        {
                            "text": e.text,
                            "entity_type": e.entity_type.value,
                            "is_target": e.is_target,
                            "domain": e.domain,
                        }
                        for e in obs.entity_mentions
                    ]

                session.add(
                    GEOObservationRow(
                        dataset_id=dataset_id,
                        keyword=obs.keyword,
                        engine_type=obs.engine_type.value,
                        target_mentioned=obs.target_mentioned,
                        target_domain=obs.target_domain,
                        mention_count=obs.mention_count,
                        entity_mentions=entity_data,
                        competitor_domains=list(obs.competitor_domains)
                        if obs.competitor_domains
                        else None,
                        citation_urls=list(obs.citation_urls)
                        if obs.citation_urls
                        else None,
                        answer_length=obs.answer_length,
                        observed_at=_naive(obs.observed_at),
                        source=obs.source,
                    )
                )
            await session.commit()
        return len(observations)

    async def list_geo_observations(
        self, dataset_id: str, *, limit: int = 50, offset: int = 0
    ):
        """List GEO observations for a dataset."""
        from sie.domain.models.search_geo import (
            EntityMention,
            EntityType,
            GenerativeEngineType,
            GEOObservation,
        )
        from sie.infrastructure.models.search_aio_geo_orm import GEOObservationRow

        async with self._sf() as session:
            count_stmt = select(func.count(GEOObservationRow.id)).where(
                GEOObservationRow.dataset_id == dataset_id
            )
            total = (await session.execute(count_stmt)).scalar_one()

            stmt = (
                select(GEOObservationRow)
                .where(GEOObservationRow.dataset_id == dataset_id)
                .order_by(GEOObservationRow.id)
                .limit(limit)
                .offset(offset)
            )
            rows = (await session.execute(stmt)).scalars().all()

        observations = []
        for r in rows:
            entity_mentions = ()
            if r.entity_mentions:
                entity_mentions = tuple(
                    EntityMention(
                        text=e["text"],
                        entity_type=EntityType(e.get("entity_type", "other")),
                        is_target=e.get("is_target", False),
                        domain=e.get("domain", ""),
                    )
                    for e in r.entity_mentions
                )

            observations.append(
                GEOObservation(
                    keyword=r.keyword,
                    engine_type=GenerativeEngineType(r.engine_type),
                    target_mentioned=bool(r.target_mentioned),
                    target_domain=r.target_domain,
                    mention_count=r.mention_count,
                    entity_mentions=entity_mentions,
                    competitor_domains=tuple(r.competitor_domains)
                    if r.competitor_domains
                    else (),
                    citation_urls=tuple(r.citation_urls)
                    if r.citation_urls
                    else (),
                    answer_length=r.answer_length,
                    observed_at=_to_aware(r.observed_at) or r.observed_at.replace(tzinfo=UTC),
                    source=r.source,
                )
            )
        return total, observations
