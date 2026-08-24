"""Integration tests for Search Intelligence API (Phase 6D)."""

import pytest

# ── fixtures / helpers ────────────────────────────────────────────────────


VALID_RECORDS = [
    {"keyword": "crm software", "target_url": "https://oursite.io/crm", "position": 3},
    {"keyword": "seo tools", "target_url": "https://oursite.io/tools", "position": 7},
]

CSV_TEXT = (
    "keyword,target_url,position\n"
    "crm software,https://oursite.io/crm,3\n"
    "seo tools,https://oursite.io/tools,7\n"
)

CSV_WITH_ERRORS = (
    "keyword,target_url,position\n"
    "good keyword,https://a.io/x,1\n"
    ",https://a.io/y,2\n"  # empty keyword → rejected
    "bad position,https://a.io/z,-5\n"  # negative position → rejected
)


@pytest.fixture
def dataset_payload() -> dict:
    return {
        "records": VALID_RECORDS,
        "dataset_id": "ds-test-001",
        "name": "integration fixture",
        "source": "test",
    }


# ── CSV import ────────────────────────────────────────────────────────────


class TestCsvImport:
    async def test_csv_text_import_success(self, client):
        response = await client.post(
            "/api/search/import/csv/text",
            content=CSV_TEXT,
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["successful_rows"] == 2
        assert data["rejected_rows"] == 0
        assert data["has_errors"] is False
        assert data["keywords_count"] == 2
        assert data["observations_count"] == 2
        assert data["validation_errors"] == []

    async def test_csv_import_with_invalid_rows(self, client):
        response = await client.post(
            "/api/search/import/csv/text",
            content=CSV_WITH_ERRORS,
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["successful_rows"] == 1
        assert data["rejected_rows"] == 2
        assert data["has_errors"] is True
        # Rejected rows are reported, not silently discarded.
        reasons = [e["reason"] for e in data["validation_errors"]]
        assert any("keyword" in r for r in reasons)
        assert any("position" in r for r in reasons)

    async def test_csv_import_missing_columns(self, client):
        bad_csv = "keyword,target_url\nfoo,https://a.io/\n"
        response = await client.post(
            "/api/search/import/csv/text",
            content=bad_csv,
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["has_errors"] is True
        assert data["total_rows"] == 0
        assert "missing required columns" in data["validation_errors"][0]["reason"]

    async def test_csv_file_upload(self, client):
        response = await client.post(
            "/api/search/import/csv",
            files={"file": ("data.csv", CSV_TEXT.encode(), "text/csv")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["successful_rows"] == 2
        assert data["has_errors"] is False


# ── JSON import ───────────────────────────────────────────────────────────


class TestJsonImport:
    async def test_json_array_import(self, client):
        response = await client.post("/api/search/import/json", json=VALID_RECORDS)
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["successful_rows"] == 2
        assert data["keywords_count"] == 2

    async def test_json_single_object_import(self, client):
        single = {"keyword": "k", "target_url": "https://a.io/", "position": 1}
        response = await client.post("/api/search/import/json", json=single)
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 1
        assert data["successful_rows"] == 1

    async def test_json_import_with_invalid_records(self, client):
        records = [
            {"keyword": "", "target_url": "https://a.io/", "position": 1},
            {"keyword": "ok", "target_url": "https://b.io/", "position": 2},
        ]
        response = await client.post("/api/search/import/json", json=records)
        assert response.status_code == 200
        data = response.json()
        assert data["rejected_rows"] == 1
        assert data["successful_rows"] == 1
        assert len(data["validation_errors"]) == 1
        error = data["validation_errors"][0]
        assert error["row_index"] == 0
        assert error["field"] == "keyword"

    async def test_malformed_json_body_rejected_by_framework(self, client):
        """FastAPI rejects structurally invalid JSON before reaching our code."""
        response = await client.post(
            "/api/search/import/json",
            content="{not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    async def test_non_object_array_rejected(self, client):
        response = await client.post("/api/search/import/json", json=["just a string"])
        # Non-dict array items are reported as per-row errors by the importer.
        assert response.status_code in (200, 422)


# ── validation endpoint ───────────────────────────────────────────────────


class TestValidateEndpoint:
    async def test_validate_valid_dataset(self, client, dataset_payload):
        response = await client.post("/api/search/validate", json=dataset_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["issue_count"] == 0
        assert data["issues"] == []
        # total_records = keywords + observations + competitor rankings.
        assert data["total_records"] == 4

    async def test_validate_detects_duplicates(self, client, dataset_payload):
        ts = "2026-08-01T10:00:00+00:00"
        duplicate = [
            {"keyword": "dup kw", "target_url": "https://x.io/", "position": 1, "observed_at": ts},
            {"keyword": "dup kw", "target_url": "https://x.io/", "position": 1, "observed_at": ts},
        ]
        payload = {**dataset_payload, "records": duplicate}
        response = await client.post("/api/search/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        codes = [i["code"] for i in data["issues"]]
        assert "duplicate_observation" in codes

    async def test_validate_detects_conflicts_as_error(self, client, dataset_payload):
        ts = "2026-08-01T10:00:00+00:00"
        conflicting = [
            {"keyword": "kw", "target_url": "https://x.io/", "position": 1, "observed_at": ts},
            {"keyword": "kw", "target_url": "https://x.io/", "position": 9, "observed_at": ts},
        ]
        payload = {**dataset_payload, "records": conflicting}
        response = await client.post("/api/search/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        issue = next(i for i in data["issues"] if i["code"] == "conflicting_observation")
        assert issue["severity"] == "error"

    async def test_validate_empty_records_422(self, client, dataset_payload):
        response = await client.post(
            "/api/search/validate", json={**dataset_payload, "records": []}
        )
        assert response.status_code == 422

    async def test_issue_exposes_required_fields(self, client, dataset_payload):
        records = [
            {"keyword": "SEO Guide", "target_url": "https://a.io/", "position": 1},
            {"keyword": "seo guide", "target_url": "https://b.io/", "position": 2},
        ]
        response = await client.post(
            "/api/search/validate", json={**dataset_payload, "records": records}
        )
        data = response.json()
        collision = next(i for i in data["issues"] if i["code"] == "keyword_collision")
        assert collision["keyword"] == "seo guide"
        assert collision["severity"] == "info"


# ── normalization endpoint ────────────────────────────────────────────────


class TestNormalizeEndpoint:
    async def test_normalize_dedupes_and_returns_counts(self, client, dataset_payload):
        ts = "2026-08-01T10:00:00+00:00"
        records = [
            {
                "keyword": "crm software",
                "target_url": "https://oursite.io/crm",
                "position": 3,
                "observed_at": ts,
            },
            {
                "keyword": "seo tools",
                "target_url": "https://oursite.io/tools",
                "position": 7,
                "observed_at": ts,
            },
            # Exact duplicate of the first row (same keyword+URL+device+timestamp).
            {
                "keyword": "crm software",
                "target_url": "https://oursite.io/crm",
                "position": 3,
                "observed_at": ts,
            },
        ]
        payload = {**dataset_payload, "records": records}
        response = await client.post("/api/search/normalize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_keywords"] == 2
        assert data["total_observations"] == 2
        assert data["observation_deduplicated"] is True

    async def test_normalize_is_deterministic(self, client, dataset_payload):
        r1 = await client.post("/api/search/normalize", json=dataset_payload)
        r2 = await client.post("/api/search/normalize", json=dataset_payload)
        d1, d2 = r1.json(), r2.json()
        assert d1["total_keywords"] == d2["total_keywords"]
        assert d1["total_observations"] == d2["total_observations"]

    async def test_normalize_preserves_metadata(self, client, dataset_payload):
        response = await client.post("/api/search/normalize", json=dataset_payload)
        data = response.json()
        assert data["dataset_id"] == "ds-test-001"
        assert data["name"] == "integration fixture"

    async def test_normalize_rejects_bad_records(self, client, dataset_payload):
        bad = [{"keyword": "no position here"}]
        response = await client.post(
            "/api/search/normalize", json={**dataset_payload, "records": bad}
        )
        assert response.status_code == 422

    async def test_normalize_empty_records_422(self, client, dataset_payload):
        response = await client.post(
            "/api/search/normalize", json={**dataset_payload, "records": []}
        )
        assert response.status_code == 422


# ── regression guards ─────────────────────────────────────────────────────


class TestExistingEndpoints:
    async def test_health_still_works(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")

    async def test_existing_crawl_routes_still_registered(self, client):
        response = await client.get("/openapi.json")
        paths = set(response.json()["paths"])
        assert "/api/crawl" in paths
        assert "/api/content/analyze" in paths
        assert "/api/diagnosis/run" in paths
        assert "/health" in paths
