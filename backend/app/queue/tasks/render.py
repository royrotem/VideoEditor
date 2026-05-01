"""Celery task: run a queued render job to completion.

The API enqueues this task with one argument - the ``RenderJob`` id -
and returns the pending job to the client. The worker process
re-builds every dependency from settings (DB engine, object store,
renderer, repositories) and calls :meth:`RenderJobService.execute`.

A new event loop is created per task: Celery itself is synchronous,
the rest of the app is async. ``asyncio.run`` keeps the bridge
trivial. For high-throughput workers we will switch to a long-lived
loop tied to ``worker_init`` - a ~50ms-per-job overhead is fine for
now and the simplicity is worth it.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from celery.utils.log import get_task_logger

from app.core.config import get_settings
from app.db.engine import create_engine_and_sessionmaker, dispose_engine
from app.pipeline.renderer import FFmpegRenderer
from app.queue.celery_app import celery_app
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.render_jobs import EdlVersionRepository, RenderJobRepository
from app.services.render import RenderJobService
from app.storage.s3 import S3ObjectStore

log = get_task_logger(__name__)


@celery_app.task(name="render.run", bind=True)
def run_render_job(self, job_id: str) -> dict[str, str]:
    """Worker entry point.

    Returns a small dict so the Celery result backend records the
    final status; the source of truth for the job's outcome stays the
    ``render_jobs`` row.
    """
    log.info("render-task.start", extra={"job_id": job_id})
    final_status = asyncio.run(_run(UUID(job_id)))
    log.info("render-task.done", extra={"job_id": job_id, "status": final_status})
    return {"job_id": job_id, "status": final_status}


async def _run(job_id: UUID) -> str:
    """Build dependencies, run the render, dispose, return the status."""
    settings = get_settings()
    engine, sessionmaker = create_engine_and_sessionmaker(settings)
    object_store = S3ObjectStore(settings)
    renderer = FFmpegRenderer()

    try:
        async with sessionmaker() as session:
            service = RenderJobService(
                settings=settings,
                renderer=renderer,
                object_store=object_store,
                projects=ProjectRepository(session),
                assets=AssetRepository(session),
                edl_versions=EdlVersionRepository(session),
                render_jobs=RenderJobRepository(session),
                # The worker never enqueues new tasks; it consumes them.
                enqueuer=None,
            )
            try:
                job = await service.execute(job_id)
                await session.commit()
                return job.status.value
            except Exception:
                await session.rollback()
                raise
    finally:
        await dispose_engine(engine)
