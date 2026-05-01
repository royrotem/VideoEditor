"""Concrete :class:`TaskEnqueuer` implementations.

The service-level abstraction lives in ``app.services.render``;
this module wires it to actual task transports so the service stays
free of Celery imports.

- :class:`CeleryRenderEnqueuer` calls ``run_render_job.delay(...)``.
  When ``Settings.celery_eager`` is true the task runs in-process
  (great for ``make dev`` and tests); otherwise it lands on the
  Redis broker for the worker to pick up.
- :class:`RecordingRenderEnqueuer` is the test-friendly variant that
  records calls without touching Celery at all.
- :class:`ImmediateRenderEnqueuer` runs an ``await service.execute``
  inline so HTTP-level tests can drive submit → execute on the same
  in-memory fakes.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID

from app.services.render import TaskEnqueuer

AsyncJobCallable = Callable[[UUID], Awaitable[None]]


class CeleryRenderEnqueuer(TaskEnqueuer):
    """Production enqueuer; delegates to the Celery render task.

    The Celery task is synchronous (``celery.task`` decorates a sync
    function). We dispatch ``.delay`` via :func:`asyncio.to_thread`
    to keep the FastAPI event loop unblocked while Redis acks the
    broker publish - a few milliseconds, but the "no sync work on
    the loop" rule is worth keeping.
    """

    async def enqueue(self, job_id: UUID) -> None:
        # Imported lazily so the service module stays Celery-free.
        from app.queue.tasks.render import run_render_job

        await asyncio.to_thread(run_render_job.delay, str(job_id))


class RecordingRenderEnqueuer(TaskEnqueuer):
    """Records every enqueue call; used by tests."""

    def __init__(self) -> None:
        self.calls: list[UUID] = []

    async def enqueue(self, job_id: UUID) -> None:
        self.calls.append(job_id)


class ImmediateRenderEnqueuer(TaskEnqueuer):
    """Test enqueuer that runs the executor inline.

    Wraps a callable that does ``await service.execute(job_id)`` so
    HTTP-level tests can drive the full submit → execute flow on
    the same in-memory fakes the route uses.
    """

    def __init__(self, run: AsyncJobCallable) -> None:
        self._run = run

    async def enqueue(self, job_id: UUID) -> None:
        await self._run(job_id)
