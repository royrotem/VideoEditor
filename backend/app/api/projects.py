"""HTTP routes for the ``projects`` resource."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import ProjectRepoDep
from app.schemas.projects import ProjectCreate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    projects: ProjectRepoDep,
) -> ProjectRead:
    project = await projects.create(name=body.name, description=body.description)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects(projects: ProjectRepoDep) -> list[ProjectRead]:
    rows = await projects.list_all()
    return [ProjectRead.model_validate(row) for row in rows]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: UUID, projects: ProjectRepoDep) -> ProjectRead:
    project = await projects.get(project_id)
    return ProjectRead.model_validate(project)
