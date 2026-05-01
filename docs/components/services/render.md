# Component: Services / RenderJobService

> Orchestrates one render request end-to-end: persist the EDL, create
> a job row, validate, download, render, upload, and update the job.

## Purpose

Connect the pieces. Routes call into :meth:`RenderJobService.submit`
with a project id and an :class:`EditDecisionList`; the service
handles the rest. This is the only component that knows about every
piece of the pipeline at once.

## Flow

```
submit(project_id, edl)
  ├── projects.get(project_id)                    # 404 if unknown
  ├── edl_versions.insert(...)                    # immutable, monotonic
  ├── render_jobs.create(...)                     # status=pending
  ├── _validate(edl)                              # EdlValidator
  │     └── on errors → render_jobs.mark_failed(error_message=...)
  ├── render_jobs.mark_running(...)
  ├── _render_and_publish(...)
  │     ├── tempfile.mkdtemp(prefix="render-")
  │     ├── object_store.get(asset.s3_bucket, asset.s3_key)  # per asset
  │     ├── renderer.render(RenderInput(...))
  │     ├── object_store.put(renders_bucket, "<project>/<job>.<ext>")
  │     ├── render_jobs.mark_succeeded(output_bucket, output_key)
  │     └── shutil.rmtree(scratch)                 # always
  └── on AppError / unexpected exception → render_jobs.mark_failed
```

The service catches errors at the outer layer so callers always
receive a final :class:`RenderJob` row; pre-render validation
failures are recorded as ``failed`` (not raised) so the UI can show
the issues.

## Public interface

```python
class RenderJobService:
    async def submit(self, *, project_id: UUID, edl: EditDecisionList,
                     session_id: UUID | None = None) -> RenderJob: ...
    async def get(self, job_id: UUID) -> RenderJob: ...
    async def list_for_project(self, project_id: UUID) -> list[RenderJob]: ...
```

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

- The render runs **inline** today. Moving it onto a Celery worker is
  a swap of one dependency: build a Celery task that takes
  ``(project_id, edl_version_id)``, retrieves the EDL JSON from the
  ``edl_versions`` row, and calls the same ``_render_and_publish``
  helper. The route stays the same (``submit`` returns ``pending``
  instead of a final state) and the rest of the system is untouched.
- The scratch directory is removed even on failure; ``ffmpeg``
  partial outputs are cleaned up by the renderer itself.
