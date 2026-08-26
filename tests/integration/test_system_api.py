"""System endpoints exercised through the full app + lifespan + SQLite."""


async def test_health_reports_ok(client):
    response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["environment"] == "test"
    assert body["app_name"] == "SEO Intelligence Engine"


async def test_index_renders_html(client):
    response = await client.get("/")

    assert response.status_code == 200
    assert "SEO Intelligence Engine" in response.text
