"""Celery application factory.

The Celery app is configured once per process; tasks register
themselves against it via :func:`celery.shared_task` so this module
and ``app.queue.tasks.*`` are not coupled by an import cycle.

Two lifecycles to keep in mind:

- **Worker process** (``celery -A app.queue.celery_app:celery_app
  worker``) — Celery reads the ``imports`` config and imports each
  task module at startup, registering every ``@shared_task``.
- **API process** — when :class:`CeleryRenderEnqueuer.enqueue` calls
  ``.delay()`` it imports the task module on demand. With
  ``task_always_eager=True`` (default for ``make dev`` and tests)
  the call runs the task in-process.

Eager mode:

    Settings.celery_eager == True   →  .delay() runs the task in-process,
                                        useful for tests and `make dev`.
    Settings.celery_eager == False  →  .delay() enqueues to Redis; the
                                        worker process consumes it.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings, get_settings

# Modules under this list are imported by Celery at worker startup so
# every ``@shared_task`` decorated function is registered with the app.
# Keep it in sync with new task modules.
TASK_MODULES = ["app.queue.tasks.render"]


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Build a Celery app bound to ``settings`` (or the cached one).

    The instance is intentionally not cached - tests want to build a
    fresh one with overridden settings without poking at module
    state.
    """
    settings = settings or get_settings()
    app = Celery(
        "ai_video_editor",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    app.conf.update(
        imports=TASK_MODULES,
        task_always_eager=settings.celery_eager,
        task_eager_propagates=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


# Process-wide instance. Workers start with
#   celery -A app.queue.celery_app:celery_app worker
celery_app = create_celery_app()
