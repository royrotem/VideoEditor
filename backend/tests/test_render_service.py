"""End-to-end tests for :class:`app.services.render.RenderJobService`.

Uses fakes for repositories, the object store, and the renderer so
the full flow runs without ``ffmpeg`` or docker-compose.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.contracts import (
    AudioPlan,
    ClipReference,
    EditDecisionList,
    OutputSpec,
    TimelineClip,
    Track,
)
from app.core.config import Settings
from app.core.errors import ExternalServiceError, NotFoundError
from app.db.enums import AssetStatus, JobStatus
from app.pipeline.renderer import RenderInput, RenderResult, Renderer
from app.services.render import RenderJobService

from tests.fakes import (
    FakeAssetRepository,
    FakeEdlVersionRepository,
    FakeProjectRepository,
    FakeRenderJobRepository,
    InMemoryObjectStore,
    make_upload_buffer,
)


class _CapturingRenderer(Renderer):
    """Records the RenderInput it received and writes a fake output."""

    def __init__(self, *, body: bytes = b"RENDERED") -> None:
        self.body = body
        self.last_payload: RenderInput | None = None

    async def render(self, payload: RenderInput) -> RenderResult:
        self.last_payload = payload
        payload.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload.output_path.write_bytes(self.body)
        return RenderResult(
            output_path=payload.output_path,
            duration_seconds=2.0,
            container=payload.edl.output.container,
        )


class _FailingRenderer(Renderer):
    async def render(self, payload: RenderInput) -> RenderResult:
        raise ExternalServiceError("ffmpeg blew up")


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


async def _seed_project_with_asset(
    *,
    settings: Settings,
    projects: FakeProjectRepository,
    assets: FakeAssetRepository,
    store: InMemoryObjectStore,
    duration_seconds: float = 30.0,
    payload: bytes = b"\x00" * 16,
):
    project = await projects.create(name="p", description=None)
    asset = await assets.create(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=len(payload),
        s3_bucket=settings.s3_bucket_assets,
        s3_key=f"{project.id}/{uuid4()}/clip.mp4",
        status=AssetStatus.UPLOADED,
        analysis={"duration_seconds": duration_seconds},
    )
    await store.put(
        asset.s3_bucket, asset.s3_key, make_upload_buffer(payload), content_type="video/mp4"
    )
    return project, asset


def _edl_for_asset(asset_id, *, version: int = 1) -> EditDecisionList:
    return EditDecisionList(
        version=version,
        timeline=[
            Track(
                kind="video",
                clips=[
                    TimelineClip(
                        clip=ClipReference(
                            asset_id=asset_id,
                            source_start_seconds=0,
                            source_end_seconds=2,
                        ),
                        timeline_start_seconds=0,
                    )
                ],
            )
        ],
        audio=AudioPlan(),
        output=OutputSpec(),
    )


@pytest.fixture
def deps(settings: Settings):
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    edl_versions = FakeEdlVersionRepository()
    render_jobs = FakeRenderJobRepository()
    store = InMemoryObjectStore()
    renderer = _CapturingRenderer()
    service = RenderJobService(
        settings=settings,
        renderer=renderer,
        object_store=store,
        projects=projects,
        assets=assets,
        edl_versions=edl_versions,
        render_jobs=render_jobs,
    )
    return service, renderer, projects, assets, edl_versions, render_jobs, store


async def test_submit_succeeds_and_uploads_render(
    settings: Settings, deps
) -> None:
    service, renderer, projects, assets, edl_versions, _jobs, store = deps
    project, asset = await _seed_project_with_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )
    edl = _edl_for_asset(asset.id)

    job = await service.submit(project_id=project.id, edl=edl)

    assert job.status is JobStatus.SUCCEEDED
    assert job.error_message is None
    assert job.output_bucket == settings.s3_bucket_renders
    assert job.output_key.startswith(f"{project.id}/")  # <project>/<job>.mp4
    assert await store.exists(job.output_bucket, job.output_key)
    assert (await store.get(job.output_bucket, job.output_key)) == b"RENDERED"

    # An EDL version was persisted with version 1.
    latest = await edl_versions.latest_for_project(project.id)
    assert latest is not None
    assert latest.version_number == 1
    # The renderer received local paths it could read.
    payload = renderer.last_payload
    assert payload is not None
    assert asset.id in payload.asset_paths
    assert payload.asset_paths[asset.id].exists() is False  # scratch dir cleaned up


async def test_submit_fails_validation_when_clip_past_asset_duration(
    settings: Settings, deps
) -> None:
    service, _renderer, projects, assets, _edl_versions, _jobs, store = deps
    project, asset = await _seed_project_with_asset(
        settings=settings,
        projects=projects,
        assets=assets,
        store=store,
        duration_seconds=1.0,  # asset only 1s long
    )
    edl = _edl_for_asset(asset.id)  # references 0..2s

    job = await service.submit(project_id=project.id, edl=edl)

    assert job.status is JobStatus.FAILED
    assert "source_end_past_asset_duration" in (job.error_message or "")
    assert job.output_key is None


async def test_submit_marks_job_failed_when_renderer_raises(
    settings: Settings,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    edl_versions = FakeEdlVersionRepository()
    render_jobs = FakeRenderJobRepository()
    store = InMemoryObjectStore()
    service = RenderJobService(
        settings=settings,
        renderer=_FailingRenderer(),
        object_store=store,
        projects=projects,
        assets=assets,
        edl_versions=edl_versions,
        render_jobs=render_jobs,
    )
    project, asset = await _seed_project_with_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )
    edl = _edl_for_asset(asset.id)

    job = await service.submit(project_id=project.id, edl=edl)

    assert job.status is JobStatus.FAILED
    assert "ffmpeg blew up" in (job.error_message or "")


async def test_subsequent_submits_increment_edl_version(
    settings: Settings, deps
) -> None:
    service, _renderer, projects, assets, edl_versions, _jobs, store = deps
    project, asset = await _seed_project_with_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )

    await service.submit(project_id=project.id, edl=_edl_for_asset(asset.id, version=1))
    await service.submit(project_id=project.id, edl=_edl_for_asset(asset.id, version=2))

    latest = await edl_versions.latest_for_project(project.id)
    assert latest is not None
    assert latest.version_number == 2


async def test_submit_rejects_unknown_project(settings: Settings, deps) -> None:
    service, *_ = deps
    edl = _edl_for_asset(uuid4())

    with pytest.raises(NotFoundError):
        await service.submit(project_id=uuid4(), edl=edl)
