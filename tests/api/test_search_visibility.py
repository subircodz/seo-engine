from types import SimpleNamespace

from sie.api.routes.search_visibility import _assessment, _seo_assessment
from sie.domain.models.search_surface import SearchSurface, SurfaceStatus


def _breakdown(score, status="ASSESSED"):
    return SimpleNamespace(
        overall_score=score,
        score_status=status,
        scoring_methodology="test methodology",
        sample_size=10,
        data_source="test",
        observation_date=None,
        limitations=[],
    )


def test_unassessed_aio_has_no_numeric_score():
    assessment = _assessment(SearchSurface.AIO, _breakdown(None, "NOT ASSESSED"), "aio")
    assert assessment.status == SurfaceStatus.NOT_ASSESSED
    assert assessment.score is None


def test_assessed_aio_preserves_real_zero():
    assessment = _assessment(SearchSurface.AIO, _breakdown(0.0), "aio")
    assert assessment.status == SurfaceStatus.ASSESSED
    assert assessment.score == 0.0


def test_seo_is_derived_from_assessed_traditional_categories_only():
    result = SimpleNamespace(
        technical_breakdown=_breakdown(80.0),
        content_breakdown=_breakdown(60.0),
        ranking_breakdown=_breakdown(None, "NOT ASSESSED"),
        architecture_breakdown=_breakdown(100.0),
    )
    assessment = _seo_assessment(result)
    assert assessment.status == SurfaceStatus.ASSESSED
    assert assessment.score == 80.0


def test_seo_is_unavailable_when_no_category_is_assessed():
    result = SimpleNamespace(
        technical_breakdown=_breakdown(None, "NOT ASSESSED"),
        content_breakdown=_breakdown(None, "INSUFFICIENT DATA"),
        ranking_breakdown=None,
        architecture_breakdown=None,
    )
    assessment = _seo_assessment(result)
    assert assessment.status == SurfaceStatus.INSUFFICIENT_DATA
    assert assessment.score is None
