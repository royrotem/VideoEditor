"""HTTP routes for render submission and inspection."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, Query, status

from app.api.deps import ObjectStoreDep, RenderServiceDep
from app.schemas.render import RenderJobRead, RenderOutputUrl, SubmitRenderBody

router = APIRouter(tags=["render"])

# Default lifetime for the presigned playback URL of a finished render.
DEFAULT_OUTPUT_TTL_SECONDS = 3600


@router.post(
    "/projects/{project_id}/render",
    response_model=RenderJobRead,
    status_code=status.HTTP_201_CREATED,
)
async def submit_render(
    body: SubmitRenderBody,
    service: RenderServiceDep,
    project_id: UUID = Path(...),
) -> RenderJobRead:
    """Submit an EDL for rendering.

    Today the render runs inline before the response - which is why
    the returned job already has a terminal ``status`` (``succeeded``
    or ``failed``). Once rendering moves to a Celery worker the route
    will return a ``pending`` job and the client will poll
    ``GET /render-jobs/{id}`` until ``status != pending``.
    """
    job = await service.submit(
        project_id=project_id,
        edl=body.edl,
        session_id=body.session_id,
    )
    return RenderJobRead.model_validate(job)


@router.get(
    "/projects/{project_id}/render-jobs",
    response_model=list[RenderJobRead],
)
async def list_render_jobs(
    service: RenderServiceDep,
    project_id: UUID = Path(...),
) -> list[RenderJobRead]:
    rows = await service.list_for_project(project_id)
    return [RenderJobRead.model_validate(row) for row in rows]


@router.get(
    "/render-jobs/{job_id}",
    response_model=RenderJobRead,
)
async def get_render_job(
    service: RenderServiceDep,
    job_id: UUID = Path(...),
) -> RenderJobRead:
    job = await service.get(job_id)
    return RenderJobRead.model_validate(job)


@router.get(
    "/render-jobs/{job_id}/output-url",
    response_model=RenderOutputUrl,
)
async def get_render_output_url(
    service: RenderServiceDep,
    object_store: ObjectStoreDep,
    job_id: UUID = Path(...),
    ttl_seconds: int = Query(
        default=DEFAULT_OUTPUT_TTL_SECONDS, ge=60, le=86_400
    ),
) -> RenderOutputUrl:
    """Return a short-lived URL the client can stream the render from.

    Returns 404 when the job has not produced an output yet (job is
    still ``pending``/``running`` or has ``failed``).
    """
    job = await service.get(job_id)
    if job.output_bucket is None or job.output_key is None:
        from app.core.errors import NotFoundError

        raise NotFoundError(
            f"render job {job_id} has no output (status={job.status})"
        )
    url = await object_store.presigned_get_url(
        job.output_bucket, job.output_key, ttl_seconds=ttl_seconds
    )
    return RenderOutputUrl(url=url, ttl_seconds=ttl_seconds)
