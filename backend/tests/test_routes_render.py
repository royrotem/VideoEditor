"""HTTP-level tests for the render API."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.agents.contracts import (
    AudioPlan,
    ClipReference,
    EditDecisionList,
    OutputSpec,
    TimelineClip,
    Track,
)
from app.api.deps import (
    get_asset_repository,
    get_edl_version_repository,
    get_object_store,
    get_probe,
    get_project_repository,
    get_render_job_repository,
    get_renderer,
)
from app.core.config import Settings
from app.db.enums import AssetStatus
from app.main import create_app
from app.pipeline.probe import StubProbe
from app.pipeline.renderer import RenderInput, RenderResult, Renderer

from tests.fakes import (
    FakeAssetRepository,
    FakeEdlVersionRepository,
    FakeProjectRepository,
    FakeRenderJobRepository,
    InMemoryObjectStore,
    make_upload_buffer,
)


class _CapturingRenderer(Renderer):
    async def render(self, payload: RenderInput) -> RenderResult:
        payload.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload.output_path.write_bytes(b"RENDERED")
        return RenderResult(
            output_path=payload.output_path,
            duration_seconds=2.0,
            container=payload.edl.output.container,
        )


@pytest.fixture
def fakes():
    return (
        FakeProjectRepository(),
        FakeAssetRepository(),
        FakeEdlVersionRepository(),
        FakeRenderJobRepository(),
        InMemoryObjectStore(),
        _CapturingRenderer(),
    )


@pytest.fixture
def app_client(fakes) -> Iterator[TestClient]:
    projects, assets, edl_versions, render_jobs, store, renderer = fakes
    app = create_app(settings=Settings(environment="test"))

    app.dependency_overrides[get_project_repository] = lambda: projects
    app.dependency_overrides[get_asset_repository] = lambda: assets
    app.dependency_overrides[get_edl_version_repository] = lambda: edl_versions
    app.dependency_overrides[get_render_job_repository] = lambda: render_jobs
    app.dependency_overrides[get_object_store] = lambda: store
    app.dependency_overrides[get_probe] = lambda: StubProbe(duration_seconds=30.0)
    app.dependency_overrides[get_renderer] = lambda: renderer

    with TestClient(app) as client:
        yield client


async def _seed_project_with_asset(
    settings: Settings,
    projects: FakeProjectRepository,
    assets: FakeAssetRepository,
    store: InMemoryObjectStore,
):
    project = await projects.create(name="p", description=None)
    asset = await assets.create(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=4,
        s3_bucket=settings.s3_bucket_assets,
        s3_key=f"{project.id}/{uuid4()}/clip.mp4",
        status=AssetStatus.READY,
        analysis={"duration_seconds": 30.0},
    )
    await store.put(
        asset.s3_bucket, asset.s3_key, make_upload_buffer(b"\x00\x01\x02\x03"),
        content_type="video/mp4",
    )
    return project, asset


def _edl_for_asset(asset_id, *, version: int = 1) -> dict:
    edl = EditDecisionList(
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
    return edl.model_dump(mode="json")


def test_submit_render_returns_succeeded_job(app_client: TestClient, fakes) -> None:
    settings = Settings(environment="test")
    projects, assets, _edl_versions, _render_jobs, store, _renderer = fakes
    import asyncio

    project, asset = asyncio.run(
        _seed_project_with_asset(settings, projects, assets, store)
    )

    response = app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(asset.id)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["output_bucket"] == settings.s3_bucket_renders
    assert body["output_key"].startswith(f"{project.id}/")


def test_submit_render_returns_failed_job_when_validation_fails(
    app_client: TestClient, fakes
) -> None:
    settings = Settings(environment="test")
    projects, assets, _edl_versions, _render_jobs, store, _renderer = fakes
    import asyncio

    project = asyncio.run(projects.create(name="p", description=None))
    # No asset uploaded — the EDL references an unknown asset.
    response = app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(uuid4())},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "failed"
    assert "asset_not_found" in (body["error_message"] or "")


def test_get_render_job_returns_known_job(app_client: TestClient, fakes) -> None:
    settings = Settings(environment="test")
    projects, assets, _edl_versions, _render_jobs, store, _renderer = fakes
    import asyncio

    project, asset = asyncio.run(
        _seed_project_with_asset(settings, projects, assets, store)
    )
    submitted = app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(asset.id)},
    ).json()

    response = app_client.get(f"/render-jobs/{submitted['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == submitted["id"]


def test_list_render_jobs_returns_jobs_for_project(
    app_client: TestClient, fakes
) -> None:
    settings = Settings(environment="test")
    projects, assets, _edl_versions, _render_jobs, store, _renderer = fakes
    import asyncio

    project, asset = asyncio.run(
        _seed_project_with_asset(settings, projects, assets, store)
    )
    app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(asset.id, version=1)},
    )
    app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(asset.id, version=2)},
    )

    response = app_client.get(f"/projects/{project.id}/render-jobs")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_output_url_returns_presigned_url_for_succeeded_job(
    app_client: TestClient, fakes
) -> None:
    settings = Settings(environment="test")
    projects, assets, _edl_versions, _render_jobs, store, _renderer = fakes
    import asyncio

    project, asset = asyncio.run(
        _seed_project_with_asset(settings, projects, assets, store)
    )
    submitted = app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(asset.id)},
    ).json()

    response = app_client.get(f"/render-jobs/{submitted['id']}/output-url")

    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("http://fake-store.local/")
    assert body["ttl_seconds"] == 3600


def test_output_url_404s_when_job_has_no_output(
    app_client: TestClient, fakes
) -> None:
    settings = Settings(environment="test")
    projects, _assets, _edl_versions, _render_jobs, _store, _renderer = fakes
    import asyncio

    project = asyncio.run(projects.create(name="p", description=None))
    failed_submitted = app_client.post(
        f"/projects/{project.id}/render",
        json={"edl": _edl_for_asset(uuid4())},  # validation will fail -> no output
    ).json()

    response = app_client.get(f"/render-jobs/{failed_submitted['id']}/output-url")

    assert response.status_code == 404


def test_submit_render_unknown_project_returns_404(app_client: TestClient) -> None:
    response = app_client.post(
        "/projects/00000000-0000-0000-0000-000000000000/render",
        json={"edl": _edl_for_asset(uuid4())},
    )
    assert response.status_code == 404
