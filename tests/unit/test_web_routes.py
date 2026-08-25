"""Tests for the server-rendered UI routes.

Verifies all pages render correctly with proper status codes and content.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from sie.api.app import create_app


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


class TestIndexPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/")
        assert r.status_code == 200
        assert "SEO Intelligence Engine" in r.text

    @pytest.mark.anyio
    async def test_contains_dashboard_elements(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/")
        assert "Dashboard" in r.text
        assert "Datasets" in r.text
        assert "Intelligence" in r.text


class TestDatasetsPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/datasets")
        assert r.status_code == 200
        assert "Search Datasets" in r.text

    @pytest.mark.anyio
    async def test_contains_import_info(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/datasets")
        assert "Import" in r.text


class TestIntelligencePage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/intelligence")
        assert r.status_code == 200
        assert "Intelligence Analysis" in r.text

    @pytest.mark.anyio
    async def test_contains_form_elements(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/intelligence")
        assert "Dataset ID" in r.text
        assert "Target Domain" in r.text


class TestIndustryPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/industry")
        assert r.status_code == 200
        assert "Industry Intelligence" in r.text

    @pytest.mark.anyio
    async def test_contains_industry_form(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/industry")
        assert "Industry Type" in r.text
        assert "casino" in r.text.lower()


class TestReportsPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/reports")
        assert r.status_code == 200
        assert "Reports" in r.text

    @pytest.mark.anyio
    async def test_contains_download_elements(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/reports")
        assert "Download PDF" in r.text
        assert "Report ID" in r.text


class TestSearchPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/search")
        assert r.status_code == 200
        assert "Live Search" in r.text

    @pytest.mark.anyio
    async def test_contains_search_form(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/search")
        assert "Keyword" in r.text
        assert "Target Domain" in r.text


class TestDatasetDetailPage:
    @pytest.mark.anyio
    async def test_returns_200(self, client: AsyncClient) -> None:
        async with client as c:
            r = await c.get("/datasets/test-dataset-id")
        assert r.status_code == 200
        assert "Loading" in r.text
