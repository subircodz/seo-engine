"""CrUX (Chrome User Experience Report) integration for real-user Core Web Vitals."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import httpx

from sie.logging import get_logger

if TYPE_CHECKING:
    from sie.domain.models.site_analysis import SiteCoreWebVitalsAnalysis

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CruxMetrics:
    """Real-user Core Web Vitals from CrUX API."""

    origin: str
    lcp_p75: int  # milliseconds
    fid_p75: int  # milliseconds
    cls_p75: float  # 0.001 units
    inp_p75: int  # milliseconds
    ttfb_p75: int  # milliseconds
    lcp_good: float  # percentage
    fid_good: float
    cls_good: float
    inp_good: float
    lcp_poor: float
    fid_poor: float
    cls_poor: float
    url_level_lcp: int | None = None
    url_level_fid: int | None = None
    url_level_cls: float | None = None
    url_level_inp: int | None = None
    url_level_ttfb: int | None = None
    form_factor: str = "PHONE"  # PHONE, DESKTOP, TABLET
    effective_date: str | None = None  # YYYYMMDD


@dataclass(frozen=True, slots=True)
class CruxResponse:
    """CrUX API response."""

    record: CruxMetrics | None = None
    error: str | None = None
    success: bool = False


class CruxService:
    """Service for fetching real-user Core Web Vitals from CrUX API."""

    CRUX_API_URL = "https://chromeuxreport.googleapis.com/v1/records:queryRecord"
    CRUX_HISTORY_URL = "https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord"

    def __init__(
        self,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        form_factor: str = "PHONE",
    ) -> None:
        self._api_key = api_key or os.getenv("CRUX_API_KEY")
        self._timeout_seconds = timeout_seconds
        self._form_factor = form_factor.upper()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    def _build_url(self, url: str) -> str:
        """Normalize URL to origin for CrUX API."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin

    async def query_origin(
        self,
        url: str,
        form_factor: str | None = None,
    ) -> CruxResponse:
        """Query CrUX for origin-level metrics."""
        if not self._api_key:
            return CruxResponse(error="CRUX_API_KEY not configured", success=False)

        origin = self._build_url(url)
        client = await self._get_client()

        # Use instance form_factor if not explicitly provided
        ff = (form_factor or self._form_factor).upper()

        payload = {
            "origin": origin,
            "formFactor": ff,
        }

        try:
            response = await client.post(
                f"{self.CRUX_API_URL}?key={self._api_key}",
                json=payload,
            )

            if response.status_code == 404:
                return CruxResponse(error=f"No CrUX data for {origin}", success=False)
            if response.status_code != 200:
                return CruxResponse(error=f"CrUX API error: {response.status_code}", success=False)

            data = response.json()
            record = self._parse_record(data, origin, ff)
            return CruxResponse(record=record, success=True)

        except httpx.TimeoutException:
            return CruxResponse(error="CrUX API timeout", success=False)
        except httpx.HTTPError as e:
            return CruxResponse(error=f"CrUX API error: {e}", success=False)
        except Exception as e:
            logger.warning("CrUX query failed: %s", e)
            return CruxResponse(error=str(e), success=False)

    async def query_url(
        self,
        url: str,
        form_factor: str | None = None,
    ) -> CruxResponse:
        """Query CrUX for URL-level metrics."""
        if not self._api_key:
            return CruxResponse(error="CRUX_API_KEY not configured", success=False)

        client = await self._get_client()

        ff = (form_factor or self._form_factor).upper()

        payload = {
            "url": url,
            "formFactor": ff,
        }

        try:
            response = await client.post(
                f"{self.CRUX_API_URL}?key={self._api_key}",
                json=payload,
            )

            if response.status_code == 404:
                return CruxResponse(error=f"No CrUX data for {url}", success=False)
            if response.status_code != 200:
                return CruxResponse(error=f"CrUX API error: {response.status_code}", success=False)

            data = response.json()
            record = self._parse_record(data, self._build_url(url), ff, url=url)
            return CruxResponse(record=record, success=True)

        except httpx.TimeoutException:
            return CruxResponse(error="CrUX API timeout", success=False)
        except httpx.HTTPError as e:
            return CruxResponse(error=f"CrUX API error: {e}", success=False)
        except Exception as e:
            logger.warning("CrUX URL query failed: %s", e)
            return CruxResponse(error=str(e), success=False)

    async def query_history(
        self,
        url: str,
        form_factor: str | None = None,
    ) -> list[CruxMetrics]:
        """Get historical CrUX data for trend analysis."""
        if not self._api_key:
            return []

        origin = self._build_url(url)
        client = await self._get_client()

        ff = (form_factor or self._form_factor).upper()

        payload = {
            "origin": origin,
            "formFactor": ff,
        }

        try:
            response = await client.post(
                f"{self.CRUX_HISTORY_URL}?key={self._api_key}",
                json=payload,
            )

            if response.status_code != 200:
                return []

            data = response.json()
            records = []
            for record_data in data.get("records", []):
                record = self._parse_record(record_data, origin, ff)
                if record:
                    records.append(record)
            return records

        except Exception as e:
            logger.warning("CrUX history query failed: %s", e)
            return []

    def _parse_record(
        self,
        data: dict,
        origin: str,
        form_factor: str,
        url: str | None = None,
    ) -> CruxMetrics | None:
        """Parse CrUX API record into CruxMetrics."""
        try:
            record = data.get("record", {})
            metrics = record.get("metrics", {})

            def get_p75(metric_name: str) -> int:
                metric = metrics.get(metric_name, {})
                histogram = metric.get("histogram", [])
                if histogram:
                    # Find p75 bucket
                    cumulative = 0
                    for bucket in histogram:
                        cumulative += bucket.get("density", 0)
                        if cumulative >= 0.75:
                            return int(bucket.get("start", 0))
                return 0

            def get_percentile(metric_name: str, threshold: float) -> float:
                """Get percentage of users meeting threshold."""
                metric = metrics.get(metric_name, {})
                histogram = metric.get("histogram", [])
                total = sum(b.get("density", 0) for b in histogram)
                if total == 0:
                    return 0.0
                good = sum(
                    b.get("density", 0) for b in histogram if int(b.get("start", 0)) <= threshold
                )
                return (good / total) * 100

            lcp_p75 = get_p75("largest_contentful_paint")
            fid_p75 = get_p75("first_input_delay")
            cls_p75 = int(get_p75("cumulative_layout_shift") * 1000)  # Convert to 0.001 units
            inp_p75 = get_p75("interaction_to_next_paint")
            ttfb_p75 = get_p75("experimental_time_to_first_byte")

            lcp_good = get_percentile("largest_contentful_paint", 2500)
            fid_good = get_percentile("first_input_delay", 100)
            cls_good = get_percentile("cumulative_layout_shift", 0.1)
            inp_good = get_percentile("interaction_to_next_paint", 200)

            lcp_poor = get_percentile("largest_contentful_paint", 4000)
            fid_poor = get_percentile("first_input_delay", 300)
            cls_poor = get_percentile("cumulative_layout_shift", 0.25)

            effective_date = record.get("collectionPeriod", {}).get("lastDate")

            return CruxMetrics(
                origin=origin,
                lcp_p75=lcp_p75,
                fid_p75=fid_p75,
                cls_p75=cls_p75 / 1000.0,
                inp_p75=inp_p75,
                ttfb_p75=ttfb_p75,
                lcp_good=lcp_good,
                fid_good=fid_good,
                cls_good=cls_good,
                inp_good=inp_good,
                lcp_poor=lcp_poor,
                fid_poor=fid_poor,
                cls_poor=cls_poor,
                form_factor=form_factor,
                effective_date=effective_date,
            )

        except Exception as e:
            logger.warning("Failed to parse CrUX record: %s", e)
            return None

    def merge_into_cwv_analysis(
        self,
        cwv: SiteCoreWebVitalsAnalysis,
        crux: CruxMetrics,
    ) -> SiteCoreWebVitalsAnalysis:
        """Merge CrUX real-user data into lab CWV analysis."""
        if not crux:
            return cwv

        # Override lab estimates with real-user data where available
        lcp_estimate = crux.lcp_p75
        fid_estimate = crux.fid_p75
        cls_estimate = crux.cls_p75
        ttfb_estimate = crux.ttfb_p75

        # Recalculate issues with real data
        lcp_issues = []
        if lcp_estimate > 2500:
            lcp_issues.append({"url": "origin", "lcp_ms": lcp_estimate, "threshold": 2500})

        fid_issues = []
        if fid_estimate > 100:
            fid_issues.append({"url": "origin", "fid_ms": fid_estimate, "threshold": 100})

        cls_issues = []
        if cls_estimate > 0.1:
            cls_issues.append({"url": "origin", "cls": cls_estimate, "threshold": 0.1})

        # Update score based on real-user data
        passing = 0
        total = 0
        if lcp_estimate <= 2500:
            passing += 1
        total += 1
        if fid_estimate <= 100:
            passing += 1
        total += 1
        if cls_estimate <= 0.1:
            passing += 1
        total += 1
        if crux.inp_p75 <= 200:
            passing += 1
        total += 1

        score = (passing / total) * 100 if total > 0 else 0

        return SiteCoreWebVitalsAnalysis(
            lcp_estimate_ms=lcp_estimate,
            fid_estimate_ms=fid_estimate,
            cls_estimate=cls_estimate,
            fcp_estimate_ms=cwv.fcp_estimate_ms,  # Keep lab FCP
            ttfb_estimate_ms=ttfb_estimate,
            pages_passing_cwv=passing,
            pages_failing_cwv=total - passing,
            lcp_issues=lcp_issues,
            fid_issues=fid_issues,
            cls_issues=cls_issues,
            resource_hints_missing=cwv.resource_hints_missing,
            recommendations=cwv.recommendations
            + (
                [
                    f"CrUX: LCP p75={lcp_estimate}ms (good: {crux.lcp_good:.1f}%)",
                    f"CrUX: INP p75={crux.inp_p75}ms (good: {crux.inp_good:.1f}%)",
                    f"CrUX: CLS p75={cls_estimate:.3f} (good: {crux.cls_good:.1f}%)",
                ]
                if crux
                else []
            ),
            score=score,
        )

    # Convenience function for easy integration


async def fetch_crux_data(
    url: str,
    api_key: str | None = None,
    form_factor: str = "PHONE",
) -> CruxResponse:
    """Fetch CrUX data for a URL."""
    async with CruxService(api_key=api_key) as service:
        return await service.query_origin(url, form_factor)
