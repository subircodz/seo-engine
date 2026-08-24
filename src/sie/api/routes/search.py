"""Search Intelligence API endpoints — import, validate, normalize datasets."""

from __future__ import annotations

import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, UploadFile
from fastapi.exceptions import HTTPException
from pydantic import BaseModel, Field

from sie.domain.models.search import SearchDataset
from sie.domain.models.search_import import SearchImportResult
from sie.domain.models.search_validation import (
    DatasetValidationResult,
    SearchDatasetContent,
)
from sie.domain.services.search_dataset_service import SearchDatasetService
from sie.domain.services.search_import_service import SearchImportService

router = APIRouter(prefix="/api/search", tags=["search"])

importer = SearchImportService()
dataset_svc = SearchDatasetService()

_DEFAULT_DATASET_NAME = "api-import"
_DEFAULT_DATASET_ID_PREFIX = "ds"


def _make_dataset_id() -> str:
    return f"{_DEFAULT_DATASET_ID_PREFIX}-{uuid.uuid4().hex[:12]}"


# ── request / response models ─────────────────────────────────────────────


class SearchRecordErrorResponse(BaseModel):
    row_index: int
    reason: str
    field: str = ""
    raw_record: dict[str, object] | None = None


class SearchImportResponse(BaseModel):
    total_rows: int
    successful_rows: int
    rejected_rows: int
    has_errors: bool
    keywords_count: int
    observations_count: int
    competitor_rankings_count: int
    validation_errors: list[SearchRecordErrorResponse]


class ValidationIssueResponse(BaseModel):
    code: str
    severity: str
    message: str
    keyword: str | None = None
    url: str | None = None


class ValidateResponse(BaseModel):
    valid: bool
    total_records: int
    issue_count: int
    issues: list[ValidationIssueResponse]


class NormalizationResponse(BaseModel):
    dataset_id: str
    name: str
    source: str
    total_keywords: int
    total_observations: int
    keyword_deduplicated: bool
    observation_deduplicated: bool
    competitor_deduplicated: bool


class DatasetRequest(BaseModel):
    records: list[dict[str, object]] = Field(
        description="JSON array of search records to import, validate, or normalize"
    )
    dataset_id: str | None = Field(default=None, description="Optional dataset identifier")
    name: str = Field(default=_DEFAULT_DATASET_NAME, description="Human-readable dataset name")
    source: str = Field(default="api-import", description="Data provenance label")


# ── helpers ───────────────────────────────────────────────────────────────


def _import_result_to_response(result: SearchImportResult) -> SearchImportResponse:
    return SearchImportResponse(
        total_rows=result.total_rows,
        successful_rows=result.successful_rows,
        rejected_rows=result.rejected_rows,
        has_errors=result.has_errors,
        keywords_count=len(result.keywords),
        observations_count=len(result.observations),
        competitor_rankings_count=len(result.competitor_rankings),
        validation_errors=[
            SearchRecordErrorResponse(
                row_index=e.row_index,
                reason=e.reason,
                field=e.field,
                raw_record=dict(e.raw_record) if e.raw_record is not None else None,
            )
            for e in result.errors
        ],
    )


def _validation_result_to_response(result: DatasetValidationResult) -> ValidateResponse:
    return ValidateResponse(
        valid=result.valid,
        total_records=result.total_records,
        issue_count=result.issue_count,
        issues=[
            ValidationIssueResponse(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
                keyword=issue.keyword,
                url=issue.url,
            )
            for issue in result.issues
        ],
    )


def _import_and_build_content(
    records: list[dict[str, object]],
    *,
    source: str,
) -> tuple[SearchImportResult, SearchDatasetContent]:
    """Import JSON records and build the dataset content bundle."""
    result = importer.import_json(json.dumps(records), source=source)
    content = dataset_svc.content_from_import_result(result)
    return result, content


def _build_dataset(
    result: SearchImportResult,
    *,
    dataset_id: str | None,
    name: str,
) -> SearchDataset:

    return SearchDataset(
        dataset_id=dataset_id or _make_dataset_id(),
        name=name,
        source="api-import",
        total_keywords=len(result.keywords),
        total_observations=len(result.observations),
    )


# ── CSV import ────────────────────────────────────────────────────────────


@router.post("/import/csv", response_model=SearchImportResponse)
async def import_csv(
    file: UploadFile,
    source: str = "csv-upload",
) -> SearchImportResponse:
    """Import search-ranking data from a CSV file upload."""
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}") from exc
    result = importer.import_csv(content, source=source)
    return _import_result_to_response(result)


@router.post("/import/csv/text", response_model=SearchImportResponse)
async def import_csv_text(
    body: Annotated[str, Body(media_type="text/csv")],
    source: str = "csv-text",
) -> SearchImportResponse:
    """Import search-ranking data from raw CSV text in the request body."""
    result = importer.import_csv(body, source=source)
    return _import_result_to_response(result)


# ── JSON import ───────────────────────────────────────────────────────────


@router.post("/import/json", response_model=SearchImportResponse)
async def import_json(
    body: Annotated[list[dict[str, object]] | dict[str, object], Body()],
    source: str = "json-upload",
) -> SearchImportResponse:
    """Import search-ranking data from a JSON array or single record object."""
    if isinstance(body, dict):
        body = [body]
    result = importer.import_json(json.dumps(body), source=source)
    return _import_result_to_response(result)


# ── validate ──────────────────────────────────────────────────────────────


@router.post("/validate", response_model=ValidateResponse)
async def validate_dataset(
    body: DatasetRequest,
) -> ValidateResponse:
    """Validate imported search records for consistency and correctness."""
    if not body.records:
        raise HTTPException(status_code=422, detail="records list must not be empty")
    import_result, _content = _import_and_build_content(body.records, source=body.source)
    if import_result.has_errors and not import_result.keywords and not import_result.observations:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "All records failed to import",
                "errors": [
                    {"row_index": e.row_index, "reason": e.reason, "field": e.field}
                    for e in import_result.errors
                ],
            },
        )
    dataset = _build_dataset(
        import_result,
        dataset_id=body.dataset_id,
        name=body.name,
    )
    result = dataset_svc.validate_dataset(
        dataset,
        keywords=import_result.keywords,
        observations=import_result.observations,
        competitor_rankings=import_result.competitor_rankings,
    )
    return _validation_result_to_response(result)


# ── normalize ─────────────────────────────────────────────────────────────


@router.post("/normalize", response_model=NormalizationResponse)
async def normalize_dataset(
    body: DatasetRequest,
) -> NormalizationResponse:
    """Normalize imported search records: deduplicate and stabilize ordering."""
    if not body.records:
        raise HTTPException(status_code=422, detail="records list must not be empty")
    import_result, content = _import_and_build_content(body.records, source=body.source)
    if import_result.has_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Records contain import errors; fix input before normalizing",
                "error_count": import_result.rejected_rows,
                "errors": [
                    {"row_index": e.row_index, "reason": e.reason, "field": e.field}
                    for e in import_result.errors
                ],
            },
        )
    dataset = _build_dataset(
        import_result,
        dataset_id=body.dataset_id,
        name=body.name,
    )
    normalized_obs_count = len(content.observations)
    normalized_comp_count = len(content.competitor_rankings)

    normalized_dataset = dataset_svc.normalize_dataset(
        dataset,
        keywords=content.keywords,
        observations=content.observations,
        competitor_rankings=content.competitor_rankings,
    )
    normalized_content = dataset_svc.normalize_content(content)
    competitor_count = len(normalized_content.competitor_rankings)
    return NormalizationResponse(
        dataset_id=normalized_dataset.dataset_id,
        name=normalized_dataset.name,
        source=normalized_dataset.source,
        total_keywords=normalized_dataset.total_keywords,
        total_observations=normalized_dataset.total_observations,
        keyword_deduplicated=len(content.keywords) != len(normalized_content.keywords),
        observation_deduplicated=normalized_obs_count != len(normalized_content.observations),
        competitor_deduplicated=normalized_comp_count != competitor_count,
    )
