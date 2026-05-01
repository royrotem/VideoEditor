"""HTTP-level test for the plan-edit route."""

from __future__ import annotations

import json
from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_asset_repository,
    get_llm_client,
    get_object_store,
    get_probe,
    get_project_repository,
)
from app.core.config import Settings
from app.db.enums import AssetStatus
from app.main import create_app
from app.pipeline.probe import StubProbe
from tests.fakes import (
    FakeAssetRepository,
    FakeProjectRepository,
    InMemoryObjectStore,
    ScriptedLLM,
    make_upload_buffer,
)


def _planner_reply(asset_id: UUID) -> str:
    return json.dumps(
        {
            "version": 1,
            "timeline": [
                {
                    "kind": "video",
                    "clips": [
                        {
                            "clip": {
                                "asset_id": str(asset_id),
                                "source_start_seconds": 0,
                                "source_end_seconds": 3,
                            },
                            "timeline_start_seconds": 0,
                            "transition_in": "fade",
                            "transition_out": "cut",
                        }
                    ],
                }
            ],
            "audio": {
                "music_url": None,
                "voice_over_asset_id": None,
                "duck_music_under_voice": True,
                "target_lufs": -14.0,
            },
            "subtitles": None,
            "color": None,
            "output": {
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "container": "mp4",
            },
        }
    )


@pytest.fixture
def deps():
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    return projects, assets, store


@pytest.fixture
def app_client(deps) -> Iterator[TestClient]:
    projects, assets, store = deps
    app = create_app(settings=Settings(environment="test"))
    llm_replies: list[str] = []
    llm = ScriptedLLM(llm_replies)

    app.dependency_overrides[get_project_repository] = lambda: projects
    app.dependency_overrides[get_asset_repository] = lambda: assets
    app.dependency_overrides[get_object_store] = lambda: store
    app.dependency_overrides[get_probe] = lambda: StubProbe()
    app.dependency_overrides[get_llm_client] = lambda: llm

    with TestClient(app) as client:
        # Expose the reply queue on the client for tests to mutate.
        client.llm_replies = llm_replies  # type: ignore[attr-defined]
        yield client


async def _seed_asset(deps, settings: Settings):
    projects, assets, store = deps
    project = await projects.create(name="p", description=None)
    asset = await assets.create(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=4,
        s3_bucket=settings.s3_bucket_assets,
        s3_key=f"{project.id}/x/clip.mp4",
        status=AssetStatus.READY,
        analysis={"duration_seconds": 30.0},
    )
    await store.put(
        asset.s3_bucket,
        asset.s3_key,
        make_upload_buffer(b"\x00\x01\x02\x03"),
        content_type="video/mp4",
    )
    return project, asset


def test_plan_edit_returns_edl_for_known_project_with_assets(app_client: TestClient, deps) -> None:
    import asyncio

    settings = Settings(environment="test")
    project, asset = asyncio.run(_seed_asset(deps, settings))
    app_client.llm_replies.append(_planner_reply(asset.id))  # type: ignore[attr-defined]

    response = app_client.post(
        f"/projects/{project.id}/plan-edit",
        json={
            "brief": {
                "title": "t",
                "intent": "i",
                "target_duration_seconds": 30,
                "style_notes": [],
                "music_direction": None,
                "pacing": "fast",
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert len(body["timeline"]) == 1


def test_plan_edit_404s_for_unknown_project(app_client: TestClient) -> None:
    response = app_client.post(
        "/projects/00000000-0000-0000-0000-000000000000/plan-edit",
        json={
            "brief": {
                "title": "t",
                "intent": "i",
                "target_duration_seconds": 30,
                "style_notes": [],
                "music_direction": None,
                "pacing": "medium",
            }
        },
    )
    assert response.status_code == 404


def test_plan_edit_422s_when_project_has_no_assets(app_client: TestClient, deps) -> None:
    import asyncio

    projects, _, _ = deps
    project = asyncio.run(projects.create(name="p", description=None))

    response = app_client.post(
        f"/projects/{project.id}/plan-edit",
        json={
            "brief": {
                "title": "t",
                "intent": "i",
                "target_duration_seconds": 30,
                "style_notes": [],
                "music_direction": None,
                "pacing": "medium",
            }
        },
    )

    assert response.status_code == 422
    assert "no analysed assets" in response.json()["error"]["message"]
