"""Integration tests for Search Analytics API (Phase 6G)."""

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
    {
        "keyword": "seo tools",
        "target_url": "https://oursite.io/tools",
        "position": 7,
        "competitor_domain": "rival.io",
        "competitor_url": "https://rival.io/seo",
    },
]


async def _create(client, dataset_id: str, records: list, name: str = "analytics-test"):
    """Helper: create and return the creation response."""
    return await client.post(
        "/api/search/datasets",
        json={"records": records, "dataset_id": dataset_id, "name": name, "source": "test"},
    )


# ── successful analytics requests ─────────────────────────────────────────


class TestAnalyticsSuccess:
    async def test_successful_analytics_request(self, client):
        await _create(client, "ds-analytics-001", RECORDS)
        response = await client.get("/api/search/datasets/ds-analytics-001/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["dataset_id"] == "ds-analytics-001"
        m = data["metrics"]
        assert m["total_keywords"] == 2
        assert m["total_observations"] == 2
        assert m["visibility_score"] > 0
        assert isinstance(m["average_position"], (int, float))
        assert isinstance(m["median_position"], (int, float))

    async def test_404_dataset(self, client):
        response = await client.get("/api/search/datasets/nonexistent-xyz/analytics")
        assert response.status_code == 404
        assert "nonexistent-xyz" in response.json()["detail"]

    async def test_analytics_after_dataset_creation(self, client):
        """Analytics reflects the exact records in the dataset."""
        await _create(client, "ds-analytics-002", RECORDS, "post-create analytics")
        analytics = (await client.get("/api/search/datasets/ds-analytics-002/analytics")).json()
        assert analytics["dataset_id"] == "ds-analytics-002"
        kws = {k["keyword"] for k in analytics["keywords"]}
        assert kws == {"crm software", "seo tools"}

    async def test_multiple_keywords(self, client):
        multi_records = [
            {"keyword": f"kw-{i:02d}", "target_url": f"https://oursite.io/kw-{i}", "position": i}
            for i in range(1, 8)
        ]
        await _create(client, "ds-analytics-multi", multi_records, "multi kw")
        analytics = (await client.get("/api/search/datasets/ds-analytics-multi/analytics")).json()
        assert analytics["metrics"]["total_keywords"] == 7
        assert analytics["metrics"]["total_observations"] == 7
        assert len(analytics["keywords"]) == 7

    async def test_competitor_metrics(self, client):
        await _create(client, "ds-analytics-comp", RECORDS_WITH_COMPETITOR, "with comps")
        analytics = (await client.get("/api/search/datasets/ds-analytics-comp/analytics")).json()
        comps = analytics["competitors"]
        assert len(comps) == 1
        c = comps[0]
        assert c["competitor_domain"] == "rival.io"
        assert c["keyword_count"] == 2
        assert c["observed_count"] == 2
        assert c["outranking_count"] == 0
        # rival.io position 3 vs ours position 3 = equal → neither; position 7 vs 7 = equal
        assert c["outranked_count"] == 0

    async def test_competitor_that_outranks_us(self, client):
        # Row 1 carries the competitor record (rival@2); Row 2 is our later,
        # worse observation (kw@5). Latest ours = 5, rival = 2 → outranks us.
        records = [
            {
                "keyword": "kw",
                "target_url": "https://oursite.io/kw",
                "position": 2,
                "competitor_domain": "rival.io",
                "competitor_url": "https://rival.io/kw",
            },
            {"keyword": "kw", "target_url": "https://oursite.io/kw", "position": 5},
        ]
        await _create(client, "ds-analytics-comp2", records, "rival beats us")
        analytics = (await client.get("/api/search/datasets/ds-analytics-comp2/analytics")).json()
        c = analytics["competitors"][0]
        assert c["outranking_count"] == 1
        assert c["outranked_count"] == 0
        # sanity: our latest observation for kw is position 5
        kw = next(k for k in analytics["keywords"] if k["keyword"] == "kw")
        assert kw["latest_position"] == 5


# ── regression guards ─────────────────────────────────────────────────────


class TestExistingEndpointsStillWork:
    async def test_phase_6d_import_still_works(self, client):
        response = await client.post("/api/search/import/json", json=RECORDS)
        assert response.status_code == 200
        assert response.json()["successful_rows"] == 2

    async def test_phase_6f_crud_still_works(self, client):
        # create
        create = await _create(client, "ds-regression-crud", RECORDS, "regression")
        assert create.status_code == 201

        # get
        get_resp = await client.get("/api/search/datasets/ds-regression-crud")
        assert get_resp.status_code == 200

        # list
        list_resp = await client.get("/api/search/datasets")
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] >= 1

        # delete
        del_resp = await client.delete("/api/search/datasets/ds-regression-crud")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

        # 404 after delete
        assert (await client.get("/api/search/datasets/ds-regression-crud")).status_code == 404

    async def test_health_still_works(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("ok", "degraded")
