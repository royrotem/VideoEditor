"""HTTP route for turning a BriefPlan into an EditDecisionList.

Bridges chat (which yields a BriefPlan) and the render pipeline (which
consumes an EDL). The frontend posts the brief, the backend asks the
Editing Planner to compose a plan against the project's analysed
assets, and the EDL comes back unchanged for the caller to ferry to
``POST /projects/{id}/render``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Path, status
from pydantic import BaseModel

from app.agents.contracts import BriefPlan, EditDecisionList
from app.api.deps import PlanningServiceDep

router = APIRouter(tags=["planning"])


class PlanEditBody(BaseModel):
    """Body of ``POST /projects/{id}/plan-edit``."""

    brief: BriefPlan
    previous_edl: EditDecisionList | None = None


@router.post(
    "/projects/{project_id}/plan-edit",
    response_model=EditDecisionList,
    status_code=status.HTTP_200_OK,
)
async def plan_edit(
    body: PlanEditBody,
    service: PlanningServiceDep,
    project_id: UUID = Path(...),
) -> EditDecisionList:
    """Plan an EDL for ``project_id`` using the supplied brief."""
    return await service.plan(
        project_id=project_id,
        brief=body.brief,
        previous_edl=body.previous_edl,
    )
