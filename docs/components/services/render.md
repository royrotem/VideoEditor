# Component: Services / RenderJobService

> Orchestrates one render request end-to-end: persist the EDL, create
> a job row, validate, download, render, upload, and update the job.

## Purpose

Connect the pieces. Routes call into :meth:`RenderJobService.submit`
with a project id and an :class:`EditDecisionList`; the service
handles the rest. This is the only component that knows about every
piece of the pipeline at once.

## Flow

The lifecycle is split across two methods:

```
# API process
submit(project_id, edl)
  ├── projects.get(project_id)                  # 404 if unknown
  ├── edl_versions.insert(...)                  # immutable, monotonic
  ├── render_jobs.create(...)                   # status=pending
  ├── enqueuer.enqueue(job.id)                  # CeleryRenderEnqueuer
  └── return pending job

# Celery worker process (or in-process when celery_eager=True)
execute(job_id)
  ├── render_jobs.get(job_id)
  ├── edl_versions.get(job.edl_version_id)
  ├── _validate(edl)                            # EdlValidator
  │     └── on errors → render_jobs.mark_failed(error_message=...)
  ├── render_jobs.mark_running(...)
  ├── _render_and_publish(...)
  │     ├── tempfile.mkdtemp(prefix="render-")
  │     ├── object_store.get(asset.s3_bucket, asset.s3_key)  # per asset
  │     ├── renderer.render(RenderInput(...))
  │     ├── object_store.put(renders_bucket, "<project>/<job>.<ext>")
  │     ├── render_jobs.mark_succeeded(output_bucket, output_key)
  │     └── shutil.rmtree(scratch)               # always
  └── on AppError / unexpected exception → render_jobs.mark_failed
```

The split lets the API return immediately with a ``pending`` job
while the actual rendering runs on a dedicated worker process. Pre-
render validation failures are recorded as ``failed`` on the job row
(not raised) so the UI can show issues without parsing 5xx bodies.

## Public interface

```python
class TaskEnqueuer:
    """Pluggable transport for "enqueue a render task by job id"."""
    async def enqueue(self, job_id: UUID) -> None: ...

class RenderJobService:
    async def submit(self, *, project_id, edl, session_id=None) -> RenderJob: ...
    async def execute(self, job_id: UUID) -> RenderJob: ...
    async def get(self, job_id: UUID) -> RenderJob: ...
    async def list_for_project(self, project_id: UUID) -> list[RenderJob]: ...
```

Concrete enqueuers live in :mod:`app.services.render_enqueuer`:

- :class:`CeleryRenderEnqueuer` — production. Calls
  ``run_render_job.delay(...)`` so the worker (or eager-mode in-
  process Celery) picks it up.
- :class:`RecordingRenderEnqueuer` — test helper that just records
  every job id it was asked to enqueue.
- :class:`ImmediateRenderEnqueuer` — test helper that runs
  ``await service.execute(job_id)`` inline against a callable, used
  by HTTP-level tests to drive submit → execute on the same fakes.

## Inputs / outputs

- ``project_id`` must reference an existing project.
- ``edl.version`` is advisory; the persisted ``edl_versions``
  ``version_number`` is auto-incremented per project. The EDL JSON is
  stored verbatim regardless.
- The output object is uploaded to
  ``<s3_bucket_renders>/<project_id>/<job_id>.<container>``.
- The returned :class:`RenderJob` row has ``status ∈ {succeeded,
  failed}``.

## Dependencies

- :class:`Renderer` (default :class:`FFmpegRenderer`).
- :class:`ObjectStore` (production: :class:`S3ObjectStore` against MinIO).
- :class:`EdlValidator` (built fresh per submit).
- Repositories: project, asset, edl_version, render_job.

## Errors

| Caller-visible exception | When                                             |
| ------------------------ | ------------------------------------------------ |
| :class:`NotFoundError`   | Project id is unknown                            |

Pipeline failures (validation, render, upload) surface inside the
returned :class:`RenderJob` row (``status = failed``,
``error_message`` populated) - not as exceptions.

## How to test

- ``backend/tests/test_render_service.py`` covers happy path, pre-
  render validation failure, renderer exception handling, monotonic
  version assignment, and the unknown-project 404.

## Change log notes

- Rendering runs on a **Celery worker** in production
  (``celery_eager=False``). With ``celery_eager=True`` (the default
  for ``make dev`` and tests) the task runs in the API process so
  no separate worker is needed for development. See
  [`docs/components/queue.md`](../queue.md) for the broker and
  worker mechanics.
- ``submit`` returns the ``pending`` job; the frontend polls
  ``/render-jobs/{id}`` (every 4s in
  [`docs/components/frontend/chat-pages.md`](../frontend/chat-pages.md))
  until it reaches a terminal status.
- The scratch directory is removed even on failure; ``ffmpeg``
  partial outputs are cleaned up by the renderer itself.
