"""Lightweight in-memory fakes used by the unit-test suite.

Lets routes and services exercise the same code paths without booting
docker-compose. End-to-end coverage against real Postgres and MinIO
lives under ``tests/integration/``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from app.core.errors import AssetNotFoundError, ExternalServiceError, NotFoundError
from app.db.enums import AssetStatus
from app.storage.base import ObjectStore, StoredObject


class FakeProject:
    def __init__(self, *, name: str, description: str | None) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.name = name
        self.description = description
        self.created_at = now
        self.updated_at = now


class FakeAsset:
    def __init__(
        self,
        *,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
        s3_bucket: str,
        s3_key: str,
        status: AssetStatus,
    ) -> None:
        now = datetime.now(UTC)
        self.id: UUID = uuid4()
        self.project_id = project_id
        self.filename = filename
        self.content_type = content_type
        self.size_bytes = size_bytes
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.status = status
        self.analysis: dict[str, Any] | None = None
        self.created_at = now
        self.updated_at = now


class FakeProjectRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeProject] = {}

    async def create(self, *, name: str, description: str | None) -> FakeProject:
        project = FakeProject(name=name, description=description)
        self._rows[project.id] = project
        return project

    async def get(self, project_id: UUID) -> FakeProject:
        project = self._rows.get(project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    async def list_all(self) -> list[FakeProject]:
        return sorted(self._rows.values(), key=lambda p: p.created_at, reverse=True)


class FakeAssetRepository:
    def __init__(self) -> None:
        self._rows: dict[UUID, FakeAsset] = {}

    async def create(
        self,
        *,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
        s3_bucket: str,
        s3_key: str,
        status: AssetStatus = AssetStatus.UPLOADED,
        analysis: dict[str, Any] | None = None,
    ) -> FakeAsset:
        asset = FakeAsset(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            status=status,
        )
        asset.analysis = analysis
        self._rows[asset.id] = asset
        return asset

    async def get(self, asset_id: UUID) -> FakeAsset:
        asset = self._rows.get(asset_id)
        if asset is None:
            raise AssetNotFoundError(f"asset {asset_id} not found")
        return asset

    async def list_for_project(self, project_id: UUID) -> list[FakeAsset]:
        return sorted(
            (a for a in self._rows.values() if a.project_id == project_id),
            key=lambda a: a.created_at,
            reverse=True,
        )


class InMemoryObjectStore(ObjectStore):
    """An ``ObjectStore`` that keeps bytes in a dict.

    Sufficient for unit tests that exercise the upload pipeline end to
    end without booting MinIO.
    """

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._content_types: dict[tuple[str, str], str | None] = {}

    async def put(
        self,
        bucket: str,
        key: str,
        data: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        body = data.read()
        self._objects[(bucket, key)] = body
        self._content_types[(bucket, key)] = content_type
        return StoredObject(
            bucket=bucket, key=key, size_bytes=len(body), content_type=content_type
        )

    async def get(self, bucket: str, key: str) -> bytes:
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise ExternalServiceError(f"missing s3://{bucket}/{key}") from exc

    async def delete(self, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)
        self._content_types.pop((bucket, key), None)

    async def exists(self, bucket: str, key: str) -> bool:
        return (bucket, key) in self._objects

    async def presigned_get_url(self, bucket: str, key: str, *, ttl_seconds: int) -> str:
        if (bucket, key) not in self._objects:
            raise ExternalServiceError(f"missing s3://{bucket}/{key}")
        return f"http://fake-store.local/{bucket}/{key}?ttl={ttl_seconds}"

    async def health_check(self) -> None:
        return None


def make_upload_buffer(payload: bytes) -> BinaryIO:
    """Build a ``BinaryIO`` that mimics ``UploadFile.file`` for tests."""
    return BytesIO(payload)
