"""Celery application factory.

Tasks live in ``app.queue.tasks.*``; importing them here registers
each one with the app. The factory builds a fresh app on every
process start so the broker URL reflects the current ``Settings``.

Eager mode:

    Settings.celery_eager == True   →  .delay() runs the task in-process,
                                        useful for tests and `make dev`.
    Settings.celery_eager == False  →  .delay() enqueues to Redis; the
                                        worker process consumes it.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import Settings, get_settings


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
        task_always_eager=settings.celery_eager,
        task_eager_propagates=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    # Side-effect import: registers tasks with the app. We import here
    # rather than at module top to avoid a cycle with the app object.
    from app.queue.tasks import render as _render_tasks  # noqa: F401

    return app


# Process-wide instance. Workers start with
#   celery -A app.queue.celery_app:celery_app worker
celery_app = create_celery_app()
