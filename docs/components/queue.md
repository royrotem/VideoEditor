# Component: Queue / Redis + Celery

> Async Redis client used as a generic cache and as the Celery broker
> + result backend. Plus the Celery app itself, registered with one
> task today (the render worker).

## Purpose

One Redis connection per backend process, exposed as an async client
for cache reads. The same Redis instance is the broker and result
backend for Celery, so long-running work (rendering today; later
analysis, transcription) moves off the API request and onto a
dedicated worker process.

## Public interface

```python
def create_redis_client(settings: Settings) -> Redis: ...
async def redis_health_check(client: Redis) -> None: ...

def create_celery_app(settings: Settings | None = None) -> Celery: ...
celery_app: Celery   # process-wide instance built on import
```

Tasks live under `app.queue.tasks.*`. Importing
`app.queue.celery_app` triggers the side-effect import of those
modules so Celery discovers each task.

## Eager vs broker-backed

Controlled by ``Settings.celery_eager``:

| Value (default ``True``) | Behaviour                                              |
| ------------------------ | ------------------------------------------------------ |
| ``True``                 | ``.delay()`` runs the task in-process. ``make dev`` and tests use this — no separate worker required. |
| ``False``                | ``.delay()`` enqueues to Redis. Start a worker with ``make backend-worker``; ``make dev`` keeps the API on its own process. |

The API code path is identical either way - the
:class:`CeleryRenderEnqueuer` is the only thing aware of the
distinction, and it just calls ``.delay()``.

## Tasks

| Task name     | Module                     | Argument           | Purpose                                          |
| ------------- | -------------------------- | ------------------ | ------------------------------------------------ |
| ``render.run`` | ``app.queue.tasks.render`` | ``job_id: str``    | Calls :meth:`RenderJobService.execute` for the queued render job. |

The task is sync (Celery is sync); ``asyncio.run`` spans a fresh
event loop per task and tears it down with the per-task DB engine.
Per-task setup adds ~50ms - fine for now, easy to swap for
``worker_init``-shared resources later.

## Inputs

`Settings.redis_host`, `redis_port`, `redis_db`, `celery_eager`.

## Errors

`redis_health_check` raises :class:`ExternalServiceError` if `PING`
fails. Celery propagates task exceptions through the result backend;
see :doc:`services/render` for how the render task records failures
on the job row instead of relying on Celery state.

## How to test

- Bring up the `redis` service from `infra/docker-compose.yml`.
- ``backend/tests/test_celery_app.py`` covers the factory: eager by
  default, disabled when ``Settings.celery_eager=False``, render
  task is registered.
- The render task itself is exercised end-to-end via
  ``RenderJobService.execute`` in
  ``backend/tests/test_render_service.py``.

## Change log notes

- ``decode_responses=False`` so binary keys/values are safe by
  default. Decode at the call site when you actually want a string.
- The Celery worker creates its own DB engine per task (see
  ``app/queue/tasks/render.py``). Sharing engines across tasks is a
  future optimisation - keep the simpler shape until the cost
  shows up in profiles.
