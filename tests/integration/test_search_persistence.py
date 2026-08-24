"""Integration tests for search dataset persistence (Phase 6E)."""

from datetime import UTC, datetime

import pytest

from sie.domain.models.search import (
    CompetitorRanking,
    RankingObservation,
    SearchDataset,
    SearchDevice,
    SearchIntent,
    SearchKeyword,
)

_TS = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
_TS2 = datetime(2026, 9, 15, 9, 30, tzinfo=UTC)


def _ds(dataset_id: str = "ds-1") -> SearchDataset:
    return SearchDataset(
        dataset_id=dataset_id,
        name="fixture",
        source="test",
        total_keywords=0,
        total_observations=0,
    )


def _kw(keyword: str = "seo guide") -> SearchKeyword:
    return SearchKeyword(keyword=keyword, search_intent=SearchIntent.INFORMATIONAL)


def _obs(
    keyword: str = "seo guide",
    url: str = "https://a.io/seo",
    position: int = 3,
) -> RankingObservation:
    return RankingObservation(
        keyword=keyword,
        target_url=url,
        position=position,
        source="gsc",
        device=SearchDevice.MOBILE,
        search_engine="google",
        country="us",
        language="en",
        observed_at=_TS,
    )


def _comp(
    keyword: str = "seo guide",
    domain: str = "rival.io",
    url: str = "https://rival.io/seo",
    position: int = 5,
) -> CompetitorRanking:
    return CompetitorRanking(
        keyword=keyword,
        competitor_domain=domain,
        competitor_url=url,
        position=position,
        observed_at=_TS,
    )


@pytest.fixture
def repo(harness):
    return harness.app.state.repository


# ── save + retrieve round-trip ─────────────────────────────────────────────


class TestSearchDatasetPersistence:
    async def test_save_and_retrieve_metadata(self, repo):
        ds = _ds("ds-meta")
        await repo.save_search_dataset(ds)
        result = await repo.get_search_dataset("ds-meta")
        assert result is not None
        fetched, content = result
        assert fetched.dataset_id == "ds-meta"
        assert fetched.name == "fixture"
        assert fetched.source == "test"
        assert len(content.keywords) == 0
        assert len(content.observations) == 0

    async def test_empty_dataset_handling(self, repo):
        ds = _ds("ds-empty")
        await repo.save_search_dataset(ds)
        _, content = await repo.get_search_dataset("ds-empty")
        assert content.keywords == ()
        assert content.observations == ()
        assert content.competitor_rankings == ()

    async def test_multiple_keywords_persisted(self, repo):
        ds = _ds("ds-kws")
        kws = [_kw("seo guide"), _kw("crm software"), _kw("email tools")]
        await repo.save_search_dataset(ds, keywords=kws)
        _, content = await repo.get_search_dataset("ds-kws")
        assert len(content.keywords) == 3
        retrieved_kw = {kw.keyword for kw in content.keywords}
        assert retrieved_kw == {"seo guide", "crm software", "email tools"}

    async def test_multiple_observations_persisted(self, repo):
        ds = _ds("ds-obs")
        observations = [
            _obs("kw1", "https://a.io/x", 1),
            _obs("kw2", "https://b.io/y", 9),
        ]
        await repo.save_search_dataset(ds, observations=observations)
        _, content = await repo.get_search_dataset("ds-obs")
        assert len(content.observations) == 2
        positions = {obs.position for obs in content.observations}
        assert positions == {1, 9}

    async def test_competitor_rankings_persisted(self, repo):
        ds = _ds("ds-comp")
        competitors = [_comp("kw", "r.io", "https://r.io/x", 3)]
        await repo.save_search_dataset(ds, competitor_rankings=competitors)
        _, content = await repo.get_search_dataset("ds-comp")
        assert len(content.competitor_rankings) == 1
        assert content.competitor_rankings[0].competitor_domain == "r.io"
        assert content.competitor_rankings[0].position == 3

    async def test_metadata_preserved(self, repo):
        ds_with_content = SearchDataset(
            dataset_id="ds-meta2",
            name="My Search Export",
            source="gsc",
            total_keywords=2,
            total_observations=3,
        )
        await repo.save_search_dataset(ds_with_content)
        fetched = (await repo.get_search_dataset("ds-meta2"))[0]
        assert fetched.dataset_id == "ds-meta2"
        assert fetched.name == "My Search Export"
        assert fetched.source == "gsc"
        assert fetched.total_keywords == 0  # record count overridden by actual writes

    async def test_timestamp_preserved(self, repo):
        ts = datetime(2026, 3, 15, 8, 45, 30, 123456, tzinfo=UTC)
        ds = SearchDataset(
            dataset_id="ds-ts",
            name="ts",
            source="s",
            created_at=ts,
            total_keywords=0,
            total_observations=0,
        )
        obs_with_ts = RankingObservation(
            keyword="kw",
            target_url="https://x.io/",
            position=1,
            source="s",
            device=SearchDevice.MOBILE,
            observed_at=ts,
        )
        await repo.save_search_dataset(ds, observations=[obs_with_ts])
        fetched_ds, content = await repo.get_search_dataset("ds-ts")
        assert fetched_ds.created_at.replace(tzinfo=UTC) == ts
        assert content.observations[0].observed_at.replace(tzinfo=UTC) == ts

    async def test_keyword_normalization_preserved(self, repo):
        ds = _ds("ds-norm")
        kw = SearchKeyword(
            keyword="SEO   Guide",
            normalized_keyword="seo guide",
            search_intent=SearchIntent.INFORMATIONAL,
        )
        await repo.save_search_dataset(ds, keywords=[kw])
        _, content = await repo.get_search_dataset("ds-norm")
        retrieved = content.keywords[0]
        assert retrieved.keyword == "SEO   Guide"
        assert retrieved.normalized_keyword == "seo guide"
        assert retrieved.search_intent is SearchIntent.INFORMATIONAL

    async def test_device_and_intent_preserved(self, repo):
        ds = _ds("ds-dev")
        kw = SearchKeyword(keyword="buy shoes", search_intent=SearchIntent.TRANSACTIONAL)
        obs = RankingObservation(
            keyword="buy shoes",
            target_url="https://shop.io/",
            position=1,
            source="gsc",
            device=SearchDevice.TABLET,
            search_engine="bing",
            country="uk",
            language="en",
            observed_at=_TS,
        )
        await repo.save_search_dataset(ds, keywords=[kw], observations=[obs])
        _, content = await repo.get_search_dataset("ds-dev")
        assert content.keywords[0].search_intent is SearchIntent.TRANSACTIONAL
        assert content.observations[0].device is SearchDevice.TABLET
        assert content.observations[0].search_engine == "bing"
        assert content.observations[0].country == "uk"

    async def test_missing_dataset_returns_none(self, repo):
        result = await repo.get_search_dataset("nonexistent-id-999")
        assert result is None

    async def test_transaction_rollback_on_failure(self, repo):
        # Duplicate dataset_id causes IntegrityError; rollback leaves DB intact.
        from sqlalchemy.exc import IntegrityError

        ds = _ds("ds-rollback")
        await repo.save_search_dataset(ds, keywords=[_kw()])

        # Second save with same id should raise IntegrityError.
        with pytest.raises(IntegrityError):
            await repo.save_search_dataset(ds, keywords=[_kw()])

        # Original must still be intact with its keyword.
        _, content = await repo.get_search_dataset("ds-rollback")
        assert content is not None
        assert len(content.keywords) == 1

    async def test_round_trip_all_fields(self, repo):
        ds_id = "ds-roundtrip"
        ts = datetime(2026, 7, 20, 14, 30, tzinfo=UTC)
        ds = SearchDataset(
            dataset_id=ds_id,
            name="Full Round Trip",
            source="test-suite",
            created_at=ts,
            total_keywords=0,
            total_observations=0,
        )
        kw = SearchKeyword(
            keyword="CRM comparison",
            normalized_keyword="crm comparison",
            search_intent=SearchIntent.COMMERCIAL,
        )
        obs = RankingObservation(
            keyword="CRM comparison",
            target_url="https://oursite.io/crm",
            position=7,
            source="manual",
            search_engine="bing",
            country="de",
            language="de",
            device=SearchDevice.MOBILE,
            observed_at=ts,
        )
        competitor = CompetitorRanking(
            keyword="CRM comparison",
            competitor_domain="rival.io",
            competitor_url="https://rival.io/crm-comparison",
            position=2,
            observed_at=ts,
        )

        await repo.save_search_dataset(
            ds,
            keywords=[kw],
            observations=[obs],
            competitor_rankings=[competitor],
        )

        fetched_ds, content = await repo.get_search_dataset(ds_id)
        assert fetched_ds.dataset_id == ds_id
        assert fetched_ds.name == "Full Round Trip"
        assert fetched_ds.source == "test-suite"
        assert fetched_ds.created_at.replace(tzinfo=UTC) == ts

        k = content.keywords[0]
        assert k.keyword == "CRM comparison"
        assert k.normalized_keyword == "crm comparison"
        assert k.search_intent is SearchIntent.COMMERCIAL

        o = content.observations[0]
        assert o.keyword == "crm comparison"
        assert o.target_url == "https://oursite.io/crm"
        assert o.position == 7
        assert o.source == "manual"
        assert o.search_engine == "bing"
        assert o.country == "de"
        assert o.language == "de"
        assert o.device is SearchDevice.MOBILE
        assert o.observed_at.replace(tzinfo=UTC) == ts

        c = content.competitor_rankings[0]
        assert c.keyword == "crm comparison"
        assert c.competitor_domain == "rival.io"
        assert c.competitor_url == "https://rival.io/crm-comparison"
        assert c.position == 2
        assert c.observed_at.replace(tzinfo=UTC) == ts

    async def test_multiple_datasets_remain_isolated(self, repo):
        ds1 = SearchDataset(
            dataset_id="ds-iso-1",
            name="Dataset One",
            source="s1",
            total_keywords=0,
            total_observations=0,
        )
        ds2 = SearchDataset(
            dataset_id="ds-iso-2",
            name="Dataset Two",
            source="s2",
            total_keywords=0,
            total_observations=0,
        )
        await repo.save_search_dataset(ds1, keywords=[_kw("keyword A")])
        await repo.save_search_dataset(ds2, keywords=[_kw("keyword B")])

        _, c1 = await repo.get_search_dataset("ds-iso-1")
        _, c2 = await repo.get_search_dataset("ds-iso-2")

        assert {kw.keyword for kw in c1.keywords} == {"keyword A"}
        assert {kw.keyword for kw in c2.keywords} == {"keyword B"}

    async def test_list_search_datasets(self, repo):
        for i in range(3):
            await repo.save_search_dataset(
                SearchDataset(
                    dataset_id=f"ds-list-{i}",
                    name=f"Dataset {i}",
                    source="test",
                    total_keywords=0,
                    total_observations=0,
                )
            )
        total, datasets = await repo.list_search_datasets()
        assert total == 3
        assert len(datasets) == 3

    async def test_delete_search_dataset(self, repo):
        ds = SearchDataset(
            dataset_id="ds-del",
            name="To Delete",
            source="test",
            total_keywords=0,
            total_observations=0,
        )
        await repo.save_search_dataset(ds, keywords=[_kw()])
        result = await repo.delete_search_dataset("ds-del")
        assert result is True
        assert (await repo.get_search_dataset("ds-del")) is None

    async def test_delete_nonexistent_returns_false(self, repo):
        result = await repo.delete_search_dataset("nonexistent-id")
        assert result is False
