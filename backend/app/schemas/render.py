"""API schemas for render jobs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.agents.contracts import EditDecisionList
from app.db.enums import JobStatus


class RenderJobRead(BaseModel):
    """Representation of a render job in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    edl_version_id: UUID
    status: JobStatus
    output_bucket: str | None
    output_key: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class SubmitRenderBody(BaseModel):
    """Body of ``POST /projects/{id}/render``.

    Carries the EDL the planner produced. The render service persists
    it as a new ``edl_versions`` row before kicking off rendering;
    the client need not pre-create the version itself.
    """

    edl: EditDecisionList
    session_id: UUID | None = None


class RenderOutputUrl(BaseModel):
    """Returned by the presigned-output endpoint."""

    url: str
    ttl_seconds: int
