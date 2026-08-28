from __future__ import annotations

import pytest

from sie.domain.intelligence.forecasting import LinearTrendForecaster
from sie.infrastructure.search.quota_tracker import QuotaExceeded, QuotaTracker


def test_quota_tracker_counts_failed_requests_once() -> None:
    quota = QuotaTracker("serpapi", cost_per_request_usd=0.005, monthly_request_limit=2)
    quota.record_request(success=False)
    quota.record_request(success=True)
    assert quota.total_requests == 2
    assert quota.failed_requests == 1
    assert quota.successful_requests == 1
    assert quota.estimated_cost_usd == pytest.approx(0.01)
    with pytest.raises(QuotaExceeded):
        quota.record_request(success=True)


def test_forecaster_requires_real_history() -> None:
    model = LinearTrendForecaster(min_samples=7)
    result = model.fit([1, 2, 3])
    assert result.status == "INSUFFICIENT_DATA"
    assert result.predicted_values == ()


def test_forecaster_fits_real_trend() -> None:
    model = LinearTrendForecaster(min_samples=7)
    fitted = model.fit([10, 12, 14, 16, 18, 20, 22])
    assert fitted.status == "TRAINED"
    assert fitted.slope == pytest.approx(2.0)
    forecast = model.predict(2)
    assert forecast.status == "PREDICTED"
    assert forecast.predicted_values == pytest.approx((24.0, 26.0))
