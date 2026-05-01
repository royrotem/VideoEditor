"""Queue / cache clients.

Exposes the Redis client (used as a generic cache and as the Celery
broker / result backend) and the Celery app factory. Concrete tasks
live under :mod:`app.queue.tasks`.
"""

from app.queue.celery_app import celery_app, create_celery_app
from app.queue.redis_client import create_redis_client, redis_health_check

__all__ = [
    "celery_app",
    "create_celery_app",
    "create_redis_client",
    "redis_health_check",
]
