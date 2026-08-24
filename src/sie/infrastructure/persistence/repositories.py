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

    def _links_to_dict(self, l) -> dict:
        return {
            "internal_links": l.internal_links,
            "external_links": l.external_links,
            "nofollow_links": l.nofollow_links,
            "internal_link_ratio": l.internal_link_ratio,
            "external_domains": l.external_domains,
            "anchor_texts": list(l.anchor_texts),
            "empty_anchors": l.empty_anchors,
            "generic_anchors": l.generic_anchors,
            "keyword_rich_anchors": l.keyword_rich_anchors,
            "anchor_diversity": l.anchor_diversity,
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
