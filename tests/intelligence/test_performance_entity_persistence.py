"""Persistence round-trip tests for Performance, Entity, and Optimization (Phase 8).

These tests verify that the ORM models and repository serialization/deserialization
work correctly using an in-memory SQLite database.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sie.infrastructure.models.search_performance_entity_orm import (
    EntitySignalRow,
    OptimizationRecommendationRow,
    PerformanceFindingRow,
)
from sie.infrastructure.persistence.database import Base


@pytest.fixture
def engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:")


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ════════════════════════════════════════════════════════════════════════════
# Performance Finding persistence
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestPerformanceFindingPersistence:
    async def test_save_and_retrieve(self, session_factory, setup_db):
        from datetime import UTC, datetime

        async with session_factory() as session:
            row = PerformanceFindingRow(
                dataset_id="ds1",
                url="http://example.com",
                metric_name="html_size",
                severity="high",
                value=200000.0,
                threshold=100000.0,
                description="HTML is large",
                recommendation="Minify HTML",
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            stmt = select(PerformanceFindingRow).where(PerformanceFindingRow.dataset_id == "ds1")
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].url == "http://example.com"
            assert rows[0].metric_name == "html_size"
            assert rows[0].severity == "high"
            assert rows[0].value == 200000.0

    async def test_empty_dataset(self, session_factory, setup_db):
        from sqlalchemy import select

        async with session_factory() as session:
            stmt = select(PerformanceFindingRow).where(
                PerformanceFindingRow.dataset_id == "nonexistent"
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 0


# ════════════════════════════════════════════════════════════════════════════
# Entity Signal persistence
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestEntitySignalPersistence:
    async def test_save_and_retrieve(self, session_factory, setup_db):
        from datetime import UTC, datetime

        async with session_factory() as session:
            row = EntitySignalRow(
                dataset_id="ds1",
                keyword="test query",
                entity_text="Acme Corp",
                category="organization",
                frequency=5,
                is_target=1,
                domain="acme.com",
                confidence=0.8,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            stmt = select(EntitySignalRow).where(EntitySignalRow.dataset_id == "ds1")
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].entity_text == "Acme Corp"
            assert rows[0].frequency == 5
            assert rows[0].is_target == 1

    async def test_multiple_signals(self, session_factory, setup_db):
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        async with session_factory() as session:
            for i in range(5):
                session.add(
                    EntitySignalRow(
                        dataset_id="ds1",
                        keyword="kw1",
                        entity_text=f"Entity{i}",
                        category="concept",
                        frequency=i + 1,
                        is_target=0,
                        domain="",
                        confidence=0.5,
                        created_at=now,
                    )
                )
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            stmt = select(EntitySignalRow).where(EntitySignalRow.dataset_id == "ds1")
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 5


# ════════════════════════════════════════════════════════════════════════════
# Optimization Recommendation persistence
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
class TestOptimizationRecommendationPersistence:
    async def test_save_and_retrieve(self, session_factory, setup_db):
        from datetime import UTC, datetime

        async with session_factory() as session:
            row = OptimizationRecommendationRow(
                dataset_id="ds1",
                category="content",
                title="Create new content",
                description="Fill content gaps",
                impact="high",
                effort="medium",
                priority_score=0.6,
                affected_keywords=["kw1", "kw2"],
                affected_urls=["http://a.com"],
                confidence=0.8,
                source_engine="optimization",
                created_at=datetime.now(UTC),
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            stmt = select(OptimizationRecommendationRow).where(
                OptimizationRecommendationRow.dataset_id == "ds1"
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].category == "content"
            assert rows[0].priority_score == 0.6
            assert rows[0].affected_keywords == ["kw1", "kw2"]

    async def test_empty_recommendations(self, session_factory, setup_db):
        from sqlalchemy import select

        async with session_factory() as session:
            stmt = select(OptimizationRecommendationRow).where(
                OptimizationRecommendationRow.dataset_id == "nonexistent"
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 0
