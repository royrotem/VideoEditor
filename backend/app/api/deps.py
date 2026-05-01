"""Shared FastAPI dependencies.

Builds the per-request stack that routes plug into: settings, object
store, repositories, services. Keeping the wiring in one place lets the
test suite override any layer with `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.services.assets import AssetService
from app.storage.base import ObjectStore


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_object_store(request: Request) -> ObjectStore:
    store: ObjectStore = request.app.state.object_store
    return store


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


def get_asset_repository(session: SessionDep) -> AssetRepository:
    return AssetRepository(session)


ProjectRepoDep = Annotated[ProjectRepository, Depends(get_project_repository)]
AssetRepoDep = Annotated[AssetRepository, Depends(get_asset_repository)]


def get_asset_service(
    settings: SettingsDep,
    object_store: ObjectStoreDep,
    projects: ProjectRepoDep,
    assets: AssetRepoDep,
) -> AssetService:
    return AssetService(
        settings=settings,
        object_store=object_store,
        projects=projects,
        assets=assets,
    )


AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
