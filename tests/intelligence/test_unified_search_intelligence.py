"""Tests for the first-class SEO/AIO/GEO visibility facade."""

from types import SimpleNamespace

import pytest

from sie.domain.models.search_surface import SearchSurface, SurfaceStatus
from sie.domain.services.unified_search_intelligence import UnifiedSearchIntelligenceService


def _search_result(total_keywords: int = 10, visibility_score: float = 0.6):
    return SimpleNamespace(
        analytics=SimpleNamespace(
            dataset_metrics=SimpleNamespace(
                total_keywords=total_keywords,
                visibility_score=visibility_score,
            )
        )
    )


def _aio_result(total_observations: int = 5, citation_rate: float = 0.4):
    return SimpleNamespace(
        dataset_metrics=SimpleNamespace(
            total_ai_overview_observations=total_observations,
            target_citation_rate=citation_rate,
        )
    )


def _geo_result(total_observations: int = 5, mention_rate: float = 0.2):
    return SimpleNamespace(
        dataset_metrics=SimpleNamespace(
            total_observations=total_observations,
            overall_mention_rate=mention_rate,
        )
    )


def test_all_three_surfaces_are_first_class_and_assessed() -> None:
    result = UnifiedSearchIntelligenceService().build_visibility(
        _search_result(),
        aio_result=_aio_result(),
        geo_result=_geo_result(),
    )

    assert {assessment.surface for assessment in result.assessments} == {
        SearchSurface.SEO,
        SearchSurface.AIO,
        SearchSurface.GEO,
    }
    assert all(assessment.status == SurfaceStatus.ASSESSED for assessment in result.assessments)
    assert result.aggregate_score == pytest.approx(40.0)


def test_unavailable_aio_and_geo_are_not_scored_as_zero() -> None:
    result = UnifiedSearchIntelligenceService().build_visibility(_search_result())

    seo, aio, geo = result.assessments
    assert seo.score == 60.0
    assert seo.status == SurfaceStatus.ASSESSED
    assert aio.score is None
    assert aio.status == SurfaceStatus.NOT_ASSESSED
    assert geo.score is None
    assert geo.status == SurfaceStatus.NOT_ASSESSED
    assert result.aggregate_score == 60.0


def test_zero_aio_score_is_distinct_from_unavailable() -> None:
    result = UnifiedSearchIntelligenceService().build_visibility(
        _search_result(),
        aio_result=_aio_result(total_observations=3, citation_rate=0.0),
    )

    aio = next(a for a in result.assessments if a.surface == SearchSurface.AIO)
    assert aio.status == SurfaceStatus.ASSESSED
    assert aio.score == 0.0
    assert result.aggregate_score == 30.0


def test_unified_visibility_requires_all_three_surface_assessments() -> None:
    from sie.domain.models.search_surface import SurfaceAssessment, UnifiedSearchVisibility

    with pytest.raises(ValueError, match="requires SEO, AIO, and GEO"):
        UnifiedSearchVisibility(
            assessments=(
                SurfaceAssessment(
                    surface=SearchSurface.SEO,
                    status=SurfaceStatus.ASSESSED,
                    score=50.0,
                    score_basis="test",
                    observation_count=1,
                    data_source="test",
                ),
            ),
            aggregate_score=50.0,
            aggregate_methodology="test",
            generated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
