"""Asset use cases: upload, list, presign.

Composes the :class:`AssetRepository`, :class:`ProjectRepository`, and
:class:`ObjectStore`. Routes call into this service so they stay free
of storage / database mechanics.
"""

from __future__ import annotations

from typing import BinaryIO
from uuid import UUID, uuid4

from app.core.config import Settings
from app.db.enums import AssetStatus
from app.db.models import Asset
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.storage.base import ObjectStore

DEFAULT_PREVIEW_TTL_SECONDS = 3600


class AssetService:
    """Coordinates uploads of user files into MinIO + Postgres."""

    def __init__(
        self,
        *,
        settings: Settings,
        object_store: ObjectStore,
        projects: ProjectRepository,
        assets: AssetRepository,
    ) -> None:
        self._settings = settings
        self._object_store = object_store
        self._projects = projects
        self._assets = assets

    async def upload(
        self,
        *,
        project_id: UUID,
        filename: str,
        content_type: str | None,
        size_bytes: int | None,
        data: BinaryIO,
    ) -> Asset:
        """Upload ``data`` into MinIO and record the asset in Postgres.

        The project is fetched first so the call fails fast (with a 404)
        when the caller references a missing project.
        """
        await self._projects.get(project_id)

        bucket = self._settings.s3_bucket_assets
        key = self._build_object_key(project_id, filename)

        stored = await self._object_store.put(
            bucket, key, data, content_type=content_type
        )

        return await self._assets.create(
            project_id=project_id,
            filename=filename,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes if stored.size_bytes is not None else size_bytes,
            s3_bucket=bucket,
            s3_key=key,
            status=AssetStatus.UPLOADED,
        )

    async def list_for_project(self, project_id: UUID) -> list[Asset]:
        await self._projects.get(project_id)
        return await self._assets.list_for_project(project_id)

    async def presigned_preview_url(
        self,
        asset_id: UUID,
        *,
        ttl_seconds: int = DEFAULT_PREVIEW_TTL_SECONDS,
    ) -> str:
        asset = await self._assets.get(asset_id)
        return await self._object_store.presigned_get_url(
            asset.s3_bucket, asset.s3_key, ttl_seconds=ttl_seconds
        )

    @staticmethod
    def _build_object_key(project_id: UUID, filename: str) -> str:
        """Stable key under ``<project>/<uuid>/<filename>``.

        Storing the original filename keeps inspection in the MinIO
        console human-readable; the per-upload UUID guarantees we never
        collide on duplicate filenames.
        """
        return f"{project_id}/{uuid4()}/{filename}"
