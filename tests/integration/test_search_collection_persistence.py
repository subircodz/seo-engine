"""Integration tests for Search Collection Persistence (Phase 6I)."""

from sie.domain.models.search import SearchQuery
from sie.domain.models.search_result import SearchResult, SearchResultItem
from sie.domain.services.search_collection_service import SearchCollectionService
from sie.infrastructure.search.mock_provider import MockSearchProvider

# ── fixtures / helpers ────────────────────────────────────────────────────


async def _create_dataset(client, dataset_id: str, records: list, name: str = "col-test"):
    return await client.post(
        "/api/search/datasets",
        json={"records": records, "dataset_id": dataset_id, "name": name, "source": "test"},
    )


async def _configure_provider(harness, results: dict[str, SearchResult]):
    """Set up the mock provider with pre-configured results."""
    harness.app.state.search_provider = MockSearchProvider(results=results)


def _result_for(keyword: str, url: str = "https://oursite.io/page", position: int = 1):
    return SearchResult(
        keyword=keyword,
        items=(SearchResultItem(position=position, title=f"Result for {keyword}", url=url),),
    )


def _result_not_found(keyword: str):
    return SearchResult(keyword=keyword, items=())


COLLECTION_RECORDS = [
    {"keyword": "crm software", "target_url": "https://oursite.io/crm", "position": 3},
    {"keyword": "seo tools", "target_url": "https://oursite.io/tools", "position": 7},
]


# ── collection + persistence ──────────────────────────────────────────────


class TestCollectionPersistence:
    async def test_successful_collection(self, client, harness):
        await _create_dataset(client, "ds-col-001", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {"crm software": _result_for("crm software", "https://oursite.io/crm", 5)},
        )
        resp = await client.post(
            "/api/search/datasets/ds-col-001/collect",
            json={
                "queries": [
                    {
                        "keyword": "crm software",
                        "target_domain": "oursite.io",
                        "search_engine": "mock",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["dataset_id"] == "ds-col-001"
        assert data["queried_count"] == 1
        assert data["ranked_count"] == 1
        assert data["not_ranking_count"] == 0
        assert data["observations_saved"] == 1
        assert data["collection_errors"] == []

    async def test_multiple_observations(self, client, harness):
        await _create_dataset(client, "ds-col-002", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {
                "crm software": _result_for("crm software", "https://oursite.io/crm", 2),
                "seo tools": _result_for("seo tools", "https://oursite.io/tools", 8),
            },
        )
        resp = await client.post(
            "/api/search/datasets/ds-col-002/collect",
            json={
                "queries": [
                    {"keyword": "crm software", "target_domain": "oursite.io"},
                    {"keyword": "seo tools", "target_domain": "oursite.io"},
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["queried_count"] == 2
        assert data["ranked_count"] == 2
        assert data["observations_saved"] == 2

    async def test_not_ranking_result(self, client, harness):
        await _create_dataset(client, "ds-col-003", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {"keyword not on site": _result_for("keyword not on site", "https://other.io/", 1)},
        )
        resp = await client.post(
            "/api/search/datasets/ds-col-003/collect",
            json={
                "queries": [
                    {
                        "keyword": "keyword not on site",
                        "target_domain": "oursite.io",
                        "search_engine": "mock",
                    }
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["queried_count"] == 1
        assert data["ranked_count"] == 0
        assert data["not_ranking_count"] == 1
        assert data["observations_saved"] == 0

    async def test_mixed_ranked_not_ranking(self, client, harness):
        await _create_dataset(client, "ds-col-004", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {
                "found kw": _result_for("found kw", "https://oursite.io/found", 1),
                "missing kw": _result_for("missing kw", "https://other.io/page", 3),
            },
        )
        resp = await client.post(
            "/api/search/datasets/ds-col-004/collect",
            json={
                "queries": [
                    {"keyword": "found kw", "target_domain": "oursite.io"},
                    {"keyword": "missing kw", "target_domain": "oursite.io"},
                ]
            },
        )
        data = resp.json()
        assert data["queried_count"] == 2
        assert data["ranked_count"] == 1
        assert data["not_ranking_count"] == 1
        assert data["observations_saved"] == 1


# ── dataset isolation ─────────────────────────────────────────────────────


class TestDatasetIsolation:
    async def test_observations_isolated_to_dataset(self, client, harness):
        # Create A and B with records (each gets 2 imported observations)
        await _create_dataset(client, "ds-iso-A", COLLECTION_RECORDS, "A")
        await _create_dataset(client, "ds-iso-B", COLLECTION_RECORDS, "B")
        await _configure_provider(
            harness,
            {"kw": _result_for("kw", "https://oursite.io/kw", 4)},
        )
        # Record B's baseline count before collecting into A
        resp_b_before = await client.get("/api/search/datasets/ds-iso-B/observations")
        b_total_before = resp_b_before.json()["total"]
        # Collect into A only
        await client.post(
            "/api/search/datasets/ds-iso-A/collect",
            json={"queries": [{"keyword": "kw", "target_domain": "oursite.io"}]},
        )
        # Verify observations in A increased
        resp_a = await client.get("/api/search/datasets/ds-iso-A/observations")
        assert resp_a.status_code == 200
        assert resp_a.json()["total"] >= 1
        # Verify B is unchanged (still only the 2 imported records)
        resp_b = await client.get("/api/search/datasets/ds-iso-B/observations")
        assert resp_b.status_code == 200
        assert resp_b.json()["total"] == b_total_before


# ── observation retrieval ─────────────────────────────────────────────────


class TestObservationRetrieval:
    async def test_retrieval_returns_all_fields(self, client, harness):
        await _create_dataset(client, "ds-obs-001", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {"test kw": _result_for("test kw", "https://oursite.io/test", 6)},
        )
        await client.post(
            "/api/search/datasets/ds-obs-001/collect",
            json={
                "queries": [
                    {
                        "keyword": "test kw",
                        "target_domain": "oursite.io",
                        "search_engine": "bing",
                        "country": "IN",
                    }
                ]
            },
        )
        resp = await client.get("/api/search/datasets/ds-obs-001/observations")
        assert resp.status_code == 200
        data = resp.json()
        # Dataset had 2 imported records + 1 collected = 3 total
        assert data["total"] == 3
        # Find the collected observation by keyword
        collected = [o for o in data["observations"] if o["keyword"] == "test kw"]
        assert len(collected) == 1
        obs = collected[0]
        assert obs["position"] == 6
        assert obs["search_engine"] == "bing"
        assert obs["country"] == "in"
        assert "observed_at" in obs

    async def test_pagination(self, client, harness):
        await _create_dataset(client, "ds-page-001", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {
                f"kw-{i}": _result_for(f"kw-{i}", f"https://oursite.io/kw-{i}", i + 1)
                for i in range(5)
            },
        )
        queries = [{"keyword": f"kw-{i}", "target_domain": "oursite.io"} for i in range(5)]
        await client.post(
            "/api/search/datasets/ds-page-001/collect",
            json={"queries": queries},
        )
        page1 = await client.get("/api/search/datasets/ds-page-001/observations?limit=2&offset=0")
        page2 = await client.get("/api/search/datasets/ds-page-001/observations?limit=2&offset=2")
        assert page1.status_code == 200
        assert page2.status_code == 200
        d1 = page1.json()
        assert len(d1["observations"]) == 2
        assert d1["total"] >= 5


# ── 404 handling ──────────────────────────────────────────────────────────


class TestNotFound:
    async def test_collect_nonexistent_dataset(self, client, harness):
        await _configure_provider(harness, {})
        resp = await client.post(
            "/api/search/datasets/nonexistent-999/collect",
            json={"queries": [{"keyword": "kw", "target_domain": "x.io"}]},
        )
        assert resp.status_code == 404

    async def test_observations_nonexistent_dataset(self, client):
        resp = await client.get("/api/search/datasets/nonexistent-999/observations")
        assert resp.status_code == 404


# ── duplicate collection ──────────────────────────────────────────────────


class TestDuplicateCollection:
    async def test_duplicate_calls_preserve_all(self, client, harness):
        await _create_dataset(client, "ds-dup-001", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {"dup kw": _result_for("dup kw", "https://oursite.io/dup", 1)},
        )
        # Get baseline count (2 imported observations)
        resp_before = await client.get("/api/search/datasets/ds-dup-001/observations")
        baseline = resp_before.json()["total"]
        q = {"queries": [{"keyword": "dup kw", "target_domain": "oursite.io"}]}
        await client.post("/api/search/datasets/ds-dup-001/collect", json=q)
        await client.post("/api/search/datasets/ds-dup-001/collect", json=q)
        resp = await client.get("/api/search/datasets/ds-dup-001/observations")
        data = resp.json()
        # Both observations preserved — deduplication is the import layer's job (Phase 6C).
        assert data["total"] == baseline + 2


# ── metadata preservation ─────────────────────────────────────────────────


class TestMetadataPreservation:
    async def test_timestamp_persisted(self, client, harness):
        await _create_dataset(client, "ds-ts-001", COLLECTION_RECORDS)
        await _configure_provider(
            harness,
            {"ts kw": _result_for("ts kw", "https://oursite.io/ts", 1)},
        )
        await client.post(
            "/api/search/datasets/ds-ts-001/collect",
            json={"queries": [{"keyword": "ts kw", "target_domain": "oursite.io"}]},
        )
        resp = await client.get("/api/search/datasets/ds-ts-001/observations")
        obs = resp.json()["observations"][0]
        from datetime import datetime

        ts = datetime.fromisoformat(obs["observed_at"])
        assert ts.tzinfo is not None


# ── regression guards ─────────────────────────────────────────────────────


class TestExistingEndpointsStillWork:
    async def test_dataset_crud_still_works(self, client):
        create = await _create_dataset(client, "ds-reg-crud", COLLECTION_RECORDS, "regression")
        assert create.status_code == 201
        get_resp = await client.get("/api/search/datasets/ds-reg-crud")
        assert get_resp.status_code == 200
        del_resp = await client.delete("/api/search/datasets/ds-reg-crud")
        assert del_resp.status_code == 200

    async def test_phase_6d_import_still_works(self, client):
        resp = await client.post("/api/search/import/json", json=COLLECTION_RECORDS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["successful_rows"] == 2

    async def test_phase_6g_analytics_still_works(self, client):
        await _create_dataset(client, "ds-reg-analytics", COLLECTION_RECORDS, "analytics")
        resp = await client.get("/api/search/datasets/ds-reg-analytics/analytics")
        assert resp.status_code == 200
        assert resp.json()["dataset_id"] == "ds-reg-analytics"

    async def test_health_still_works(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("ok", "degraded")


# ── collection service unit behaviour ──────────────────────────────────────


class TestCollectionServiceUnit:
    async def test_collect_and_return_items(self):
        provider = MockSearchProvider(results={"kw": _result_for("kw", "https://oursite.io/kw", 1)})
        svc = SearchCollectionService(provider, source="unit-test")
        query = SearchQuery(query="kw", target_domain="oursite.io")
        items = await svc.collect([query])
        assert len(items) == 1
        assert items[0].found is True
        assert items[0].observation is not None

    async def test_not_ranking_service_returns_not_found(self):
        provider = MockSearchProvider(results={"kw": _result_for("kw", "https://other.io/page", 1)})
        svc = SearchCollectionService(provider, source="unit-test")
        query = SearchQuery(query="kw", target_domain="oursite.io")
        items = await svc.collect([query])
        assert items[0].found is False
        assert items[0].observation is None
