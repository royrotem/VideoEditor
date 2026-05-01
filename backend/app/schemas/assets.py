"""API schemas for the ``assets`` resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import AssetStatus


class AssetRead(BaseModel):
    """Representation of an asset in API responses.

    The raw bytes are not exposed - callers should request a presigned
    URL via ``GET /projects/{id}/assets/{asset_id}/url`` instead.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    filename: str
    content_type: str | None
    size_bytes: int | None
    status: AssetStatus
    created_at: datetime


class AssetCreated(BaseModel):
    """Returned right after a successful upload.

    Includes a short-lived presigned URL so the client can immediately
    preview the asset without an extra round trip.
    """

    asset: AssetRead
    preview_url: str
    preview_url_ttl_seconds: int
