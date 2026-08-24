"""Unit tests for SearchDatasetService (Phase 6C).

Input data is synthetic fixture data.  No real search/ranking metrics are
asserted as facts; all assertions validate importer/validator *behaviour*.
"""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
    SearchKeyword,
)
from sie.domain.models.search_validation import (
    CONFLICTING_COMPETITOR_RANKING,
    CONFLICTING_OBSERVATION,
    DUPLICATE_COMPETITOR_RANKING,
    DUPLICATE_OBSERVATION,
    EMPTY_DATASET,
    INCONSISTENT_KEYWORD_NORMALIZATION,
    KEYWORD_COLLISION,
    MALFORMED_URL,
    NEGATIVE_COUNT,
    NON_HTTPS_URL,
    SEVERITY_ERROR,
    DatasetValidationResult,
    SearchDatasetContent,
)
from sie.domain.services.search_dataset_service import SearchDatasetService

TS = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def obs(
    keyword: str = "crm software",
    target_url: str = "https://oursite.io/crm",
    position: int = 3,
    source: str = "gsc",
    device: SearchDevice = SearchDevice.DESKTOP,
    observed_at: datetime = TS,
) -> RankingObservation:
    return RankingObservation(
        keyword=keyword,
        target_url=target_url,
        position=position,
        source=source,
        device=device,
        observed_at=observed_at,
    )


def comp(
    keyword: str = "crm software",
    domain: str = "rival.io",
    url: str = "https://rival.io/crm",
    position: int = 4,
    observed_at: datetime = TS,
) -> CompetitorRanking:
    return CompetitorRanking(
        keyword=keyword,
        competitor_domain=domain,
        competitor_url=url,
        position=position,
        observed_at=observed_at,
    )


_FIXED_CREATED_AT = datetime(2026, 8, 1, 0, 0, tzinfo=UTC)


def ds(**kw) -> SearchDataset:
    defaults = dict(
        dataset_id="ds-1",
        name="fixture",
        source="test",
        created_at=_FIXED_CREATED_AT,
        total_observations=1,
    )
    defaults.update(kw)
    return SearchDataset(**defaults)


@pytest.fixture
def svc() -> SearchDatasetService:
    return SearchDatasetService()


def _codes(result: DatasetValidationResult) -> dict[str, int]:
    """Count issues by code for compact assertion."""
    counts: dict[str, int] = {}
    for issue in result.issues:
        counts[issue.code] = counts.get(issue.code, 0) + 1
    return counts


# ════════════════════════════════════════════════════════════════════════════
# Valid datasets
# ════════════════════════════════════════════════════════════════════════════


class TestValidDatasets:
    def test_valid_dataset_no_issues(self, svc):
        result = svc.validate_dataset(ds(), keywords=[SearchKeyword("seo")], observations=[obs()])
        assert result.valid is True
        assert result.issue_count == 0
        assert result.total_records == 2

    def test_empty_dataset_flags_error(self, svc):
        result = svc.validate_dataset(ds(), keywords=(), observations=(), competitor_rankings=())
        assert result.valid is False
        assert result.issue_count == 1
        assert result.issues[0].code == EMPTY_DATASET
        assert result.issues[0].severity == SEVERITY_ERROR

    def test_content_bundle_accepted(self, svc):
        content = SearchDatasetContent(keywords=(SearchKeyword("k"),), observations=(obs(),))
        result = svc.validate_content(ds(), content)
        assert result.valid is True
        assert result.total_records == 2

    def test_empty_import_result_content(self, svc):
        import_result = __import__(
            "sie.domain.models.search_import", fromlist=["SearchImportResult"]
        ).SearchImportResult()
        content = svc.content_from_import_result(import_result)
        result = svc.validate_content(ds(), content)
        assert result.valid is False
        assert any(i.code == EMPTY_DATASET for i in result.issues)

    def test_total_records_includes_all_collections(self, svc):
        result = svc.validate_dataset(
            ds(),
            keywords=(SearchKeyword("a"), SearchKeyword("b")),
            observations=(obs(),),
            competitor_rankings=(comp(),),
        )
        assert result.total_records == 4


# ════════════════════════════════════════════════════════════════════════════
# Dataset integrity
# ════════════════════════════════════════════════════════════════════════════


class TestDatasetIntegrity:
    def test_negative_total_keywords_flagged(self, svc):
        dataset = ds()
        object.__setattr__(dataset, "total_keywords", -1)
        result = svc.validate_dataset(dataset, observations=(obs(),))
        codes = _codes(result)
        assert codes.get(NEGATIVE_COUNT, 0) >= 1

    def test_negative_total_observations_flagged(self, svc):
        dataset = ds()
        object.__setattr__(dataset, "total_observations", -5)
        result = svc.validate_dataset(dataset, observations=(obs(),))
        codes = _codes(result)
        assert codes.get(NEGATIVE_COUNT, 0) >= 1


# ════════════════════════════════════════════════════════════════════════════
# Duplicate / conflict detection
# ════════════════════════════════════════════════════════════════════════════


class TestDuplicateDetection:
    def test_exact_duplicate_observation_flagged(self, svc):
        identical = [obs(), obs()]
        result = svc.validate_dataset(ds(), observations=identical)
        assert result.valid is True  # harmless duplicates are warnings
        codes = _codes(result)
        assert codes.get(DUPLICATE_OBSERVATION, 0) == 1

    def test_exact_duplicate_deduped_by_normalize(self, svc):
        identical = (obs(), obs())
        content = SearchDatasetContent(observations=identical)
        normalized = svc.normalize_content(content)
        assert len(normalized.observations) == 1

    def test_conflicting_duplicate_positions_flagged_as_error(self, svc):
        a = obs(position=3)
        b = obs(position=7)
        result = svc.validate_dataset(ds(), observations=(a, b))
        assert result.valid is False
        codes = _codes(result)
        assert codes.get(CONFLICTING_OBSERVATION, 0) == 1

    def test_conflicting_duplicates_kept_by_normalize(self, svc):
        a = obs(position=3)
        b = obs(position=7)
        content = SearchDatasetContent(observations=(a, b))
        normalized = svc.normalize_content(content)
        assert len(normalized.observations) == 2

    def test_exact_duplicate_competitor_rankings_flagged(self, svc):
        result = svc.validate_dataset(
            ds(), observations=(obs(),), competitor_rankings=(comp(), comp())
        )
        assert result.valid is True  # harmless duplicates are warnings
        codes = _codes(result)
        assert codes.get(DUPLICATE_COMPETITOR_RANKING, 0) == 1

    def test_competitor_position_conflict_error(self, svc):
        a = comp(position=2)
        b = comp(position=9)
        result = svc.validate_dataset(ds(), observations=(obs(),), competitor_rankings=(a, b))
        assert result.valid is False
        assert any(i.code == CONFLICTING_COMPETITOR_RANKING for i in result.issues)

    def test_duplicate_competitor_deduped(self, svc):
        content = SearchDatasetContent(competitor_rankings=(comp(), comp(), comp()))
        normalized = svc.normalize_content(content)
        assert len(normalized.competitor_rankings) == 1

    def test_duplicate_deterministic_across_runs(self, svc):
        items = (
            obs("a", "https://a.io/", 1),
            obs("b", "https://b.io/", 2),
            obs("a", "https://a.io/", 1),
        )
        r1 = svc.validate_dataset(ds(), observations=items)
        r2 = svc.validate_dataset(ds(), observations=items)
        assert r1.issues == r2.issues


# ════════════════════════════════════════════════════════════════════════════
# Position / URL validation
# ════════════════════════════════════════════════════════════════════════════


class TestPositionValidation:
    def test_zero_position_defensive_detected(self, svc):
        o = obs()
        object.__setattr__(o, "position", 0)
        result = svc.validate_dataset(ds(), observations=(o,))
        codes = _codes(result)
        assert codes.get("invalid_position", 0) >= 1

    def test_negative_position_defensive_detected(self, svc):
        o = obs()
        object.__setattr__(o, "position", -3)
        result = svc.validate_dataset(ds(), observations=(o,))
        codes = _codes(result)
        assert codes.get("invalid_position", 0) >= 1


class TestUrlValidation:
    def test_malformed_url_detected(self, svc):
        o = obs()
        object.__setattr__(o, "target_url", "not-a-url")
        result = svc.validate_dataset(ds(), observations=(o,))
        codes = _codes(result)
        assert codes.get(MALFORMED_URL, 0) >= 1

    def test_non_https_scheme_detected(self, svc):
        o = obs()
        object.__setattr__(o, "target_url", "ftp://files.example.com/x")
        result = svc.validate_dataset(ds(), observations=(o,))
        codes = _codes(result)
        assert codes.get(NON_HTTPS_URL, 0) >= 1

    def test_valid_urls_not_flagged(self, svc):
        result = svc.validate_dataset(ds(), observations=[obs()])
        assert not any(i.code in (MALFORMED_URL, NON_HTTPS_URL) for i in result.issues)


# ════════════════════════════════════════════════════════════════════════════
# Keyword consistency
# ════════════════════════════════════════════════════════════════════════════


class TestKeywordConsistency:
    def test_keyword_collision_detected(self, svc):
        kws = [SearchKeyword("SEO Guide"), SearchKeyword("seo   guide")]
        result = svc.validate_dataset(ds(), keywords=kws)
        codes = _codes(result)
        assert codes.get(KEYWORD_COLLISION, 0) == 1

    def test_whitespace_variant_collision(self, svc):
        kws = [SearchKeyword(" SEO  Guide "), SearchKeyword("seo guide")]
        result = svc.validate_dataset(ds(), keywords=kws)
        codes = _codes(result)
        assert codes.get(KEYWORD_COLLISION, 0) == 1

    def test_inconsistent_normalization_field_detected(self, svc):
        kw = SearchKeyword("SEO Audit")
        object.__setattr__(kw, "normalized_keyword", "WRONG")
        result = svc.validate_dataset(ds(), keywords=(kw,))
        assert result.valid is False
        assert any(i.code == INCONSISTENT_KEYWORD_NORMALIZATION for i in result.issues)

    def test_consistent_keywords_no_collision_issue(self, svc):
        kws = [SearchKeyword("seo tools"), SearchKeyword("crm software")]
        result = svc.validate_dataset(ds(), keywords=kws)
        assert not any(i.code == KEYWORD_COLLISION for i in result.issues)

    def test_normalize_orders_keywords_stably(self, svc):
        content = SearchDatasetContent(
            keywords=(SearchKeyword("zzz"), SearchKeyword("aaa"), SearchKeyword("mmm"))
        )
        normalized = svc.normalize_content(content)
        result = [kw.keyword for kw in normalized.keywords]
        assert result == ["aaa", "mmm", "zzz"]


# ════════════════════════════════════════════════════════════════════════════
# Competitor validation
# ════════════════════════════════════════════════════════════════════════════


class TestCompetitorValidation:
    def test_invalid_competitor_defensive_detected(self, svc):
        c = comp()
        object.__setattr__(c, "position", 0)
        result = svc.validate_dataset(ds(), observations=(obs(),), competitor_rankings=(c,))
        codes = _codes(result)
        assert codes.get("invalid_position", 0) >= 1

    def test_malformed_competitor_url_detected(self, svc):
        c = comp()
        object.__setattr__(c, "competitor_url", "bad url")
        result = svc.validate_dataset(ds(), observations=(obs(),), competitor_rankings=(c,))
        codes = _codes(result)
        assert codes.get(MALFORMED_URL, 0) >= 1

    def test_non_http_competitor_url_detected(self, svc):
        c = comp()
        object.__setattr__(c, "competitor_url", "ftp://x.io/r")
        result = svc.validate_dataset(ds(), observations=(obs(),), competitor_rankings=(c,))
        codes = _codes(result)
        assert codes.get(NON_HTTPS_URL, 0) >= 1


# ════════════════════════════════════════════════════════════════════════════
# Normalization
# ════════════════════════════════════════════════════════════════════════════


class TestNormalization:
    def test_normalize_dataset_recomputes_counts(self, svc):
        dataset = ds(total_keywords=999, total_observations=999)
        content = SearchDatasetContent(
            keywords=(SearchKeyword("a"), SearchKeyword("b")),
            observations=(obs(), obs("k2", "https://b.io/", 1)),
        )
        result = svc.normalize_dataset(dataset, content=content)
        assert result.total_keywords == 2
        assert result.total_observations == 2

    def test_normalize_preserves_metadata(self, svc):
        dataset = ds(dataset_id="ID-42", name="My Export", source="gsc")
        result = svc.normalize_dataset(dataset, observations=(obs(),))
        assert result.dataset_id == "ID-42"
        assert result.name == "My Export"
        assert result.source == "gsc"

    def test_normalize_is_deterministic(self, svc):
        content = SearchDatasetContent(
            observations=(obs("b", "https://b.io/", 2), obs("a", "https://a.io/", 1))
        )
        r1 = svc.normalize_dataset(ds(), content=content)
        r2 = svc.normalize_dataset(ds(), content=content)
        assert r1 == r2

    def test_normalize_without_content_returns_equal_dataset(self, svc):
        dataset = ds()
        result = svc.normalize_dataset(dataset)
        assert result is dataset

    def test_stable_ordering_of_observations(self, svc):
        content = SearchDatasetContent(
            observations=(obs("zzz", "https://z.io/", 2), obs("aaa", "https://a.io/", 1))
        )
        normalized = svc.normalize_content(content)
        keys = [(o.keyword, o.position) for o in normalized.observations]
        assert keys == [("aaa", 1), ("zzz", 2)]

    def test_normalize_content_returns_new_instances(self, svc):
        original_kw = SearchKeyword("test")
        original_obs = obs()
        original_comp = comp()
        content = SearchDatasetContent(
            keywords=(original_kw,),
            observations=(original_obs,),
            competitor_rankings=(original_comp,),
        )
        normalized = svc.normalize_content(content)
        assert len(normalized.keywords) == 1
        assert len(normalized.observations) == 1
        assert len(normalized.competitor_rankings) == 1
        # The service never mutates input — frozen models prevent mutation anyway,
        # but verify new tuple objects are returned.
        assert normalized.keywords is not content.keywords


class TestNormalizationStability:
    def test_multiple_runs_produce_identical_objects(self, svc):
        content = SearchDatasetContent(
            observations=(
                obs("b", "https://b.io/", 2),
                obs("a", "https://a.io/", 1),
                obs("b", "https://b.io/", 2),  # exact duplicate
            )
        )
        n1 = svc.normalize_content(content)
        n2 = svc.normalize_content(content)
        assert n1.observations == n2.observations
        assert len(n1.observations) == 2
