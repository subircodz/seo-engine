"""Integration tests for Search Dataset Management API (Phase 6F)."""

# ── fixtures / helpers ────────────────────────────────────────────────────

RECORDS = [
    {"keyword": "crm software", "target_url": "https://oursite.io/crm", "position": 3},
    {"keyword": "seo tools", "target_url": "https://oursite.io/tools", "position": 7},
]

RECORDS_WITH_COMPETITOR = [
    {
        "keyword": "crm software",
        "target_url": "https://oursite.io/crm",
        "position": 3,
        "competitor_domain": "rival.io",
        "competitor_url": "https://rival.io/crm",
    },
]


async def _create_dataset(client, dataset_id: str, records: list, name: str = "test"):
    """Helper: create a persisted dataset and return the response."""
    return await client.post(
        "/api/search/datasets",
        json={"records": records, "dataset_id": dataset_id, "name": name, "source": "test"},
    )


# ── create ────────────────────────────────────────────────────────────────


class TestCreateDataset:
    async def test_create_dataset(self, client):
        response = await client.post(
            "/api/search/datasets",
            json={
                "records": RECORDS,
                "dataset_id": "ds-create-001",
                "name": "basic create",
                "source": "test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["dataset_id"] == "ds-create-001"
        assert data["name"] == "basic create"
        assert data["total_keywords"] == 2
        assert data["total_observations"] == 2
        assert "created_at" in data

    async def test_create_dataset_with_keywords(self, client):
        response = await client.post(
            "/api/search/datasets",
            json={
                "records": RECORDS,
                "dataset_id": "ds-create-kw",
                "name": "keywords test",
                "source": "test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        kw_texts = {kw["keyword"] for kw in data["keywords"]}
        assert "crm software" in kw_texts
        assert "seo tools" in kw_texts
        for kw in data["keywords"]:
            assert kw["normalized_keyword"] == kw["keyword"].casefold()
            assert kw["search_intent"] == "unknown"

    async def test_create_dataset_with_ranking_observations(self, client):
        response = await client.post(
            "/api/search/datasets",
            json={
                "records": RECORDS,
                "dataset_id": "ds-create-obs",
                "name": "observations test",
                "source": "gsc-test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["observations"]) == 2
        positions = {obs["position"] for obs in data["observations"]}
        assert positions == {3, 7}
        obs = data["observations"][0]
        for field in (
            "keyword",
            "target_url",
            "position",
            "source",
            "search_engine",
            "country",
            "language",
            "device",
            "observed_at",
        ):
            assert field in obs

    async def test_create_dataset_with_competitor_rankings(self, client):
        response = await client.post(
            "/api/search/datasets",
            json={
                "records": RECORDS_WITH_COMPETITOR,
                "dataset_id": "ds-create-comp",
                "name": "competitors test",
                "source": "test",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["competitor_rankings"]) == 1
        comp = data["competitor_rankings"][0]
        assert comp["keyword"] == "crm software"
        assert comp["competitor_domain"] == "rival.io"
        assert comp["competitor_url"] == "https://rival.io/crm"
        assert comp["position"] == 3
        assert "observed_at" in comp


# ── retrieve ──────────────────────────────────────────────────────────────


class TestRetrieveDataset:
    async def test_retrieve_dataset(self, client):
        await _create_dataset(client, "ds-retrieve-001", RECORDS, "retrieve me")
        response = await client.get("/api/search/datasets/ds-retrieve-001")
        assert response.status_code == 200
        data = response.json()
        # Stored values preserved verbatim.
        assert data["dataset_id"] == "ds-retrieve-001"
        assert data["name"] == "retrieve me"
        assert len(data["keywords"]) == 2
        assert len(data["observations"]) == 2
        urls = {obs["target_url"] for obs in data["observations"]}
        assert urls == {"https://oursite.io/crm", "https://oursite.io/tools"}

    async def test_retrieve_missing_dataset(self, client):
        response = await client.get("/api/search/datasets/nonexistent-id-999")
        assert response.status_code == 404


# ── list ──────────────────────────────────────────────────────────────────


class TestListDatasets:
    async def test_list_datasets(self, client):
        for i in range(3):
            await _create_dataset(client, f"ds-list-{i}", [RECORDS[0]], f"Dataset {i}")
        response = await client.get("/api/search/datasets")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["datasets"]) == 3
        ids = {ds["dataset_id"] for ds in data["datasets"]}
        assert ids == {"ds-list-0", "ds-list-1", "ds-list-2"}
        # Metadata-only listing: no record payload exposed.
        assert "keywords" not in data["datasets"][0]
        assert "observations" not in data["datasets"][0]

    async def test_list_pagination(self, client):
        for i in range(5):
            await _create_dataset(client, f"ds-page-{i}", [RECORDS[0]], f"Page {i}")
        page1 = (await client.get("/api/search/datasets?limit=2&offset=0")).json()
        assert page1["total"] == 5
        assert len(page1["datasets"]) == 2
        assert page1["limit"] == 2
        assert page1["offset"] == 0

        page2 = (await client.get("/api/search/datasets?limit=2&offset=2")).json()
        assert len(page2["datasets"]) == 2
        assert page2["offset"] == 2

        page3 = (await client.get("/api/search/datasets?limit=2&offset=4")).json()
        assert len(page3["datasets"]) == 1

        seen_ids = {
            ds["dataset_id"]
            for page in (page1, page2, page3)
            for ds in page["datasets"]
        }
        assert seen_ids == {f"ds-page-{i}" for i in range(5)}


# ── delete ────────────────────────────────────────────────────────────────


class TestDeleteDataset:
    async def test_delete_dataset(self, client):
        await _create_dataset(client, "ds-delete-001", RECORDS, "delete me")
        response = await client.delete("/api/search/datasets/ds-delete-001")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["dataset_id"] == "ds-delete-001"
        get_response = await client.get("/api/search/datasets/ds-delete-001")
        assert get_response.status_code == 404

    async def test_delete_missing_dataset(self, client):
        response = await client.delete("/api/search/datasets/nonexistent-id-999")
        assert response.status_code == 404

    async def test_cascade_deletion(self, client):
        """Child rows (keywords/observations/competitors) are removed by cascade."""
        await _create_dataset(client, "ds-cascade-001", RECORDS_WITH_COMPETITOR, "cascade")
        fetched = (
            await client.get("/api/search/datasets/ds-cascade-001")
        ).json()
        assert len(fetched["keywords"]) == 1
        assert len(fetched["observations"]) == 1
        assert len(fetched["competitor_rankings"]) == 1

        del_response = await client.delete("/api/search/datasets/ds-cascade-001")
        assert del_response.status_code == 200
        assert (await client.get("/api/search/datasets/ds-cascade-001")).status_code == 404

        # Re-creating the same ID succeeds only because cascade wiped child rows;
        # leftover children would surface as stale/orphan content here.
        recreate = await _create_dataset(client, "ds-cascade-001", [RECORDS[1]], "recreated")
        assert recreate.status_code == 201
        recreated = recreate.json()
        assert len(recreated["keywords"]) == 1
        assert recreated["keywords"][0]["keyword"] == "seo tools"
        assert len(recreated["observations"]) == 1
        assert len(recreated["competitor_rankings"]) == 0


# ── validation & conflicts ────────────────────────────────────────────────


class TestDatasetValidation:
    async def test_invalid_dataset_rejected(self, client):
        response = await client.post(
            "/api/search/datasets",
            json={"records": [], "name": "empty dataset"},
        )
        assert response.status_code == 422

        bad_records = [{"keyword": "", "target_url": "https://a.io/", "position": 1}]
        response2 = await client.post(
            "/api/search/datasets",
            json={"records": bad_records, "name": "bad keyword"},
        )
        assert response2.status_code == 422
        detail = response2.json()["detail"]
        assert "errors" in detail or "issues" in detail

    async def test_conflicting_records_rejected(self, client):
        ts = "2026-08-01T10:00:00+00:00"
        conflicting = [
            {"keyword": "kw", "target_url": "https://x.io/", "position": 1, "observed_at": ts},
            {"keyword": "kw", "target_url": "https://x.io/", "position": 9, "observed_at": ts},
        ]
        response = await client.post(
            "/api/search/datasets",
            json={"records": conflicting, "name": "conflict"},
        )
        assert response.status_code == 422

    async def test_duplicate_dataset_id_handled(self, client):
        first = await _create_dataset(client, "ds-dup-001", RECORDS, "first")
        assert first.status_code == 201
        second = await _create_dataset(client, "ds-dup-001", RECORDS, "second")
        assert second.status_code == 409
        # Original dataset remains intact.
        original = (await client.get("/api/search/datasets/ds-dup-001")).json()
        assert original["name"] == "first"


# ── regression guards ─────────────────────────────────────────────────────


class TestExistingEndpointsStillWork:
    async def test_phase_6d_import_still_works(self, client):
        response = await client.post("/api/search/import/json", json=RECORDS)
        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["successful_rows"] == 2
        assert data["has_errors"] is False

    async def test_phase_6d_validate_still_works(self, client):
        response = await client.post(
            "/api/search/validate",
            json={"records": RECORDS, "dataset_id": "ds-regression", "name": "regression"},
        )
        assert response.status_code == 200
        assert response.json()["valid"] is True

    async def test_health_still_works(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
