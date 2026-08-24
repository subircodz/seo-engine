"""Search Dataset Service — deterministic validation & normalization.

Validates an imported search dataset (metadata + records) against the Phase 6A
model invariants and dataset-level consistency rules, and performs only safe,
lossless normalization:

- deduplication of *fully identical* records only
- stable, deterministic ordering
- keyword handling delegated to the existing ``SearchKeyword`` model

Conflicting duplicates are flagged by ``validate_dataset`` and deliberately
kept by ``normalize_dataset`` — nothing is silently resolved or discarded.

No network, no LLM, no persistence.  Same input always yields the same output.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchKeyword,
)
from sie.domain.models.search_import import SearchImportResult
from sie.domain.models.search_validation import (
    CONFLICTING_COMPETITOR_RANKING,
    CONFLICTING_OBSERVATION,
    DUPLICATE_COMPETITOR_RANKING,
    DUPLICATE_OBSERVATION,
    EMPTY_DATASET,
    INCONSISTENT_KEYWORD_NORMALIZATION,
    INVALID_COMPETITOR_RANKING,
    INVALID_KEYWORD,
    INVALID_OBSERVATION,
    INVALID_POSITION,
    KEYWORD_COLLISION,
    MALFORMED_URL,
    MISSING_COMPETITOR_DOMAIN,
    MISSING_COMPETITOR_URL,
    NEGATIVE_COUNT,
    NON_HTTPS_URL,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    DatasetValidationIssue,
    DatasetValidationResult,
    SearchDatasetContent,
)

__all__ = ["SearchDatasetService"]

_UNSET = object()

_KeywordSeq = tuple[SearchKeyword, ...] | list[SearchKeyword]
_ObservationSeq = tuple[RankingObservation, ...] | list[RankingObservation]
_CompetitorSeq = tuple[CompetitorRanking, ...] | list[CompetitorRanking]


def _observation_identity(obs: RankingObservation) -> tuple[str, str, str, str]:
    """Deterministic duplicate identity: keyword + URL + device + timestamp."""
    return (obs.keyword, obs.target_url, obs.device.value, obs.observed_at.isoformat())


def _competitor_identity(comp: CompetitorRanking) -> tuple[str, str, str, str]:
    return (
        comp.keyword,
        comp.competitor_domain,
        comp.competitor_url,
        comp.observed_at.isoformat(),
    )


class SearchDatasetService:
    """Validates and normalizes imported search datasets (side-effect free)."""

    # ══════════════════════════════════════════════════════════════════════
    # Validation
    # ══════════════════════════════════════════════════════════════════════

    def validate_dataset(
        self,
        dataset: SearchDataset,
        *,
        keywords: _KeywordSeq = (),
        observations: _ObservationSeq = (),
        competitor_rankings: _CompetitorSeq = (),
        content: SearchDatasetContent | None = None,
    ) -> DatasetValidationResult:
        """Validate a dataset together with its record payload.

        ``content`` is a convenience alternative to passing the three
        collections individually (see ``SearchDatasetContent``).  Records are
        expected to come from the Phase 6B importer; because the Phase 6A
        models already enforce their own invariants at construction time, the
        object-level checks below act as defensive verification for records
        whose fields were altered after construction.
        """
        if content is not None:
            keywords, observations, competitor_rankings = (
                content.keywords,
                content.observations,
                content.competitor_rankings,
            )
        keywords = tuple(keywords)
        observations = tuple(observations)
        competitor_rankings = tuple(competitor_rankings)

        issues: list[DatasetValidationIssue] = []

        if not keywords and not observations:
            issues.append(
                DatasetValidationIssue(
                    code=EMPTY_DATASET,
                    severity=SEVERITY_ERROR,
                    message="dataset contains no keywords and no ranking observations",
                )
            )

        issues.extend(self._dataset_integrity_issues(dataset))
        issues.extend(self._keyword_issues(keywords, observations))
        issues.extend(self._observation_issues(observations))
        issues.extend(self._competitor_issues(competitor_rankings))

        total_records = len(keywords) + len(observations) + len(competitor_rankings)
        has_errors = any(issue.severity == SEVERITY_ERROR for issue in issues)
        return DatasetValidationResult(
            valid=not has_errors,
            total_records=total_records,
            issue_count=len(issues),
            issues=tuple(issues),
        )

    def validate_content(
        self,
        dataset: SearchDataset,
        content: SearchDatasetContent,
    ) -> DatasetValidationResult:
        """Convenience wrapper: validate a ``SearchDatasetContent`` bundle."""
        return self.validate_dataset(
            dataset,
            keywords=content.keywords,
            observations=content.observations,
            competitor_rankings=content.competitor_rankings,
        )

    # ══════════════════════════════════════════════════════════════════════
    # Normalization
    # ══════════════════════════════════════════════════════════════════════

    def normalize_dataset(
        self,
        dataset: SearchDataset,
        *,
        keywords: _KeywordSeq | object = _UNSET,
        observations: _ObservationSeq | object = _UNSET,
        competitor_rankings: _CompetitorSeq | object = _UNSET,
        content: SearchDatasetContent | None = None,
    ) -> SearchDataset:
        """Return a new immutable dataset with counts recomputed from the
        normalized/deduplicated content.

        Only lossless changes are made: fully identical duplicate records are
        collapsed, ordering is stabilized, and counts derive from the result.
        Metadata (id, name, source, created_at) is preserved verbatim; the
        input dataset is never mutated.  When no content is supplied at all,
        the dataset is returned unchanged.
        """
        if content is not None:
            keywords, observations, competitor_rankings = (
                content.keywords,
                content.observations,
                content.competitor_rankings,
            )
        if keywords is _UNSET and observations is _UNSET and competitor_rankings is _UNSET:
            return dataset

        normalized_keywords = self._normalize_keywords(
            () if keywords is _UNSET else tuple(keywords)  # type: ignore[arg-type]
        )
        normalized_observations = self._normalize_observations(
            () if observations is _UNSET else tuple(observations)  # type: ignore[arg-type]
        )
        normalized_competitors = self._normalize_competitors(
            () if competitor_rankings is _UNSET else tuple(competitor_rankings)  # type: ignore[arg-type]
        )
        del normalized_competitors  # counted datasets track keywords/observations only

        return SearchDataset(
            dataset_id=dataset.dataset_id,
            name=dataset.name,
            source=dataset.source,
            created_at=dataset.created_at,
            total_keywords=len(normalized_keywords),
            total_observations=len(normalized_observations),
        )

    def normalize_content(self, content: SearchDatasetContent) -> SearchDatasetContent:
        """Deduplicate and stably order a content bundle (lossless only)."""
        return SearchDatasetContent(
            keywords=self._normalize_keywords(content.keywords),
            observations=self._normalize_observations(content.observations),
            competitor_rankings=self._normalize_competitors(content.competitor_rankings),
        )

    def content_from_import_result(self, result: SearchImportResult) -> SearchDatasetContent:
        """Build content from a Phase 6B import result."""
        return SearchDatasetContent.from_import_result(result)

    # ══════════════════════════════════════════════════════════════════════
    # Normalization internals (lossless dedup + stable order)
    # ══════════════════════════════════════════════════════════════════════

    def _normalize_keywords(self, keywords: tuple[SearchKeyword, ...]) -> tuple[SearchKeyword, ...]:
        ordered = sorted(
            keywords,
            key=lambda kw: (kw.normalized_keyword or "", kw.keyword, kw.search_intent.value),
        )
        unique: dict[tuple[str, str, str], SearchKeyword] = {}
        for kw in ordered:
            unique.setdefault((kw.keyword, kw.normalized_keyword or "", kw.search_intent.value), kw)
        return tuple(unique.values())

    def _normalize_observations(
        self, observations: tuple[RankingObservation, ...]
    ) -> tuple[RankingObservation, ...]:
        ordered = sorted(
            observations,
            key=lambda o: (
                o.keyword,
                o.target_url,
                o.device.value,
                o.observed_at.isoformat(),
                o.position,
                o.source,
                o.search_engine,
                o.country,
                o.language,
            ),
        )
        seen: dict[tuple[str, str, str, str], RankingObservation] = {}
        kept: list[RankingObservation] = []
        for obs in ordered:
            identity = _observation_identity(obs)
            first = seen.get(identity)
            if first is None:
                seen[identity] = obs
                kept.append(obs)
            elif first == obs:
                continue  # fully identical — collapsing loses no information
            else:
                kept.append(obs)  # conflicting — keep both, validator reports it
        return tuple(kept)

    def _normalize_competitors(
        self, competitors: tuple[CompetitorRanking, ...]
    ) -> tuple[CompetitorRanking, ...]:
        ordered = sorted(
            competitors,
            key=lambda c: (
                c.keyword,
                c.competitor_domain,
                c.competitor_url,
                c.observed_at.isoformat(),
                c.position,
            ),
        )
        seen: dict[tuple[str, str, str, str], CompetitorRanking] = {}
        kept: list[CompetitorRanking] = []
        for comp in ordered:
            identity = _competitor_identity(comp)
            first = seen.get(identity)
            if first is None:
                seen[identity] = comp
                kept.append(comp)
            elif first == comp:
                continue
            else:
                kept.append(comp)
        return tuple(kept)

    # ══════════════════════════════════════════════════════════════════════
    # Validation internals
    # ══════════════════════════════════════════════════════════════════════

    def _dataset_integrity_issues(self, dataset: SearchDataset) -> list[DatasetValidationIssue]:
        issues: list[DatasetValidationIssue] = []
        for name, value in (
            ("total_keywords", dataset.total_keywords),
            ("total_observations", dataset.total_observations),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                issues.append(
                    DatasetValidationIssue(
                        code=NEGATIVE_COUNT,
                        severity=SEVERITY_ERROR,
                        message=(
                            f"impossible dataset count {name}={value!r} "
                            "(must be a non-negative integer)"
                        ),
                    )
                )
        return issues

    def _keyword_issues(
        self,
        keywords: tuple[SearchKeyword, ...],
        observations: tuple[RankingObservation, ...],
    ) -> list[DatasetValidationIssue]:
        issues: list[DatasetValidationIssue] = []

        for kw in keywords:
            if not isinstance(kw, SearchKeyword):
                issues.append(_invalid_object_issue(INVALID_KEYWORD, repr(kw)))
                continue
            try:
                canonical = SearchKeyword(kw.keyword).normalized_keyword
            except ValueError:
                issues.append(
                    DatasetValidationIssue(
                        code=INVALID_KEYWORD,
                        severity=SEVERITY_ERROR,
                        message=f"invalid keyword record: {kw.keyword!r}",
                        keyword=kw.keyword,
                    )
                )
                continue
            if canonical != kw.normalized_keyword:
                issues.append(
                    DatasetValidationIssue(
                        code=INCONSISTENT_KEYWORD_NORMALIZATION,
                        severity=SEVERITY_ERROR,
                        message=(
                            f"stored normalization {kw.normalized_keyword!r} does not match "
                            f"model normalization {canonical!r}"
                        ),
                        keyword=kw.keyword,
                    )
                )

        # Raw spellings that collapse onto one normalized form (Phase 6A rule).
        raw_by_normalized: dict[str, set[str]] = defaultdict(set)
        for kw in keywords:
            if isinstance(kw, SearchKeyword):
                raw_by_normalized[kw.normalized_keyword or ""].add(kw.keyword)
        for obs in observations:
            if isinstance(obs, RankingObservation) and obs.keyword.strip():
                try:
                    normalized = SearchKeyword(obs.keyword).normalized_keyword
                except ValueError:
                    continue
                raw_by_normalized[normalized].add(obs.keyword)
        for normalized in sorted(raw_by_normalized):
            variants = raw_by_normalized[normalized]
            if len(variants) > 1:
                issues.append(
                    DatasetValidationIssue(
                        code=KEYWORD_COLLISION,
                        severity=SEVERITY_INFO,
                        message=(
                            f"{len(variants)} raw spellings resolve to normalized keyword "
                            f"{normalized!r}: {sorted(variants)!r}"
                        ),
                        keyword=normalized,
                    )
                )
        return issues

    def _observation_issues(
        self, observations: tuple[RankingObservation, ...]
    ) -> list[DatasetValidationIssue]:
        issues: list[DatasetValidationIssue] = []

        for obs in observations:
            if not isinstance(obs, RankingObservation) or not isinstance(obs.observed_at, datetime):
                issues.append(_invalid_object_issue(INVALID_OBSERVATION, repr(obs)))
                continue
            position = obs.position
            if isinstance(position, bool) or not isinstance(position, int):
                issues.append(
                    _position_issue(obs, f"position must be an integer, got {position!r}")
                )
            elif position < 1:
                issues.append(
                    _position_issue(obs, f"position {position} outside valid range (must be >= 1)")
                )
            issues.extend(_url_issues(obs.target_url, keyword=obs.keyword))

        issues.extend(self._duplicate_and_conflict_issues(observations=observations))
        return issues

    def _competitor_issues(
        self, competitors: tuple[CompetitorRanking, ...]
    ) -> list[DatasetValidationIssue]:
        issues: list[DatasetValidationIssue] = []

        for comp in competitors:
            if not isinstance(comp, CompetitorRanking) or not isinstance(
                comp.observed_at, datetime
            ):
                issues.append(_invalid_object_issue(INVALID_COMPETITOR_RANKING, repr(comp)))
                continue
            position = comp.position
            if isinstance(position, bool) or not isinstance(position, int):
                issues.append(
                    DatasetValidationIssue(
                        code=INVALID_POSITION,
                        severity=SEVERITY_ERROR,
                        message=f"position must be an integer, got {position!r}",
                        keyword=comp.keyword,
                        url=comp.competitor_url,
                    )
                )
            elif position < 1:
                issues.append(
                    DatasetValidationIssue(
                        code=INVALID_POSITION,
                        severity=SEVERITY_ERROR,
                        message=f"position {position} outside valid range (must be >= 1)",
                        keyword=comp.keyword,
                        url=comp.competitor_url,
                    )
                )
            domain = comp.competitor_domain
            if not isinstance(domain, str) or not domain.strip():
                issues.append(
                    DatasetValidationIssue(
                        code=MISSING_COMPETITOR_DOMAIN,
                        severity=SEVERITY_ERROR,
                        message="competitor ranking without competitor domain",
                        keyword=comp.keyword,
                    )
                )
            url = comp.competitor_url
            if not isinstance(url, str) or not url.strip():
                issues.append(
                    DatasetValidationIssue(
                        code=MISSING_COMPETITOR_URL,
                        severity=SEVERITY_ERROR,
                        message="competitor ranking without competitor URL",
                        keyword=comp.keyword,
                    )
                )
            else:
                issues.extend(_url_issues(url, keyword=comp.keyword))

        issues.extend(self._duplicate_and_conflict_issues(competitors=competitors))
        return issues

    # -- duplicate / conflict grouping -------------------------------------

    def _duplicate_and_conflict_issues(
        self,
        observations: tuple[RankingObservation, ...] = (),
        competitors: tuple[CompetitorRanking, ...] = (),
    ) -> list[DatasetValidationIssue]:
        """Flag duplicate identities and conflicting ranking information."""
        issues: list[DatasetValidationIssue] = []

        obs_groups: dict[tuple[str, str, str, str], list[RankingObservation]] = defaultdict(list)
        for obs in observations:
            if isinstance(obs, RankingObservation) and isinstance(obs.observed_at, datetime):
                obs_groups[_observation_identity(obs)].append(obs)
        for identity in sorted(obs_groups):
            members = obs_groups[identity]
            if len(members) < 2:
                continue
            keyword, url = members[0].keyword, members[0].target_url
            positions = sorted({obs.position for obs in members})
            if len(positions) > 1:
                issues.append(
                    DatasetValidationIssue(
                        code=CONFLICTING_OBSERVATION,
                        severity=SEVERITY_ERROR,
                        message=(
                            f"{len(members)} observations share keyword+URL+device+timestamp "
                            f"but disagree on position ({positions}); conflict must be "
                            "resolved manually"
                        ),
                        keyword=keyword,
                        url=url,
                    )
                )
            else:
                issues.append(
                    DatasetValidationIssue(
                        code=DUPLICATE_OBSERVATION,
                        severity=SEVERITY_WARNING,
                        message=(
                            f"{len(members)} identical observations share "
                            "keyword+URL+device+timestamp"
                        ),
                        keyword=keyword,
                        url=url,
                    )
                )

        comp_groups: dict[tuple[str, str, str, str], list[CompetitorRanking]] = defaultdict(list)
        for comp in competitors:
            if isinstance(comp, CompetitorRanking) and isinstance(comp.observed_at, datetime):
                comp_groups[_competitor_identity(comp)].append(comp)
        for identity in sorted(comp_groups):
            members = comp_groups[identity]
            if len(members) < 2:
                continue
            positions = sorted({comp.position for comp in members})
            if len(positions) > 1:
                issues.append(
                    DatasetValidationIssue(
                        code=CONFLICTING_COMPETITOR_RANKING,
                        severity=SEVERITY_ERROR,
                        message=(
                            f"{len(members)} competitor rankings agree on "
                            f"keyword+domain+URL+timestamp but disagree on position "
                            f"({positions}); records kept"
                        ),
                        keyword=members[0].keyword,
                        url=members[0].competitor_url,
                    )
                )
            else:
                issues.append(
                    DatasetValidationIssue(
                        code=DUPLICATE_COMPETITOR_RANKING,
                        severity=SEVERITY_WARNING,
                        message=(
                            f"{len(members)} identical competitor rankings for the same "
                            "keyword+domain+URL+timestamp"
                        ),
                        keyword=members[0].keyword,
                        url=members[0].competitor_url,
                    )
                )
        return issues


def _position_issue(obs: RankingObservation, message: str) -> DatasetValidationIssue:
    return DatasetValidationIssue(
        code=INVALID_POSITION,
        severity=SEVERITY_ERROR,
        message=message,
        keyword=obs.keyword,
        url=obs.target_url,
    )


def _url_issues(url: str, *, keyword: str | None = None) -> list[DatasetValidationIssue]:
    """Static URL checks: malformed shapes and non-http(s) schemes."""
    if not isinstance(url, str) or not url.strip():
        return [
            DatasetValidationIssue(
                code=MALFORMED_URL,
                severity=SEVERITY_ERROR,
                message=f"malformed URL: {url!r}",
                keyword=keyword,
            )
        ]
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return [
            DatasetValidationIssue(
                code=MALFORMED_URL,
                severity=SEVERITY_ERROR,
                message=f"malformed URL (missing scheme or host): {url!r}",
                keyword=keyword,
                url=url,
            )
        ]
    if parsed.scheme not in ("http", "https"):
        return [
            DatasetValidationIssue(
                code=NON_HTTPS_URL,
                severity=SEVERITY_ERROR,
                message=f"URL scheme must be http/https, got {parsed.scheme!r}: {url!r}",
                keyword=keyword,
                url=url,
            )
        ]
    return []


def _invalid_object_issue(code: str, representation: str) -> DatasetValidationIssue:
    return DatasetValidationIssue(
        code=code,
        severity=SEVERITY_ERROR,
        message=f"record failed model invariants: {representation}",
    )
