"""Search Data Importer — deterministic CSV/JSON → Phase 6A domain models.

Converts externally supplied search-ranking data into validated
``SearchKeyword`` / ``RankingObservation`` / ``CompetitorRanking`` objects.

Guarantees:

- Deterministic: no network, no LLM, no persistence, no invented values.
  Positions and competitor rankings are taken verbatim from the input or not
  at all.
- All-or-nothing per row: a record is either fully imported or reported in
  ``SearchImportResult.errors`` — malformed data is never silently dropped.
- Keyword normalization reuses the Phase 6A model behaviour (casefold +
  whitespace collapse) by delegating to the domain models themselves.

The full intent classifier is out of scope; ``SearchKeyword.search_intent``
stays at the existing ``UNKNOWN`` default.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDevice,
    SearchKeyword,
)
from sie.domain.models.search_import import SearchImportResult, SearchRecordError

__all__ = ["DEFAULT_IMPORT_SOURCE", "SearchImportService"]

DEFAULT_IMPORT_SOURCE = "search-import"

_REQUIRED_STRING_FIELDS = ("keyword", "target_url")
_OPTIONAL_FIELDS = ("search_engine", "country", "language", "source", "device", "observed_at")

_INT_RE = re.compile(r"[+-]?\d+")
_FLOAT_RE = re.compile(r"[+-]?(\d+\.\d*|\.\d+|\d+(\.\d*)?[eE][+-]?\d+)")

# csv.DictReader restkey used to park surplus cells; never treated as a field.
_EXTRA_CELLS_KEY = "__extra_cells__"

# Sentinel returned by row helpers when validation fails.
_RowResult = tuple[SearchKeyword, RankingObservation, CompetitorRanking | None] | SearchRecordError


def _has_value(value: Any) -> bool:
    """A field counts as supplied when present with any non-blank content."""
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None


def _decode(content: str | bytes) -> str:
    if isinstance(content, bytes):
        return content.decode("utf-8-sig")
    if isinstance(content, str):
        return content
    raise TypeError("content must be str or bytes")


def _file_failure(reason: str) -> SearchImportResult:
    return SearchImportResult(errors=(SearchRecordError(row_index=-1, reason=reason),))


def _iso_datetime(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO 8601 timestamp, got {value.strip()!r}"
        ) from exc


class SearchImportService:
    """Imports externally supplied CSV/JSON ranking data into domain models."""

    def import_csv(
        self, content: str | bytes, *, source: str = DEFAULT_IMPORT_SOURCE
    ) -> SearchImportResult:
        """Parse CSV text and convert rows into validated domain objects.

        The first row is the header and must contain at least ``keyword``,
        ``target_url``, and ``position`` columns.  A row-level ``source`` cell
        overrides the ``source`` argument for that row.
        """
        text = _decode(content)
        try:
            reader = csv.DictReader(io.StringIO(text), restkey=_EXTRA_CELLS_KEY, strict=True)
            rows: list[dict[str, Any]] = list(reader)
        except csv.Error as exc:
            return _file_failure(f"malformed CSV: {exc}")

        if not reader.fieldnames:
            return SearchImportResult()
        fieldnames = [str(fn).strip() for fn in reader.fieldnames]
        missing = [name for name in ("keyword", "target_url", "position") if name not in fieldnames]
        if missing:
            return _file_failure(f"missing required columns: {', '.join(missing)}")

        normalized_rows = [
            {str(key).strip(): value for key, value in row.items() if key is not None}
            for row in rows
        ]
        return self._process_rows(normalized_rows, source=source)

    def import_json(
        self, content: str | bytes, *, source: str = DEFAULT_IMPORT_SOURCE
    ) -> SearchImportResult:
        """Parse JSON text (an array of records, or a single record object)."""
        text = _decode(content)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return _file_failure(f"malformed JSON: {exc}")

        if isinstance(payload, dict):
            payload = [payload]
        if not isinstance(payload, list):
            return _file_failure(
                f"JSON payload must be an array of records, got {type(payload).__name__}"
            )

        rows: list[dict[str, Any]] = []
        pre_errors: list[SearchRecordError] = []
        for index, item in enumerate(payload):
            if isinstance(item, dict):
                rows.append(item)
            else:
                pre_errors.append(
                    SearchRecordError(
                        row_index=index,
                        reason=f"record must be an object, got {type(item).__name__}",
                    )
                )
        return self._process_rows(
            rows, source=source, pre_errors=pre_errors, total_rows=len(payload)
        )

    # ══════════════════════════════════════════════════════════════════════
    # Row pipeline
    # ══════════════════════════════════════════════════════════════════════

    def _process_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        source: str,
        pre_errors: list[SearchRecordError] | None = None,
        total_rows: int | None = None,
    ) -> SearchImportResult:
        keywords_by_normalized: dict[str, SearchKeyword] = {}
        observations: list[RankingObservation] = []
        competitors: list[CompetitorRanking] = []
        errors = list(pre_errors or [])

        for index, raw in enumerate(rows):
            converted = self._convert_row(index, raw, source=source)
            if isinstance(converted, SearchRecordError):
                errors.append(converted)
                continue
            keyword, observation, competitor = converted
            keywords_by_normalized.setdefault(observation.keyword, keyword)
            observations.append(observation)
            if competitor is not None:
                competitors.append(competitor)

        return SearchImportResult(
            keywords=tuple(keywords_by_normalized.values()),
            observations=tuple(observations),
            competitor_rankings=tuple(competitors),
            errors=tuple(errors),
            total_rows=len(rows) if total_rows is None else total_rows,
        )

    def _convert_row(
        self,
        index: int,
        raw: dict[str, Any],
        *,
        source: str,
    ) -> _RowResult:
        for name in _REQUIRED_STRING_FIELDS:
            error = _check_required_string(index, raw, name)
            if error is not None:
                return error

        position_or_error = _check_position(index, raw)
        if isinstance(position_or_error, SearchRecordError):
            return position_or_error
        position: int = position_or_error
        if position < 1:
            return SearchRecordError(
                row_index=index,
                field="position",
                reason=f"position must be >= 1, got {position}",
                raw_record=dict(raw),
            )

        url_error = _check_target_url(index, raw)
        if url_error is not None:
            return url_error

        optionals: dict[str, str | None] = {}
        for name in _OPTIONAL_FIELDS:
            value = raw.get(name)
            if value is None or (isinstance(value, str) and not value.strip()):
                optionals[name] = None
                continue
            if not isinstance(value, str):
                return SearchRecordError(
                    row_index=index,
                    field=name,
                    reason=f"{name} must be a string, got {type(value).__name__}",
                    raw_record=dict(raw),
                )
            optionals[name] = value.strip()

        device: SearchDevice | None = None
        if optionals["device"] is not None:
            try:
                device = SearchDevice(optionals["device"].casefold())
            except ValueError as exc:
                return SearchRecordError(
                    row_index=index, field="device", reason=str(exc), raw_record=dict(raw)
                )

        observed_at: datetime | None = None
        if optionals["observed_at"] is not None:
            try:
                observed_at = _iso_datetime(optionals["observed_at"], "observed_at")
            except ValueError as exc:
                return SearchRecordError(
                    row_index=index, field="observed_at", reason=str(exc), raw_record=dict(raw)
                )

        competitor_error = _check_competitor_pair(index, raw)
        if competitor_error is not None:
            return competitor_error

        # One shared fallback timestamp keeps all objects from one row consistent.
        fallback_now = datetime.now(UTC)

        try:
            keyword = SearchKeyword(keyword=raw["keyword"])
            observation_kwargs: dict[str, Any] = {
                "keyword": raw["keyword"],
                "target_url": raw["target_url"],
                "position": position,
                "source": optionals["source"] if optionals["source"] is not None else source,
                "observed_at": observed_at if observed_at is not None else fallback_now,
            }
            if optionals["search_engine"] is not None:
                observation_kwargs["search_engine"] = optionals["search_engine"]
            if optionals["country"] is not None:
                observation_kwargs["country"] = optionals["country"]
            if optionals["language"] is not None:
                observation_kwargs["language"] = optionals["language"]
            if device is not None:
                observation_kwargs["device"] = device
            observation = RankingObservation(**observation_kwargs)

            competitor = None
            if _has_value(raw.get("competitor_domain")):
                competitor = CompetitorRanking(
                    keyword=observation.keyword,
                    competitor_domain=str(raw["competitor_domain"]),
                    competitor_url=str(raw["competitor_url"]),
                    position=position,
                    observed_at=observation.observed_at,
                )
        except ValueError as exc:
            # Final safety net from the Phase 6A validators — still reported, never silent.
            return SearchRecordError(
                row_index=index, field="", reason=str(exc), raw_record=dict(raw)
            )

        return keyword, observation, competitor


def _check_required_string(index: int, raw: dict[str, Any], name: str) -> SearchRecordError | None:
    value = raw.get(name)
    if value is None:
        return SearchRecordError(
            row_index=index,
            field=name,
            reason=f"missing required field '{name}'",
            raw_record=dict(raw),
        )
    if not isinstance(value, str):
        return SearchRecordError(
            row_index=index,
            field=name,
            reason=f"{name} must be a string, got {type(value).__name__}",
            raw_record=dict(raw),
        )
    if not value.strip():
        return SearchRecordError(
            row_index=index,
            field=name,
            reason=f"'{name}' must be a non-empty string",
            raw_record=dict(raw),
        )
    return None


def _check_target_url(index: int, raw: dict[str, Any]) -> SearchRecordError | None:
    """Mirror the Phase 6A URL rule so failures carry precise field attribution."""
    value = str(raw["target_url"]).strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return SearchRecordError(
            row_index=index,
            field="target_url",
            reason=f"target_url must be an absolute http(s) URL, got {value!r}",
            raw_record=dict(raw),
        )
    return None


def _check_position(index: int, raw: dict[str, Any]) -> int | SearchRecordError:
    def fail(reason: str) -> SearchRecordError:
        return SearchRecordError(
            row_index=index, field="position", reason=reason, raw_record=dict(raw)
        )

    value = raw.get("position")
    if value is None:
        return fail("missing required field 'position'")
    if isinstance(value, bool):
        return fail(f"position must be an integer, got boolean {value!r}")
    if isinstance(value, float):
        return fail(f"position must be an integer, got floating-point value {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return fail("missing required field 'position'")
        if _INT_RE.fullmatch(text):
            return int(text)
        if _FLOAT_RE.fullmatch(text):
            return fail(f"position must be an integer, got floating-point value {text!r}")
        return fail(f"position must be numeric, got non-numeric value {value!r}")
    return fail(f"position must be numeric, got {type(value).__name__}")


def _check_competitor_pair(index: int, raw: dict[str, Any]) -> SearchRecordError | None:
    """Competitor rankings require both fields explicitly; never infer either."""
    domain_present = _has_value(raw.get("competitor_domain"))
    url_present = _has_value(raw.get("competitor_url"))
    if domain_present == url_present:
        return None
    supplied, missing = (
        ("competitor_domain", "competitor_url")
        if domain_present
        else ("competitor_url", "competitor_domain")
    )
    return SearchRecordError(
        row_index=index,
        field=missing,
        reason=(
            f"{supplied} was provided without {missing}; "
            "competitor_domain and competitor_url must be supplied together"
        ),
        raw_record=dict(raw),
    )
