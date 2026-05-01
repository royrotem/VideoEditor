"""HTTP routes for the ``assets`` resource (nested under projects)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Path, Query, UploadFile, status

from app.api.deps import AssetServiceDep
from app.schemas.assets import AssetCreated, AssetRead
from app.services.assets import DEFAULT_PREVIEW_TTL_SECONDS

router = APIRouter(prefix="/projects/{project_id}/assets", tags=["assets"])


@router.post("", response_model=AssetCreated, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    service: AssetServiceDep,
    project_id: UUID = Path(...),
    file: UploadFile = File(...),
) -> AssetCreated:
    """Upload a single file (video / audio / image) to a project."""
    asset = await service.upload(
        project_id=project_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        size_bytes=file.size,
        data=file.file,
    )
    preview_url = await service.presigned_preview_url(
        asset.id, ttl_seconds=DEFAULT_PREVIEW_TTL_SECONDS
    )
    return AssetCreated(
        asset=AssetRead.model_validate(asset),
        preview_url=preview_url,
        preview_url_ttl_seconds=DEFAULT_PREVIEW_TTL_SECONDS,
    )


@router.get("", response_model=list[AssetRead])
async def list_assets(
    service: AssetServiceDep,
    project_id: UUID = Path(...),
) -> list[AssetRead]:
    rows = await service.list_for_project(project_id)
    return [AssetRead.model_validate(row) for row in rows]


@router.get("/{asset_id}/url", response_model=dict[str, str | int])
async def presigned_asset_url(
    service: AssetServiceDep,
    project_id: UUID = Path(...),
    asset_id: UUID = Path(...),
    ttl_seconds: int = Query(default=DEFAULT_PREVIEW_TTL_SECONDS, ge=60, le=86_400),
) -> dict[str, str | int]:
    """Return a short-lived URL the client can fetch the bytes from."""
    url = await service.presigned_preview_url(asset_id, ttl_seconds=ttl_seconds)
    return {"url": url, "ttl_seconds": ttl_seconds}
