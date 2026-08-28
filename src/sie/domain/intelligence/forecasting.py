"""Small, dependency-free time-series forecasting primitive.

This is intentionally a transparent baseline model, not a claim of a trained
production ML system. It requires real historical observations and reports
whether there is enough data to forecast.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

__all__ = ["ForecastResult", "LinearTrendForecaster"]


@dataclass(frozen=True, slots=True)
class ForecastResult:
    status: str
    predicted_values: tuple[float, ...]
    slope: float | None
    intercept: float | None
    rmse: float | None
    sample_size: int
    confidence: str
    limitations: tuple[str, ...] = ()


class LinearTrendForecaster:
    """Fit an ordinary least-squares linear trend to real observations."""

    def __init__(self, *, min_samples: int = 7) -> None:
        self._min_samples = min_samples
        self._slope: float | None = None
        self._intercept: float | None = None
        self._rmse: float | None = None
        self._n = 0

    def fit(self, values: list[float] | tuple[float, ...]) -> ForecastResult:
        clean = [float(v) for v in values]
        self._n = len(clean)
        if self._n < self._min_samples:
            self._slope = self._intercept = self._rmse = None
            return ForecastResult(
                status="INSUFFICIENT_DATA",
                predicted_values=(),
                slope=None,
                intercept=None,
                rmse=None,
                sample_size=self._n,
                confidence="UNABLE TO VERIFY",
                limitations=(
                    f"At least {self._min_samples} historical observations are required.",
                ),
            )
        xs = list(range(self._n))
        x_mean = sum(xs) / self._n
        y_mean = sum(clean) / self._n
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = (
            sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, clean, strict=True)) / denominator
        )
        intercept = y_mean - slope * x_mean
        residuals = [y - (intercept + slope * x) for x, y in zip(xs, clean, strict=True)]
        rmse = sqrt(sum(r * r for r in residuals) / self._n)
        self._slope, self._intercept, self._rmse = slope, intercept, rmse
        confidence = "HIGH" if self._n >= 30 else "MEDIUM" if self._n >= 14 else "LOW"
        return ForecastResult(
            status="TRAINED",
            predicted_values=(),
            slope=slope,
            intercept=intercept,
            rmse=rmse,
            sample_size=self._n,
            confidence=confidence,
            limitations=(
                "Linear trend does not model seasonality, algorithm updates, or causal effects.",
            ),
        )

    def predict(self, periods: int) -> ForecastResult:
        if self._slope is None or self._intercept is None or periods < 1:
            return ForecastResult(
                status="NOT_TRAINED",
                predicted_values=(),
                slope=self._slope,
                intercept=self._intercept,
                rmse=self._rmse,
                sample_size=self._n,
                confidence="UNABLE TO VERIFY",
                limitations=(
                    "Fit the forecaster with real historical observations before predicting.",
                ),
            )
        start = self._n
        predictions = tuple(
            max(0.0, self._intercept + self._slope * (start + i)) for i in range(periods)
        )
        confidence = "HIGH" if self._n >= 30 else "MEDIUM" if self._n >= 14 else "LOW"
        return ForecastResult(
            status="PREDICTED",
            predicted_values=predictions,
            slope=self._slope,
            intercept=self._intercept,
            rmse=self._rmse,
            sample_size=self._n,
            confidence=confidence,
            limitations=(
                "Forecast is a statistical trend baseline; "
                "it is not a guaranteed ranking or traffic prediction.",
            ),
        )
