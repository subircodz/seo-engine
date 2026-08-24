"""Unit tests for the Search Data Importer (Phase 6B).

All input data below is synthetic fixture data describing *how* the importer
must behave — no real search/ranking metrics are asserted as facts.
"""

import json
from datetime import UTC, datetime

import pytest

from sie.domain.models.search import SearchDevice, SearchIntent
from sie.domain.services.search_import_service import SearchImportService

FULL_HEADER = (
    "keyword,target_url,position,"
    "search_engine,country,language,device,observed_at,source,"
    "competitor_domain,competitor_url\n"
)


def csv_row(
    keyword: str,
    target_url: str,
    position: str,
    *,
    search_engine: str = "",
    country: str = "",
    language: str = "",
    device: str = "",
    observed_at: str = "",
    source: str = "",
    competitor_domain: str = "",
    competitor_url: str = "",
) -> str:
    return (
        ",".join(
            [
                keyword,
                target_url,
                position,
                search_engine,
                country,
                language,
                device,
                observed_at,
                source,
                competitor_domain,
                competitor_url,
            ]
        )
        + "\n"
    )


@pytest.fixture
def service() -> SearchImportService:
    return SearchImportService()


# ════════════════════════════════════════════════════════════════════════════
# Valid imports
# ════════════════════════════════════════════════════════════════════════════


class TestValidCsvImport:
    def test_single_valid_row_with_all_columns(self, service):
        row = csv_row(
            "best crm software",
            "https://example.io/crm",
            "3",
            observed_at="2026-08-01T10:00:00+00:00",
            source="manual",
        )
        result = service.import_csv(FULL_HEADER + row)
        assert not result.has_errors
        assert result.total_rows == 1
        assert result.successful_rows == 1
        assert len(result.observations) == 1

        obs = result.observations[0]
        assert obs.keyword == "best crm software"
        assert obs.target_url == "https://example.io/crm"
        assert obs.position == 3
        assert obs.source == "manual"
        assert obs.search_engine == "google"
        assert obs.country == "us"
        assert obs.language == "en"
        assert obs.device is SearchDevice.DESKTOP
        assert obs.observed_at == datetime(2026, 8, 1, 10, 0, tzinfo=UTC)

    def test_minimal_row_uses_defaults(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("kw", "https://a.io/", "5"))
        obs = result.observations[0]
        assert not result.has_errors
        assert obs.position == 5
        assert obs.source == "search-import"
        assert obs.search_engine == "google"
        assert isinstance(obs.observed_at, datetime)

    def test_multiple_records(self, service):
        rows = csv_row("seo audit", "https://a.io/audit", "1") + csv_row(
            "crawl depth", "https://a.io/crawl", "7"
        )
        result = service.import_csv(FULL_HEADER + rows)
        assert result.total_rows == 2
        assert result.successful_rows == 2
        assert [o.position for o in result.observations] == [1, 7]
        assert len(result.keywords) == 2

    def test_keyword_normalization_applied(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("  SEO   AUDIT  ", "https://a.io/x", "2"))
        assert result.observations[0].keyword == "seo audit"
        assert result.keywords[0].normalized_keyword == "seo audit"

    def test_row_level_source_overrides_service_source(self, service):
        row = csv_row("kw", "https://a.io/", "5", source="gsc")
        result = service.import_csv(FULL_HEADER + row, source="csv-upload")
        assert result.observations[0].source == "gsc"

    def test_intent_defaults_to_unknown(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("kw", "https://a.io/", "1"))
        assert result.keywords[0].search_intent is SearchIntent.UNKNOWN


class TestValidJsonImport:
    def test_single_valid_record(self, service):
        payload = """
        [{"keyword": "running shoes",
          "target_url": "https://shop.example.com/shoes",
          "position": 4,
          "source": "gsc"}]
        """
        result = service.import_json(payload)
        assert not result.has_errors
        assert result.total_rows == 1
        obs = result.observations[0]
        assert obs.keyword == "running shoes"
        assert obs.position == 4
        assert obs.source == "gsc"
        assert obs.device is SearchDevice.DESKTOP

    def test_multiple_records_and_dedup_keywords(self, service):
        payload = [
            {"keyword": "CRM Software", "target_url": "https://a.io/", "position": 1},
            {"keyword": "crm software", "target_url": "https://b.io/", "position": 9},
            {"keyword": "email tools", "target_url": "https://c.io/", "position": 12},
        ]
        result = service.import_json(json.dumps(payload))
        assert result.total_rows == 3
        assert result.successful_rows == 3
        assert len(result.observations) == 3
        # Same normalized keyword appears once in the keyword list.
        assert len(result.keywords) == 2

    def test_single_object_payload_accepted(self, service):
        result = service.import_json(
            '{"keyword": "k", "target_url": "https://a.io/", "position": 2}'
        )
        assert result.total_rows == 1
        assert result.successful_rows == 1

    def test_bytes_input_accepted(self, service):
        one = '{"keyword": "k", "target_url": "https://a.io/", "position": 2}'
        assert service.import_json(one.encode()).successful_rows == 1
        assert service.import_csv(
            FULL_HEADER.encode() + csv_row("k", "https://a.io/", "2").encode()
        )

    def test_keyword_normalization_applied_json(self, service):
        payload = [
            {"keyword": "  Email   MARKETING ", "target_url": "https://a.io/", "position": 6}
        ]
        result = service.import_json(json.dumps(payload))
        assert result.observations[0].keyword == "email marketing"


# ════════════════════════════════════════════════════════════════════════════
# Optional-field handling
# ════════════════════════════════════════════════════════════════════════════


class TestOptionalFields:
    def test_all_optional_fields_respected(self, service):
        payload = [
            {
                "keyword": "k",
                "target_url": "https://a.io/",
                "position": 8,
                "search_engine": "Bing",
                "country": "DE",
                "language": "de",
                "device": "mobile",
                "observed_at": "2026-08-02T09:30:00Z",
                "source": "manual-export",
            }
        ]
        result = service.import_json(json.dumps(payload))
        obs = result.observations[0]
        assert obs.search_engine == "bing"
        assert obs.country == "de"
        assert obs.language == "de"
        assert obs.device is SearchDevice.MOBILE
        assert obs.observed_at == datetime(2026, 8, 2, 9, 30, tzinfo=UTC)
        assert obs.source == "manual-export"

    def test_blank_optional_cells_fall_back_to_defaults(self, service):
        row = csv_row("kw", "https://a.io/", "4", search_engine=" ", country="", language="")
        result = service.import_csv(FULL_HEADER + row)
        assert result.successful_rows == 1
        assert result.observations[0].search_engine == "google"

    def test_invalid_device_rejected(self, service):
        payload = [
            {"keyword": "k", "target_url": "https://a.io/", "position": 1, "device": "fridge"}
        ]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "device"

    def test_invalid_observed_at_rejected(self, service):
        payload = [
            {
                "keyword": "k",
                "target_url": "https://a.io/",
                "position": 1,
                "observed_at": "yesterday",
            }
        ]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "observed_at"
        assert "ISO 8601" in result.errors[0].reason

    def test_non_string_optional_field_rejected(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": 1, "country": 44}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "country"


# ════════════════════════════════════════════════════════════════════════════
# Required-field validation
# ════════════════════════════════════════════════════════════════════════════


class TestRequiredFieldValidation:
    def test_missing_keyword_json(self, service):
        result = service.import_json('[{"target_url": "https://a.io/", "position": 1}]')
        assert result.rejected_rows == 1
        assert result.errors[0].field == "keyword"
        assert "missing required field 'keyword'" in result.errors[0].reason
        assert result.observations == ()

    def test_empty_keyword_csv(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("  ", "https://a.io/", "1"))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "keyword"

    def test_missing_target_url_json(self, service):
        result = service.import_json('[{"keyword": "k", "position": 1}]')
        assert result.rejected_rows == 1
        assert result.errors[0].field == "target_url"
        assert "missing" in result.errors[0].reason

    def test_missing_url_cell_csv(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("k", "  ", "1"))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "target_url"

    @pytest.mark.parametrize("bad_url", ["not-a-url", "ftp://example.com/x", "example.com/page"])
    def test_invalid_urls_rejected(self, service, bad_url):
        payload = [{"keyword": "k", "target_url": bad_url, "position": 1}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "http(s)" in result.errors[0].reason or "absolute" in result.errors[0].reason

    def test_non_string_required_field_rejected(self, service):
        payload = [{"keyword": 42, "target_url": "https://a.io/", "position": 1}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "keyword"
        assert "must be a string" in result.errors[0].reason


# ════════════════════════════════════════════════════════════════════════════
# Position validation
# ════════════════════════════════════════════════════════════════════════════


class TestPositionValidation:
    def test_zero_position(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": 0}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert ">= 1" in result.errors[0].reason

    def test_negative_position_json(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": -4}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert ">= 1" in result.errors[0].reason

    def test_negative_position_from_csv_string(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("k", "https://a.io/", "-2"))
        assert result.rejected_rows == 1
        assert ">= 1" in result.errors[0].reason

    def test_boolean_position(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": True}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "boolean" in result.errors[0].reason

    def test_float_position(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": 3.5}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "floating-point" in result.errors[0].reason

    def test_integral_float_still_rejected(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": 3.0}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "floating-point" in result.errors[0].reason

    def test_float_position_from_csv(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("k", "https://a.io/", "3.5"))
        assert result.rejected_rows == 1
        assert "floating-point" in result.errors[0].reason

    def test_boolean_word_position_from_csv(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("k", "https://a.io/", "true"))
        assert result.rejected_rows == 1
        assert "non-numeric" in result.errors[0].reason

    def test_string_position_from_json(self, service):
        payload = [{"keyword": "k", "target_url": "https://a.io/", "position": "abc"}]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "non-numeric" in result.errors[0].reason

    def test_numeric_string_position_accepted(self, service):
        """CSV cells are strings; numeric strings must parse."""
        result = service.import_csv(FULL_HEADER + csv_row("k", "https://a.io/", " 12 "))
        assert result.successful_rows == 1
        assert result.observations[0].position == 12

    def test_null_and_missing_position_rejected(self, service):
        null_payload = [{"keyword": "k", "target_url": "https://a.io/", "position": None}]
        result = service.import_json(json.dumps(null_payload))
        assert result.rejected_rows == 1
        assert "missing" in result.errors[0].reason

        missing_result = service.import_json('[{"keyword": "k", "target_url": "https://a.io/"}]')
        assert missing_result.rejected_rows == 1
        assert missing_result.errors[0].field == "position"


# ════════════════════════════════════════════════════════════════════════════
# File-level failures
# ════════════════════════════════════════════════════════════════════════════


class TestFileLevelFailures:
    def test_malformed_json_reported(self, service):
        result = service.import_json('{"keyword": "k", ')
        assert result.has_errors
        assert result.total_rows == 0
        assert result.errors[0].row_index == -1
        assert "malformed JSON" in result.errors[0].reason

    def test_malformed_json_wrong_shape(self, service):
        result = service.import_json('"just a string"')
        assert result.has_errors
        assert "array of records" in result.errors[0].reason

    def test_malformed_csv_quoting_reported(self, service):
        result = service.import_csv(FULL_HEADER + '"unclosed,https://a.io/,1\n')
        assert result.has_errors
        assert result.total_rows == 0
        assert result.errors[0].row_index == -1
        assert "malformed CSV" in result.errors[0].reason

    def test_missing_required_columns_reported(self, service):
        result = service.import_csv("keyword,target_url\nk,https://a.io/\n")
        assert result.has_errors
        assert result.total_rows == 0
        assert "missing required columns: position" in result.errors[0].reason

    def test_non_object_json_records_reported_per_row(self, service):
        record = {"keyword": "k", "target_url": "https://a.io/", "position": 1}
        result = service.import_json(json.dumps(["nope", record]))
        assert result.total_rows == 2  # every payload record is accounted for
        assert result.rejected_rows == 1
        assert result.errors[0].row_index == 0
        assert result.successful_rows == 1


# ════════════════════════════════════════════════════════════════════════════
# Competitor fields
# ════════════════════════════════════════════════════════════════════════════


class TestCompetitorFields:
    def test_explicit_competitor_data_imported(self, service):
        payload = [
            {
                "keyword": "crm pricing",
                "target_url": "https://oursite.io/pricing",
                "position": 2,
                "competitor_domain": "Rival.io",
                "competitor_url": "https://rival.io/plans",
            }
        ]
        result = service.import_json(json.dumps(payload))
        assert result.successful_rows == 1
        assert len(result.competitor_rankings) == 1
        comp = result.competitor_rankings[0]
        assert comp.keyword == "crm pricing"
        assert comp.competitor_domain == "rival.io"
        assert comp.position == 2
        assert comp.observed_at == result.observations[0].observed_at

    def test_no_competitor_inference_without_fields(self, service):
        result = service.import_csv(FULL_HEADER + csv_row("kw", "https://a.io/", "1"))
        assert result.successful_rows == 1
        assert result.competitor_rankings == ()

    def test_competitor_domain_without_url_rejected(self, service):
        payload = [
            {
                "keyword": "k",
                "target_url": "https://a.io/",
                "position": 1,
                "competitor_domain": "rival.io",
            }
        ]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "together" in result.errors[0].reason
        assert result.observations == ()  # all-or-nothing per row

    def test_competitor_url_without_domain_rejected(self, service):
        payload = [
            {
                "keyword": "k",
                "target_url": "https://a.io/",
                "position": 1,
                "competitor_url": "https://rival.io/",
            }
        ]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert result.errors[0].field == "competitor_domain"

    def test_invalid_competitor_url_rejected(self, service):
        payload = [
            {
                "keyword": "k",
                "target_url": "https://a.io/",
                "position": 1,
                "competitor_domain": "rival.io",
                "competitor_url": "not-a-url",
            }
        ]
        result = service.import_json(json.dumps(payload))
        assert result.rejected_rows == 1
        assert "competitor_url" in result.errors[0].reason


# ════════════════════════════════════════════════════════════════════════════
# Mixed / edge datasets
# ════════════════════════════════════════════════════════════════════════════


class TestPartialFailuresAndEmptyDatasets:
    def test_partial_failure_reports_both_kinds(self, service):
        rows = (
            csv_row("good keyword", "https://a.io/one", "1")
            + csv_row("bad keyword", "https://a.io/two", "0")  # zero position -> rejected
            + csv_row("another good one", "https://a.io/three", "15")
        )
        result = service.import_csv(FULL_HEADER + rows)
        assert result.total_rows == 3
        assert result.successful_rows == 2
        assert result.rejected_rows == 1
        assert len(result.observations) == 2
        assert result.errors[0].row_index == 1
        assert result.errors[0].raw_record is not None
        assert result.errors[0].raw_record["keyword"] == "bad keyword"

    def test_errors_are_reported_not_silently_dropped(self, service):
        payload = [
            {"keyword": "", "target_url": "https://a.io/", "position": 1},
            {"keyword": "ok", "target_url": "https://a.io/", "position": 2},
        ]
        result = service.import_json(json.dumps(payload))
        # The rejected row must appear in errors with its raw record...
        assert result.rejected_rows == 1
        assert len(result.validation_errors) == 1
        assert result.errors[0].raw_record["keyword"] == ""
        # ...and must NOT appear among successes.
        assert [o.keyword for o in result.observations] == ["ok"]

    def test_empty_json_array_is_clean_empty_dataset(self, service):
        result = service.import_json("[]")
        assert result.total_rows == 0
        assert result.successful_rows == 0
        assert result.rejected_rows == 0
        assert not result.has_errors

    def test_header_only_csv_is_clean_empty_dataset(self, service):
        result = service.import_csv(FULL_HEADER)
        assert result.total_rows == 0
        assert not result.has_errors

    def test_every_invalid_row_is_reported_individually(self, service):
        payload = [
            {"keyword": "a", "target_url": "bad", "position": 1},
            {"keyword": "b", "target_url": "https://b.io/", "position": -1},
        ]
        result = service.import_json(json.dumps(payload))
        assert result.total_rows == 2
        assert result.rejected_rows == 2
        assert result.observations == ()
        assert {e.field for e in result.errors} == {"target_url", "position"}

    def test_result_counts_are_consistent(self, service):
        rows = (
            csv_row("one", "https://a.io/1", "1")
            + csv_row("", "https://a.io/2", "2")
            + csv_row("three", "https://a.io/3", "x")
            + csv_row("four", "https://a.io/4", "4")
        )
        result = service.import_csv(FULL_HEADER + rows)
        assert result.total_rows == result.successful_rows + result.rejected_rows
        assert result.total_rows == 4
        assert result.successful_rows == 2
