"""Integration tests for AIO and GEO persistence (Phase 7)."""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import SearchDataset
from sie.domain.models.search_aio import (
    AIOCitation,
    AIOverviewObservation,
    AIOverviewType,
    CitationSource,
)
from sie.domain.models.search_geo import (
    EntityMention,
    EntityType,
    GenerativeEngineType,
    GEOObservation,
)

_T0 = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


@pytest.fixture
def repo(harness):
    return harness.app.state.repository


async def _create_dataset_via_repo(repo, dataset_id: str = "ds-persist-001"):
    """Create a test dataset directly via the repository."""
    dataset = SearchDataset(
        dataset_id=dataset_id,
        name="persistence-test",
        source="test",
        total_keywords=5,
        total_observations=10,
    )
    await repo.save_search_dataset(
        dataset,
        keywords=(),
        observations=(),
        competitor_rankings=(),
    )
    return dataset.dataset_id


# ── AIO Persistence Tests ────────────────────────────────────────────────


class TestAIOPersistence:
    @pytest.mark.anyio
    async def test_save_and_list_empty(self, repo):
        await _create_dataset_via_repo(repo, "ds-aio-001")
        total, observations = await repo.list_aio_observations("ds-aio-001")
        assert total == 0
        assert observations == []

    @pytest.mark.anyio
    async def test_save_single_observation(self, repo):
        await _create_dataset_via_repo(repo, "ds-aio-002")

        obs = AIOverviewObservation(
            keyword="seo tools",
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_cited=True,
            target_domain="oursite.io",
            citation_count=3,
            citations=(
                AIOCitation(
                    domain="oursite.io",
                    url="https://oursite.io/page",
                    position=0,
                    source_type=CitationSource.WEB_PAGE,
                    title="Our Page",
                ),
            ),
            competitor_cited_domains=("comp1.com", "comp2.com"),
            observed_at=_T0,
            source="test",
        )

        count = await repo.save_aio_observations("ds-aio-002", (obs,))
        assert count == 1

        total, observations = await repo.list_aio_observations("ds-aio-002")
        assert total == 1
        assert len(observations) == 1

        saved = observations[0]
        assert saved.keyword == "seo tools"
        assert saved.ai_type == AIOverviewType.AI_OVERVIEW
        assert saved.present is True
        assert saved.target_cited is True
        assert saved.target_domain == "oursite.io"
        assert saved.citation_count == 3
        assert len(saved.citations) == 1
        assert saved.citations[0].domain == "oursite.io"
        assert saved.citations[0].url == "https://oursite.io/page"
        assert saved.citations[0].position == 0
        assert saved.citations[0].source_type == CitationSource.WEB_PAGE
        assert saved.citations[0].title == "Our Page"
        assert "comp1.com" in saved.competitor_cited_domains
        assert "comp2.com" in saved.competitor_cited_domains

    @pytest.mark.anyio
    async def test_save_multiple_observations(self, repo):
        await _create_dataset_via_repo(repo, "ds-aio-003")

        obs1 = AIOverviewObservation(
            keyword="kw1",
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_cited=False,
            observed_at=_T0,
        )
        obs2 = AIOverviewObservation(
            keyword="kw2",
            ai_type=AIOverviewType.PERPLEXITY,
            present=False,
            observed_at=_T0,
        )

        count = await repo.save_aio_observations("ds-aio-003", (obs1, obs2))
        assert count == 2

        total, observations = await repo.list_aio_observations("ds-aio-003")
        assert total == 2
        assert len(observations) == 2

    @pytest.mark.anyio
    async def test_save_observation_no_citations(self, repo):
        await _create_dataset_via_repo(repo, "ds-aio-004")

        obs = AIOverviewObservation(
            keyword="kw1",
            ai_type=AIOverviewType.AI_OVERVIEW,
            present=True,
            target_cited=False,
            citation_count=0,
            citations=(),
            competitor_cited_domains=(),
            observed_at=_T0,
        )

        count = await repo.save_aio_observations("ds-aio-004", (obs,))
        assert count == 1

        total, observations = await repo.list_aio_observations("ds-aio-004")
        assert total == 1
        saved = observations[0]
        assert saved.citations == ()
        assert saved.competitor_cited_domains == ()

    @pytest.mark.anyio
    async def test_list_with_pagination(self, repo):
        await _create_dataset_via_repo(repo, "ds-aio-005")

        for i in range(5):
            obs = AIOverviewObservation(
                keyword=f"kw{i}",
                ai_type=AIOverviewType.AI_OVERVIEW,
                present=True,
                observed_at=_T0,
            )
            await repo.save_aio_observations("ds-aio-005", (obs,))

        total, page1 = await repo.list_aio_observations("ds-aio-005", limit=2, offset=0)
        assert total == 5
        assert len(page1) == 2

        total, page2 = await repo.list_aio_observations("ds-aio-005", limit=2, offset=2)
        assert total == 5
        assert len(page2) == 2

        total, page3 = await repo.list_aio_observations("ds-aio-005", limit=2, offset=4)
        assert total == 5
        assert len(page3) == 1


# ── GEO Persistence Tests ────────────────────────────────────────────────


class TestGEOPersistence:
    @pytest.mark.anyio
    async def test_save_and_list_empty(self, repo):
        await _create_dataset_via_repo(repo, "ds-geo-001")
        total, observations = await repo.list_geo_observations("ds-geo-001")
        assert total == 0
        assert observations == []

    @pytest.mark.anyio
    async def test_save_single_observation(self, repo):
        await _create_dataset_via_repo(repo, "ds-geo-002")

        obs = GEOObservation(
            keyword="best seo tools",
            engine_type=GenerativeEngineType.PERPLEXITY,
            target_mentioned=True,
            target_domain="oursite.io",
            mention_count=2,
            entity_mentions=(
                EntityMention(
                    text="OurSite",
                    entity_type=EntityType.BRAND,
                    is_target=True,
                    domain="oursite.io",
                ),
            ),
            competitor_domains=("comp1.com",),
            citation_urls=("https://oursite.io/page",),
            answer_length=500,
            observed_at=_T0,
            source="test",
        )

        count = await repo.save_geo_observations("ds-geo-002", (obs,))
        assert count == 1

        total, observations = await repo.list_geo_observations("ds-geo-002")
        assert total == 1
        assert len(observations) == 1

        saved = observations[0]
        assert saved.keyword == "best seo tools"
        assert saved.engine_type == GenerativeEngineType.PERPLEXITY
        assert saved.target_mentioned is True
        assert saved.target_domain == "oursite.io"
        assert saved.mention_count == 2
        assert len(saved.entity_mentions) == 1
        assert saved.entity_mentions[0].text == "OurSite"
        assert saved.entity_mentions[0].entity_type == EntityType.BRAND
        assert saved.entity_mentions[0].is_target is True
        assert saved.entity_mentions[0].domain == "oursite.io"
        assert "comp1.com" in saved.competitor_domains
        assert "https://oursite.io/page" in saved.citation_urls
        assert saved.answer_length == 500

    @pytest.mark.anyio
    async def test_save_multiple_observations(self, repo):
        await _create_dataset_via_repo(repo, "ds-geo-003")

        obs1 = GEOObservation(
            keyword="kw1",
            engine_type=GenerativeEngineType.PERPLEXITY,
            target_mentioned=True,
            observed_at=_T0,
        )
        obs2 = GEOObservation(
            keyword="kw2",
            engine_type=GenerativeEngineType.CHATGPT,
            target_mentioned=False,
            observed_at=_T0,
        )

        count = await repo.save_geo_observations("ds-geo-003", (obs1, obs2))
        assert count == 2

        total, observations = await repo.list_geo_observations("ds-geo-003")
        assert total == 2
        assert len(observations) == 2

    @pytest.mark.anyio
    async def test_save_observation_no_entities(self, repo):
        await _create_dataset_via_repo(repo, "ds-geo-004")

        obs = GEOObservation(
            keyword="kw1",
            engine_type=GenerativeEngineType.OTHER,
            target_mentioned=False,
            entity_mentions=(),
            competitor_domains=(),
            citation_urls=(),
            observed_at=_T0,
        )

        count = await repo.save_geo_observations("ds-geo-004", (obs,))
        assert count == 1

        total, observations = await repo.list_geo_observations("ds-geo-004")
        assert total == 1
        saved = observations[0]
        assert saved.entity_mentions == ()
        assert saved.competitor_domains == ()
        assert saved.citation_urls == ()

    @pytest.mark.anyio
    async def test_list_with_pagination(self, repo):
        await _create_dataset_via_repo(repo, "ds-geo-005")

        for i in range(5):
            obs = GEOObservation(
                keyword=f"kw{i}",
                engine_type=GenerativeEngineType.OTHER,
                target_mentioned=False,
                observed_at=_T0,
            )
            await repo.save_geo_observations("ds-geo-005", (obs,))

        total, page1 = await repo.list_geo_observations("ds-geo-005", limit=2, offset=0)
        assert total == 5
        assert len(page1) == 2

        total, page2 = await repo.list_geo_observations("ds-geo-005", limit=2, offset=2)
        assert total == 5
        assert len(page2) == 2

        total, page3 = await repo.list_geo_observations("ds-geo-005", limit=2, offset=4)
        assert total == 5
        assert len(page3) == 1
