"""Unit tests for :class:`app.services.analysis.AssetAnalysisService`."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import ExternalServiceError
from app.db.enums import AssetStatus
from app.pipeline.probe import Probe, ProbeResult, StubProbe
from app.services.analysis import AssetAnalysisService

from tests.fakes import (
    FakeAssetRepository,
    FakeProjectRepository,
    InMemoryObjectStore,
    make_upload_buffer,
)


class _FailingProbe(Probe):
    async def probe(self, path: Path) -> ProbeResult:
        raise ExternalServiceError("ffprobe blew up")


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


async def _seed_asset(
    *,
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
        status=AssetStatus.UPLOADED,
    )
    await store.put(
        asset.s3_bucket, asset.s3_key, make_upload_buffer(b"\x00\x01\x02\x03"),
        content_type="video/mp4",
    )
    return project, asset


async def test_analyze_writes_probe_facts_and_marks_ready(
    settings: Settings,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )
    service = AssetAnalysisService(
        probe=StubProbe(
            duration_seconds=12.5, width=1920, height=1080, has_audio=True
        ),
        object_store=store,
        assets=assets,
    )

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.READY
    assert updated.analysis is not None
    assert updated.analysis["duration_seconds"] == 12.5
    assert updated.analysis["width"] == 1920
    assert updated.analysis["height"] == 1080
    assert updated.analysis["has_audio"] is True


async def test_analyze_marks_failed_and_stores_error_when_probe_raises(
    settings: Settings,
) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )
    service = AssetAnalysisService(
        probe=_FailingProbe(), object_store=store, assets=assets
    )

    updated = await service.analyze(asset.id)

    assert updated.status is AssetStatus.FAILED
    assert updated.analysis is not None
    assert "ffprobe blew up" in updated.analysis["error"]


async def test_analyze_preserves_prior_analysis_keys(settings: Settings) -> None:
    projects = FakeProjectRepository()
    assets = FakeAssetRepository()
    store = InMemoryObjectStore()
    _, asset = await _seed_asset(
        settings=settings, projects=projects, assets=assets, store=store
    )
    asset.analysis = {"summary": "warm wedding ceremony", "shots": ["s1", "s2"]}

    service = AssetAnalysisService(
        probe=StubProbe(duration_seconds=30.0),
        object_store=store,
        assets=assets,
    )

    updated = await service.analyze(asset.id)

    assert updated.analysis is not None
    # Probe fields populated.
    assert updated.analysis["duration_seconds"] == 30.0
    # Prior keys retained.
    assert updated.analysis["summary"] == "warm wedding ceremony"
    assert updated.analysis["shots"] == ["s1", "s2"]


async def test_analyze_raises_when_asset_does_not_exist(
    settings: Settings,
) -> None:
    service = AssetAnalysisService(
        probe=StubProbe(),
        object_store=InMemoryObjectStore(),
        assets=FakeAssetRepository(),
    )

    with pytest.raises(Exception):
        await service.analyze(uuid4())
