"""SQLAlchemy queries for the ``projects`` table."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.models import Project


class ProjectRepository:
    """Data-access for :class:`~app.db.models.Project`.

    The repository never commits - the surrounding request transaction
    (see :func:`app.db.session.get_db_session`) decides the outcome.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, description: str | None) -> Project:
        project = Project(name=name, description=description)
        self._session.add(project)
        await self._session.flush()
        return project

    async def get(self, project_id: UUID) -> Project:
        project = await self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    async def list_all(self) -> list[Project]:
        result = await self._session.execute(
            select(Project).order_by(Project.created_at.desc())
        )
        return list(result.scalars())
