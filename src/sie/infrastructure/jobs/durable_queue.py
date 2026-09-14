"""Database-backed durable background job queue.

The queue stores only JSON-serializable task type/payload data. Workers claim
jobs with leases so a process crash does not permanently strand work.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None] | dict[str, Any] | None]

__all__ = ["DurableJobQueue", "JobNotFoundError"]


class JobNotFoundError(KeyError):
    """Requested job does not exist."""


class DurableJobQueue:
    """Durable queue using the application's existing SQL database."""

    def __init__(self, session_factory: async_sessionmaker, *, lease_seconds: int = 300, max_attempts: int = 3) -> None:
        if lease_seconds < 30:
            raise ValueError("lease_seconds must be at least 30 seconds")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._session_factory = session_factory
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._handlers: dict[str, JobHandler] = {}

    def register(self, task_type: str, handler: JobHandler) -> None:
        if not task_type.strip():
            raise ValueError("task_type must not be empty")
        if task_type in self._handlers:
            raise ValueError(f"Handler already registered for {task_type!r}")
        self._handlers[task_type] = handler

    async def enqueue(
        self,
        task_type: str,
        payload: dict[str, Any],
        *,
        available_at: datetime | None = None,
        max_attempts: int | None = None,
    ) -> str:
        if not task_type.strip():
            raise ValueError("task_type must not be empty")
        if max_attempts is not None and max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        available = available_at or now
        effective_max_attempts = self._max_attempts if max_attempts is None else max_attempts
        async with self._session_factory() as session:
            await session.execute(
                text("""INSERT INTO background_jobs
                    (id, task_type, payload, status, attempts, max_attempts,
                     available_at, created_at)
                    VALUES (:id, :task_type, :payload, 'queued', 0, :max_attempts,
                            :available_at, :created_at)"""),
                {
                    "id": job_id,
                    "task_type": task_type,
                    "payload": payload,
                    "max_attempts": effective_max_attempts,
                    "available_at": available,
                    "created_at": now,
                },
            )
            await session.commit()
        return job_id

    async def get(self, job_id: str) -> dict[str, Any]:
        async with self._session_factory() as session:
            result = await session.execute(text("SELECT * FROM background_jobs WHERE id = :id"), {"id": job_id})
            row = result.mappings().first()
        if row is None:
            raise JobNotFoundError(job_id)
        return dict(row)

    async def recover_expired(self) -> int:
        """Recover expired leases without exceeding the retry budget."""
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            result = await session.execute(
                text("""UPDATE background_jobs
                       SET status=CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END,
                           worker_id=NULL, leased_until=NULL,
                           completed_at=CASE WHEN attempts >= max_attempts THEN :completed_at ELSE NULL END,
                           last_error=CASE
                               WHEN attempts >= max_attempts THEN COALESCE(last_error, 'worker lease expired')
                               ELSE last_error
                           END
                     WHERE status='running' AND leased_until IS NOT NULL
                       AND leased_until < :now"""),
                {"now": now, "completed_at": now},
            )
            await session.commit()
            return result.rowcount or 0

    async def claim(self, worker_id: str) -> dict[str, Any] | None:
        """Atomically claim one available job and establish a lease."""
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        now = datetime.now(UTC)
        lease = now + timedelta(seconds=self._lease_seconds)
        async with self._session_factory() as session:
            dialect = session.bind.dialect.name if session.bind is not None else ""
            if dialect == "postgresql":
                query = text("""SELECT id FROM background_jobs
                       WHERE (status='queued' OR (status='running' AND leased_until < :now))
                         AND available_at <= :now AND attempts < max_attempts
                       ORDER BY available_at, created_at
                       FOR UPDATE SKIP LOCKED LIMIT 1""")
            else:
                query = text("""SELECT id FROM background_jobs
                       WHERE (status='queued' OR (status='running' AND leased_until < :now))
                         AND available_at <= :now AND attempts < max_attempts
                       ORDER BY available_at, created_at LIMIT 1""")
            result = await session.execute(query, {"now": now})
            row = result.mappings().first()
            if row is None:
                await session.rollback()
                return None
            job_id = row["id"]
            updated = await session.execute(
                text("""UPDATE background_jobs
                       SET status='running', attempts=attempts+1,
                           worker_id=:worker_id, leased_until=:leased_until,
                           started_at=COALESCE(started_at, :started_at), last_error=NULL
                     WHERE id=:id AND (status='queued' OR leased_until < :now)
                       AND attempts < max_attempts"""),
                {
                    "id": job_id,
                    "worker_id": worker_id,
                    "leased_until": lease,
                    "started_at": now,
                    "now": now,
                },
            )
            if updated.rowcount != 1:
                await session.rollback()
                return None
            await session.commit()
        return await self.get(job_id)

    async def complete(self, job_id: str, result: dict[str, Any] | None = None, *, worker_id: str) -> bool:
        """Complete a job only if this worker still owns its active lease."""
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            updated = await session.execute(
                text("""UPDATE background_jobs
                       SET status='completed', result=:result, completed_at=:completed_at,
                           leased_until=NULL, worker_id=NULL
                     WHERE id=:id AND status='running' AND worker_id=:worker_id
                       AND leased_until IS NOT NULL AND leased_until >= :now"""),
                {"id": job_id, "worker_id": worker_id, "result": result, "completed_at": now, "now": now},
            )
            await session.commit()
            return updated.rowcount == 1

    async def fail(self, job_id: str, error: str, *, retry: bool = True, worker_id: str) -> None:
        """Fail or requeue a job only if this worker still owns its active lease."""
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    text("SELECT attempts, max_attempts FROM background_jobs WHERE id=:id AND status='running' AND worker_id=:worker_id"),
                    {"id": job_id, "worker_id": worker_id},
                )
            ).mappings().first()
            if row is None:
                return
            terminal = not retry or int(row["attempts"]) >= int(row["max_attempts"])
            await session.execute(
                text("""UPDATE background_jobs
                       SET status=:status, last_error=:error, leased_until=NULL, worker_id=NULL,
                           completed_at=:completed_at
                     WHERE id=:id AND status='running' AND worker_id=:worker_id"""),
                {
                    "id": job_id,
                    "worker_id": worker_id,
                    "status": "failed" if terminal else "queued",
                    "error": error[:8000],
                    "completed_at": now if terminal else None,
                },
            )
            await session.commit()

    async def run_worker(
        self,
        worker_id: str,
        *,
        poll_interval_seconds: float = 1.0,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Run a durable worker loop until ``stop_event`` is set."""
        stop_event = stop_event or asyncio.Event()
        while not stop_event.is_set():
            await self.recover_expired()
            job = await self.claim(worker_id)
            if job is None:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_interval_seconds)
                continue
            handler = self._handlers.get(job["task_type"])
            if handler is None:
                await self.fail(
                    job["id"],
                    f"No handler registered for task type {job['task_type']!r}",
                    retry=False,
                    worker_id=worker_id,
                )
                continue
            try:
                value = handler(job["payload"])
                if inspect.isawaitable(value):
                    value = await value
                await self.complete(job["id"], value if isinstance(value, dict) else None, worker_id=worker_id)
            except Exception as exc:
                await self.fail(job["id"], f"{type(exc).__name__}: {exc}", worker_id=worker_id)
