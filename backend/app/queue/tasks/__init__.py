"""Celery task modules.

Each module under this package registers one or more tasks against
:data:`app.queue.celery_app.celery_app`. Importing this package via
the celery app's side-effect import is what makes the worker
discover them.
"""
