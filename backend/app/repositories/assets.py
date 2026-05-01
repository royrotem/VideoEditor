"""SQLAlchemy queries for the ``assets`` table."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AssetNotFoundError
from app.db.enums import AssetStatus
from app.db.models import Asset


class AssetRepository:
    """Data-access for :class:`~app.db.models.Asset`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
    ) -> Asset:
        asset = Asset(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            status=status,
            analysis=analysis,
        )
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def get(self, asset_id: UUID) -> Asset:
        asset = await self._session.get(Asset, asset_id)
        if asset is None:
            raise AssetNotFoundError(f"asset {asset_id} not found")
        return asset

    async def list_for_project(self, project_id: UUID) -> list[Asset]:
        result = await self._session.execute(
            select(Asset)
            .where(Asset.project_id == project_id)
            .order_by(Asset.created_at.desc())
        )
        return list(result.scalars())
