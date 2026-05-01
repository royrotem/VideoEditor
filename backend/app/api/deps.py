"""Shared FastAPI dependencies.

Builds the per-request stack that routes plug into: settings, object
store, repositories, services. Keeping the wiring in one place lets the
test suite override any layer with `app.dependency_overrides`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.client import LLMClient
from app.core.config import Settings
from app.db.session import get_db_session
from app.pipeline.probe import Probe
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.sessions import MessageRepository, SessionRepository
from app.services.analysis import AssetAnalysisService
from app.services.assets import AssetService
from app.services.chat import ChatService
from app.storage.base import ObjectStore


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_object_store(request: Request) -> ObjectStore:
    store: ObjectStore = request.app.state.object_store
    return store


def get_llm_client(request: Request) -> LLMClient:
    llm: LLMClient = request.app.state.llm_client
    return llm


def get_probe(request: Request) -> Probe:
    probe: Probe = request.app.state.probe
    return probe


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
ProbeDep = Annotated[Probe, Depends(get_probe)]


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


def get_asset_repository(session: SessionDep) -> AssetRepository:
    return AssetRepository(session)


def get_session_repository(session: SessionDep) -> SessionRepository:
    return SessionRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


ProjectRepoDep = Annotated[ProjectRepository, Depends(get_project_repository)]
AssetRepoDep = Annotated[AssetRepository, Depends(get_asset_repository)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repository)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]


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


def get_chat_service(
    llm: LLMClientDep,
    projects: ProjectRepoDep,
    assets: AssetRepoDep,
    sessions: SessionRepoDep,
    messages: MessageRepoDep,
) -> ChatService:
    return ChatService(
        llm=llm,
        projects=projects,
        assets=assets,
        sessions=sessions,
        messages=messages,
    )


def get_asset_analysis_service(
    probe: ProbeDep,
    object_store: ObjectStoreDep,
    assets: AssetRepoDep,
) -> AssetAnalysisService:
    return AssetAnalysisService(
        probe=probe, object_store=object_store, assets=assets
    )


AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
AssetAnalysisServiceDep = Annotated[
    AssetAnalysisService, Depends(get_asset_analysis_service)
]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
