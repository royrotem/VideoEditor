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
    """``render.run`` binds to whichever Celery app is current.

    Importing the tasks module registers the ``@shared_task`` against
    every existing Celery app. The factory itself does not import
    tasks - Celery's worker startup does that via the ``imports``
    config - so we trigger the registration explicitly in the test.
    """
    import app.queue.tasks.render

    app = create_celery_app(Settings(environment="test"))
    assert "render.run" in app.tasks
    # The factory also advertises the module so a real worker process
    # imports it at startup.
    assert "app.queue.tasks.render" in app.conf.imports
