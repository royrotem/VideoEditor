"""End-to-end render orchestration.

Two responsibilities, each its own method:

- :meth:`RenderJobService.submit` runs in the API request: it
  persists the EDL as a new :class:`EdlVersion`, creates a
  :class:`RenderJob` row in ``pending`` state, and enqueues the
  worker task. Returns immediately with the pending job.
- :meth:`RenderJobService.execute` runs in the Celery worker (or
  inline when ``Settings.celery_eager`` is true): it loads the EDL
  back from the DB, validates against the project's assets,
  downloads the referenced asset bytes, invokes the renderer,
  uploads the result to MinIO, and finalises the job row.

Splitting the lifecycle this way means the service is the single
seam between the API request, the worker, and the agent network -
nothing else needs to know whether rendering is sync or async.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from app.agents.contracts import EditDecisionList
from app.core.config import Settings
from app.core.errors import AppError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.models import RenderJob
from app.pipeline.edl_validator import (
    AssetSpec,
    EdlValidator,
    ValidationReport,
)
from app.pipeline.renderer import Renderer, RenderInput
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.render_jobs import EdlVersionRepository, RenderJobRepository
from app.storage.base import ObjectStore


class TaskEnqueuer:
    """Tiny abstraction for "enqueue a render task by job id".

    Lives here so the service can be unit-tested without importing
    Celery. Production wires :class:`CeleryRenderEnqueuer`; tests
    can pass a fake that records calls or runs the executor inline.

    ``enqueue`` is async so test enqueuers can ``await
    service.execute(...)`` directly inside FastAPI's running loop;
    a sync method would force a nested ``asyncio.run`` and error
    out.
    """

    async def enqueue(self, job_id: UUID) -> None:  # pragma: no cover - protocol stub
        raise NotImplementedError


class RenderJobService:
    """Persists and executes one render request end-to-end."""

    def __init__(
        self,
        *,
        settings: Settings,
        renderer: Renderer,
        object_store: ObjectStore,
        projects: ProjectRepository,
        assets: AssetRepository,
        edl_versions: EdlVersionRepository,
        render_jobs: RenderJobRepository,
        enqueuer: TaskEnqueuer | None = None,
    ) -> None:
        self._settings = settings
        self._renderer = renderer
        self._object_store = object_store
        self._projects = projects
        self._assets = assets
        self._edl_versions = edl_versions
        self._render_jobs = render_jobs
        self._enqueuer = enqueuer
        self._log = get_logger("services.render")

    # --- API-side: persist + enqueue ------------------------------------

    async def submit(
        self,
        *,
        project_id: UUID,
        edl: EditDecisionList,
        session_id: UUID | None = None,
    ) -> RenderJob:
        """Persist the EDL, create a pending job, enqueue the worker.

        Returns immediately with the ``pending`` job. The actual
        render runs in the worker (or inline when
        :class:`TaskEnqueuer` is configured eager).
        """
        await self._projects.get(project_id)

        edl_version = await self._edl_versions.insert(
            project_id=project_id,
            edl=edl.model_dump(mode="json"),
            session_id=session_id,
        )
        job = await self._render_jobs.create(project_id=project_id, edl_version_id=edl_version.id)

        if self._enqueuer is not None:
            await self._enqueuer.enqueue(job.id)
            self._log.info("render.enqueued", job_id=str(job.id))

        return job

    # --- Worker-side: do the actual work --------------------------------

    async def execute(self, job_id: UUID) -> RenderJob:
        """Run the render for an existing ``pending`` job.

        Validates against the project's assets, downloads bytes,
        invokes the renderer, uploads, and writes the terminal
        status. Pre-render validation failures are recorded as
        ``failed`` (with a structured ``error_message``) rather than
        raised - the caller wants to display issues, not handle 5xx.
        """
        job = await self._render_jobs.get(job_id)
        edl_version = await self._edl_versions.get(job.edl_version_id)
        edl = EditDecisionList.model_validate(edl_version.edl)

        validation = await self._validate(job.project_id, edl)
        if not validation.ok:
            return await self._render_jobs.mark_failed(job.id, error_message=_summarise(validation))

        await self._render_jobs.mark_running(job.id)

        try:
            return await self._render_and_publish(job.project_id, job.id, edl)
        except AppError as exc:
            self._log.warning("render.failed", job_id=str(job.id), error=exc.message)
            return await self._render_jobs.mark_failed(job.id, error_message=exc.message)
        except Exception as exc:
            self._log.exception("render.crashed", job_id=str(job.id))
            return await self._render_jobs.mark_failed(
                job.id, error_message=f"unexpected error: {exc}"
            )

    # --- Read paths used by routes --------------------------------------

    async def list_for_project(self, project_id: UUID) -> list[RenderJob]:
        await self._projects.get(project_id)
        return await self._render_jobs.list_for_project(project_id)

    async def get(self, job_id: UUID) -> RenderJob:
        return await self._render_jobs.get(job_id)

    # --- Internals -------------------------------------------------------

    async def _validate(self, project_id: UUID, edl: EditDecisionList) -> ValidationReport:
        """Run :class:`EdlValidator` over ``edl`` against project assets.

        Note: we do not pass ``previous_version`` to the validator -
        :meth:`EdlVersionRepository.insert` owns version assignment in
        this flow, so the version field on the incoming EDL is
        advisory and the validator's monotonicity rule is redundant
        here. (It is still useful when an EDL is round-tripped
        externally - e.g. imported - which is why the validator
        keeps the option.)
        """
        rows = await self._assets.list_for_project(project_id)
        validator = EdlValidator(AssetSpec.from_asset_row(a) for a in rows)
        return validator.validate(edl)

    async def _render_and_publish(
        self,
        project_id: UUID,
        job_id: UUID,
        edl: EditDecisionList,
    ) -> RenderJob:
        scratch = Path(tempfile.mkdtemp(prefix="render-"))
        try:
            asset_paths = await self._download_assets(project_id, edl, scratch)
            output_path = scratch / f"output.{edl.output.container}"

            self._log.info("render.starting", job_id=str(job_id))
            result = await self._renderer.render(
                RenderInput(
                    edl=edl,
                    asset_paths=asset_paths,
                    output_path=output_path,
                )
            )

            output_key = self._build_output_key(project_id, job_id, result.container)
            with output_path.open("rb") as fh:
                stored = await self._object_store.put(
                    self._settings.s3_bucket_renders,
                    output_key,
                    fh,
                    content_type=f"video/{result.container}",
                )
            self._log.info(
                "render.uploaded",
                job_id=str(job_id),
                bucket=stored.bucket,
                key=stored.key,
            )
            return await self._render_jobs.mark_succeeded(
                job_id, output_bucket=stored.bucket, output_key=stored.key
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    async def _download_assets(
        self,
        project_id: UUID,
        edl: EditDecisionList,
        scratch: Path,
    ) -> dict[UUID, Path]:
        """Pull every asset referenced by the EDL onto local disk.

        Reads the bytes once and writes them to a single file per
        asset, even if the EDL references the same asset multiple
        times (which is common for "use the same clip twice" edits).
        """
        wanted: set[UUID] = {clip.clip.asset_id for track in edl.timeline for clip in track.clips}

        rows = await self._assets.list_for_project(project_id)
        by_id = {a.id: a for a in rows}

        paths: dict[UUID, Path] = {}
        for asset_id in wanted:
            row = by_id.get(asset_id)
            if row is None:
                raise NotFoundError(f"asset {asset_id} not in project {project_id}")
            data = await self._object_store.get(row.s3_bucket, row.s3_key)
            local_path = scratch / f"{asset_id}_{Path(row.filename).name}"
            local_path.write_bytes(data)
            paths[asset_id] = local_path
        return paths

    @staticmethod
    def _build_output_key(project_id: UUID, job_id: UUID, container: str) -> str:
        """Stable key under ``<project>/<job>.<ext>``.

        Project- and job-prefixed so renders for the same project are
        easy to find in the MinIO console, and never collide.
        """
        return f"{project_id}/{job_id}.{container}"


def _summarise(report: ValidationReport) -> str:
    if not report.issues:
        raise ValidationError("validation report has no issues")
    return "; ".join(
        f"{issue.code} ({issue.location or 'edl'}): {issue.message}" for issue in report.issues
    )
