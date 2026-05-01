# Component: API / Render

> Submit an :class:`EditDecisionList` for rendering, inspect the job,
> and fetch a short-lived URL to play back the output. The end-to-end
> seam between the agent network and the deterministic pipeline.

## Purpose

Expose :class:`RenderJobService` over HTTP. Routes are thin: parse
the input, delegate to the service, return the resulting
:class:`RenderJob`. The service itself owns validation, asset
download, ffmpeg invocation, MinIO upload, and DB writes -
documented in [`services/render.md`](../services/render.md).

## Public interface

| Method | Path                                   | Body / Query             | Response                |
| ------ | -------------------------------------- | ------------------------ | ----------------------- |
| POST   | `/projects/{id}/render`                | `SubmitRenderBody`       | `RenderJobRead` 201     |
| GET    | `/projects/{id}/render-jobs`           | -                        | `list[RenderJobRead]`   |
| GET    | `/render-jobs/{job_id}`                | -                        | `RenderJobRead`         |
| GET    | `/render-jobs/{job_id}/output-url`     | `ttl_seconds`            | `RenderOutputUrl`       |

Schemas live in `backend/app/schemas/render.py`.

## Inputs / outputs

`SubmitRenderBody` carries the full :class:`EditDecisionList` and an
optional ``session_id`` (the chat session that produced it). The
service persists the EDL as a new ``edl_versions`` row before
rendering, so the client does not need to pre-create the version.

The returned :class:`RenderJobRead` always reports the job's terminal
state today (``succeeded`` or ``failed``) because rendering runs
inline. When rendering moves to a Celery worker the route will
return ``pending`` and the client will poll
``GET /render-jobs/{id}`` until ``status != pending``.

`output-url` returns a presigned MinIO/S3 URL the client can use to
stream the rendered file directly. TTL is configurable between 60s
and 24h (default 1h). The route returns 404 if the job has not
produced an output yet.

## Errors

| Error                     | When                                   | HTTP |
| ------------------------- | -------------------------------------- | ---- |
| `resource.not_found`      | Project, job, or output is unknown     | 404  |
| `validation.failed`       | Request body fails Pydantic validation | 422  |
| `external.failed`         | MinIO presign failure                  | 502  |

Pipeline failures (validation against assets, ffmpeg crash, upload
errors) surface inside the returned :class:`RenderJobRead` row
(``status = failed``, ``error_message`` populated) - never as 5xx.
The client renders both states with the same UI.

## How to test

- HTTP: `backend/tests/test_routes_render.py` covers the happy path,
  validation-driven failure (no asset → ``failed`` job),
  fetch-by-id, list-for-project, presigned output URL on success,
  404 on missing output, and unknown-project 404. Uses
  ``dependency_overrides`` for repos, store, probe, and renderer.
- Service-level coverage lives in `test_render_service.py`.

## Change log notes

- The route returns 201 even when the job ended up ``failed`` -
  failure is a *result*, not an HTTP error. The client checks
  ``status``.
- ``output-url`` is a separate call (rather than embedded on the job
  response) because the URL is short-lived and we don't want it to
  be cached anywhere a long-running job listing might end up.
