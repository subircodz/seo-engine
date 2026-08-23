"""SQLAlchemy implementations of the crawl persistence ports."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sie.domain.models.crawl import (
    CrawlPageRecord,
    CrawlRunRecord,
    CrawlStatus,
)
from sie.infrastructure.models.crawl_orm import CrawlPageRow, CrawlRunRow


def _naive(aware: datetime) -> datetime:
    return aware.astimezone(UTC).replace(tzinfo=None)


def _to_aware(naive: datetime | None) -> datetime | None:
    if naive is None:
        return None
    return naive.replace(tzinfo=UTC)


class SqlAlchemyCrawlRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def create_run(self, run: CrawlRunRecord) -> None:
        async with self._sf() as session:
            session.add(
                CrawlRunRow(
                    id=run.id,
                    target_url=run.target_url,
                    status=run.status.value,
                    started_at=_naive(run.started_at),
                    policy_snapshot=dict(run.policy_snapshot),
                    total_pages=run.total_pages,
                    error_count=run.error_count,
                )
            )
            await session.commit()

    async def finish_run(
        self,
        run_id: str,
        *,
        status: CrawlStatus,
        completed_at: datetime,
        error: str | None = None,
        total_pages: int = 0,
        error_count: int = 0,
    ) -> None:
        async with self._sf() as session:
            row = await session.get(CrawlRunRow, run_id)
            if row is None:
                return
            row.status = status.value
            row.completed_at = _naive(completed_at)
            row.error = error
            row.total_pages = total_pages
            row.error_count = error_count
            await session.commit()

    async def get_run(self, run_id: str) -> CrawlRunRecord | None:
        async with self._sf() as session:
            row = await session.get(CrawlRunRow, run_id)
            if row is None:
                return None
            return CrawlRunRecord(
                id=row.id,
                target_url=row.target_url,
                status=CrawlStatus(row.status),
                started_at=_to_aware(row.started_at),
                completed_at=_to_aware(row.completed_at),
                policy_snapshot=row.policy_snapshot or {},
                error=row.error,
                total_pages=row.total_pages or 0,
                error_count=row.error_count or 0,
            )

    async def add_page(self, run_id: str, page: CrawlPageRecord) -> None:
        async with self._sf() as session:
            session.add(
                CrawlPageRow(
                    run_id=run_id,
                    url=page.url,
                    status_code=page.status_code,
                    fetched_at=_naive(page.fetched_at) if page.fetched_at is not None else None,
                    error_message=page.error_message,
                    html_size=page.html_size,
                    content_type=page.content_type,
                    depth=page.depth,
                    parent_url=page.parent_url,
                )
            )
            await session.commit()

    async def list_pages(
        self, run_id: str, *, limit: int, offset: int
    ) -> tuple[int, list[CrawlPageRecord]]:
        async with self._sf() as session:
            total = (
                await session.execute(
                    select(func.count())
                    .select_from(CrawlPageRow)
                    .where(CrawlPageRow.run_id == run_id)
                )
            ).scalar_one()
            rows = (
                (
                    await session.execute(
                        select(CrawlPageRow)
                        .where(CrawlPageRow.run_id == run_id)
                        .order_by(CrawlPageRow.id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
            return total, [self._page_record(r) for r in rows]

    @staticmethod
    def _page_record(row: CrawlPageRow) -> CrawlPageRecord:
        return CrawlPageRecord(
            url=row.url,
            status_code=row.status_code,
            fetched_at=_to_aware(row.fetched_at),
            html_size=row.html_size,
            error_message=row.error_message,
            content_type=row.content_type,
            depth=row.depth,
            parent_url=row.parent_url,
        )

    async def list_runs(
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[int, list[CrawlRunRecord]]:
        async with self._sf() as session:
            total = (
                await session.execute(select(func.count()).select_from(CrawlRunRow))
            ).scalar_one()
            rows = (
                await session.execute(
                    select(CrawlRunRow)
                    .order_by(CrawlRunRow.started_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
            ).scalars()
            return total, [self._run_record(r) for r in rows]

    @staticmethod
    def _run_record(row: CrawlRunRow) -> CrawlRunRecord:
        return CrawlRunRecord(
            id=row.id,
            target_url=row.target_url,
            status=CrawlStatus(row.status),
            started_at=_to_aware(row.started_at) or row.started_at.replace(tzinfo=UTC),
            completed_at=_to_aware(row.completed_at),
            policy_snapshot=row.policy_snapshot or {},
            error=row.error,
            total_pages=row.total_pages or 0,
            error_count=row.error_count or 0,
        )
