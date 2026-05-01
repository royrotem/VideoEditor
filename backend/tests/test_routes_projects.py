"""HTTP-level tests for project and asset routes.

The DB session and object store are swapped for in-memory fakes via
FastAPI's ``dependency_overrides`` so the routes are tested without
docker-compose.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_asset_analysis_service,
    get_asset_repository,
    get_object_store,
    get_probe,
    get_project_repository,
)
from app.core.config import Settings
from app.main import create_app
from app.pipeline.probe import StubProbe
from app.services.analysis import AssetAnalysisService
from tests.fakes import FakeAssetRepository, FakeProjectRepository, InMemoryObjectStore


@pytest.fixture
def fakes() -> tuple[FakeProjectRepository, FakeAssetRepository, InMemoryObjectStore]:
    return FakeProjectRepository(), FakeAssetRepository(), InMemoryObjectStore()


@pytest.fixture
def app_client(
    fakes: tuple[FakeProjectRepository, FakeAssetRepository, InMemoryObjectStore],
) -> Iterator[TestClient]:
    projects, assets, store = fakes
    app = create_app(settings=Settings(environment="test"))

    app.dependency_overrides[get_project_repository] = lambda: projects
    app.dependency_overrides[get_asset_repository] = lambda: assets
    app.dependency_overrides[get_object_store] = lambda: store
    # Stub probe so tests do not invoke real ffprobe on placeholder bytes.
    stub_probe = StubProbe(duration_seconds=12.5, width=1920, height=1080, has_audio=True)
    app.dependency_overrides[get_probe] = lambda: stub_probe
    # Skip the vision pass in route-level tests by injecting a probe-only
    # AssetAnalysisService. Vision-path coverage lives in
    # tests/test_analysis_service.py.
    app.dependency_overrides[get_asset_analysis_service] = lambda: AssetAnalysisService(
        probe=stub_probe, object_store=store, assets=assets
    )

    with TestClient(app) as client:
        yield client


def test_create_and_fetch_project(app_client: TestClient) -> None:
    response = app_client.post(
        "/projects",
        json={"name": "Wedding edit", "description": "First cut for review"},
    )
    assert response.status_code == 201
    body = response.json()
    project_id = body["id"]
    assert body["name"] == "Wedding edit"

    fetched = app_client.get(f"/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == project_id


def test_upload_asset_returns_preview_url(app_client: TestClient) -> None:
    project_id = app_client.post("/projects", json={"name": "p", "description": None}).json()["id"]

    upload = app_client.post(
        f"/projects/{project_id}/assets",
        files={"file": ("clip.mp4", b"\x00\x01\x02\x03", "video/mp4")},
    )
    assert upload.status_code == 201
    body = upload.json()
    assert body["asset"]["filename"] == "clip.mp4"
    # Probe runs inline on upload, so the asset reports its post-analysis state.
    assert body["asset"]["status"] == "ready"
    assert body["preview_url"].startswith("http://fake-store.local/")
    assert body["preview_url_ttl_seconds"] > 0


def test_list_assets_after_upload(app_client: TestClient) -> None:
    project_id = app_client.post("/projects", json={"name": "p", "description": None}).json()["id"]
    app_client.post(
        f"/projects/{project_id}/assets",
        files={"file": ("a.mp4", b"abc", "video/mp4")},
    )
    app_client.post(
        f"/projects/{project_id}/assets",
        files={"file": ("b.mp4", b"def", "video/mp4")},
    )

    listed = app_client.get(f"/projects/{project_id}/assets")
    assert listed.status_code == 200
    filenames = {a["filename"] for a in listed.json()}
    assert filenames == {"a.mp4", "b.mp4"}


def test_get_missing_project_returns_404(app_client: TestClient) -> None:
    response = app_client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource.not_found"


def test_reanalyze_route_runs_probe_again(app_client: TestClient) -> None:
    project_id = app_client.post("/projects", json={"name": "p", "description": None}).json()["id"]
    asset_id = app_client.post(
        f"/projects/{project_id}/assets",
        files={"file": ("clip.mp4", b"abc", "video/mp4")},
    ).json()["asset"]["id"]

    response = app_client.post(f"/projects/{project_id}/assets/{asset_id}/analyze")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
