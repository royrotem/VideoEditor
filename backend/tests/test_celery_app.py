"""Smoke tests for the Celery app factory.

The render task itself is exercised end-to-end by
``test_render_service.py`` via :meth:`RenderJobService.execute`; this
file just verifies the task is registered and that eager mode is
the default (so tests / `make dev` never accidentally rely on a
running worker).
"""

from __future__ import annotations

from app.core.config import Settings
from app.queue.celery_app import create_celery_app


def test_factory_returns_eager_app_by_default() -> None:
    app = create_celery_app(Settings(environment="test"))
    assert app.conf.task_always_eager is True
    assert app.conf.task_eager_propagates is True


def test_factory_disables_eager_when_settings_say_so() -> None:
    app = create_celery_app(Settings(environment="prod", celery_eager=False))
    assert app.conf.task_always_eager is False


def test_render_task_is_registered() -> None:
    app = create_celery_app(Settings(environment="test"))
    # The register-on-import side effect runs when the factory imports
    # the tasks module; the canonical name is ``render.run``.
    assert "render.run" in app.tasks
