"""API schemas for the ``projects`` resource."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    """Body of ``POST /projects``."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4096)


class ProjectRead(BaseModel):
    """Representation of a project in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
