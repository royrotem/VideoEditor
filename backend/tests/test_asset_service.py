"""Unit tests for :class:`app.services.assets.AssetService`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.enums import AssetStatus
from app.services.assets import AssetService
from tests.fakes import (
    FakeAssetRepository,
    FakeProjectRepository,
    InMemoryObjectStore,
    make_upload_buffer,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test")


@pytest.fixture
def projects() -> FakeProjectRepository:
    return FakeProjectRepository()


@pytest.fixture
def assets() -> FakeAssetRepository:
    return FakeAssetRepository()


@pytest.fixture
def store() -> InMemoryObjectStore:
    return InMemoryObjectStore()


@pytest.fixture
def service(
    settings: Settings,
    projects: FakeProjectRepository,
    assets: FakeAssetRepository,
    store: InMemoryObjectStore,
) -> AssetService:
    return AssetService(settings=settings, object_store=store, projects=projects, assets=assets)


async def test_upload_writes_to_store_and_db(
    service: AssetService,
    projects: FakeProjectRepository,
    store: InMemoryObjectStore,
    settings: Settings,
) -> None:
    project = await projects.create(name="demo", description=None)
    payload = b"\x00\x01\x02\x03"

    asset = await service.upload(
        project_id=project.id,
        filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=len(payload),
        data=make_upload_buffer(payload),
    )

    assert asset.project_id == project.id
    assert asset.filename == "clip.mp4"
    assert asset.size_bytes == len(payload)
    assert asset.status == AssetStatus.UPLOADED
    assert asset.s3_bucket == settings.s3_bucket_assets
    assert await store.exists(asset.s3_bucket, asset.s3_key)
    assert await store.get(asset.s3_bucket, asset.s3_key) == payload


async def test_upload_rejects_missing_project(service: AssetService) -> None:
    with pytest.raises(NotFoundError):
        await service.upload(
            project_id=uuid4(),
            filename="clip.mp4",
            content_type="video/mp4",
            size_bytes=4,
            data=make_upload_buffer(b"\x00\x01\x02\x03"),
        )


async def test_list_for_project_returns_uploaded_assets(
    service: AssetService, projects: FakeProjectRepository
) -> None:
    project = await projects.create(name="demo", description=None)
    await service.upload(
        project_id=project.id,
        filename="a.mp4",
        content_type="video/mp4",
        size_bytes=1,
        data=make_upload_buffer(b"a"),
    )
    await service.upload(
        project_id=project.id,
        filename="b.mp4",
        content_type="video/mp4",
        size_bytes=1,
        data=make_upload_buffer(b"b"),
    )

    listed = await service.list_for_project(project.id)
    assert {a.filename for a in listed} == {"a.mp4", "b.mp4"}


async def test_presigned_url_returns_a_string(
    service: AssetService, projects: FakeProjectRepository
) -> None:
    project = await projects.create(name="demo", description=None)
    asset = await service.upload(
        project_id=project.id,
        filename="a.mp4",
        content_type="video/mp4",
        size_bytes=1,
        data=make_upload_buffer(b"a"),
    )

    url = await service.presigned_preview_url(asset.id, ttl_seconds=600)
    assert url.startswith("http://fake-store.local/")
    assert "ttl=600" in url
