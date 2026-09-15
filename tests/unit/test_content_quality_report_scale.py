from unittest.mock import MagicMock

import pytest

from sie.domain.models.content import QualityTier
from sie.domain.services.content_service import ContentService


@pytest.mark.asyncio
async def test_quality_report_normalizes_metric_percentage_to_unit_score() -> None:
    metric = MagicMock()
    metric.url = "https://example.com/"
    metric.quality_score = 75.0
    metric.quality_tier = QualityTier.GOOD
    metric.thin_content = False
    metric.headings.h1_count = 1
    metric.images.missing_alt_percentage = 0
    metric.links.internal_links = 3
    metric.readability.flesch_reading_ease = 60
    metric.keywords.keyword_stuffing_score = 0.0
    metric.freshness.is_stale = False
    metric.structured_data.has_schema_org = True

    service = ContentService(repository=MagicMock(), parser=MagicMock())

    report = await service.generate_quality_report("run-1", [metric])

    assert report.avg_quality_score == pytest.approx(0.75)
