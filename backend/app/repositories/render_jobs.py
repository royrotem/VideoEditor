"""SQLAlchemy queries for the ``render_jobs`` and ``edl_versions`` tables."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.enums import JobStatus
from app.db.models import EdlVersion, RenderJob


class EdlVersionRepository:
    """Append-only access to ``edl_versions``.

    Versions are immutable - amendments produce a new row, never an
    UPDATE. The repository enforces this by exposing only ``insert``
    and read operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def insert(
        self,
        *,
        project_id: UUID,
        edl: dict[str, Any],
        session_id: UUID | None = None,
    ) -> EdlVersion:
        next_version = await self._next_version(project_id)
        row = EdlVersion(
            project_id=project_id,
            version_number=next_version,
            edl=edl,
            session_id=session_id,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def get(self, edl_version_id: UUID) -> EdlVersion:
        row = await self._db.get(EdlVersion, edl_version_id)
        if row is None:
            raise NotFoundError(f"edl_version {edl_version_id} not found")
        return row

    async def latest_for_project(self, project_id: UUID) -> EdlVersion | None:
        result = await self._db.execute(
            select(EdlVersion)
            .where(EdlVersion.project_id == project_id)
            .order_by(EdlVersion.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _next_version(self, project_id: UUID) -> int:
        result = await self._db.execute(
            select(func.coalesce(func.max(EdlVersion.version_number), 0)).where(
                EdlVersion.project_id == project_id
            )
        )
        return int(result.scalar_one()) + 1


class RenderJobRepository:
    """Data-access for :class:`~app.db.models.RenderJob`."""

    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    async def create(
        self, *, project_id: UUID, edl_version_id: UUID
    ) -> RenderJob:
        job = RenderJob(
            project_id=project_id,
            edl_version_id=edl_version_id,
            status=JobStatus.PENDING,
        )
        self._db.add(job)
        await self._db.flush()
        return job

    async def get(self, job_id: UUID) -> RenderJob:
        job = await self._db.get(RenderJob, job_id)
        if job is None:
            raise NotFoundError(f"render_job {job_id} not found")
        return job

    async def mark_running(self, job_id: UUID) -> RenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.RUNNING
        await self._db.flush()
        return job

    async def mark_succeeded(
        self, job_id: UUID, *, output_bucket: str, output_key: str
    ) -> RenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.SUCCEEDED
        job.output_bucket = output_bucket
        job.output_key = output_key
        job.error_message = None
        await self._db.flush()
        return job

    async def mark_failed(
        self, job_id: UUID, *, error_message: str
    ) -> RenderJob:
        job = await self.get(job_id)
        job.status = JobStatus.FAILED
        job.error_message = error_message
        await self._db.flush()
        return job

    async def list_for_project(self, project_id: UUID) -> list[RenderJob]:
        result = await self._db.execute(
            select(RenderJob)
            .where(RenderJob.project_id == project_id)
            .order_by(RenderJob.created_at.desc())
        )
        return list(result.scalars())
