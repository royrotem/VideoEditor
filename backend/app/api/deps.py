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
from app.pipeline.frame_extractor import FrameExtractor
from app.pipeline.probe import Probe
from app.pipeline.renderer import Renderer
from app.pipeline.transcriber import Transcriber
from app.repositories.assets import AssetRepository
from app.repositories.projects import ProjectRepository
from app.repositories.render_jobs import EdlVersionRepository, RenderJobRepository
from app.repositories.sessions import MessageRepository, SessionRepository
from app.services.analysis import AssetAnalysisService
from app.services.assets import AssetService
from app.services.chat import ChatService
from app.services.planning import PlanningService
from app.services.render import RenderJobService, TaskEnqueuer
from app.services.render_enqueuer import CeleryRenderEnqueuer
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


def get_renderer(request: Request) -> Renderer:
    renderer: Renderer = request.app.state.renderer
    return renderer


def get_frame_extractor(request: Request) -> FrameExtractor:
    extractor: FrameExtractor = request.app.state.frame_extractor
    return extractor


def get_transcriber(request: Request) -> Transcriber:
    """Return the process-wide :class:`Transcriber`.

    Production wires :class:`WhisperTranscriber`. The lifespan keeps
    a single instance so the (heavy) Whisper model is loaded at most
    once per process - the actual model load is itself lazy, on the
    first ``transcribe`` call.
    """
    transcriber: Transcriber = request.app.state.transcriber
    return transcriber


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
ObjectStoreDep = Annotated[ObjectStore, Depends(get_object_store)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
ProbeDep = Annotated[Probe, Depends(get_probe)]
RendererDep = Annotated[Renderer, Depends(get_renderer)]
FrameExtractorDep = Annotated[FrameExtractor, Depends(get_frame_extractor)]
TranscriberDep = Annotated[Transcriber, Depends(get_transcriber)]


def get_project_repository(session: SessionDep) -> ProjectRepository:
    return ProjectRepository(session)


def get_asset_repository(session: SessionDep) -> AssetRepository:
    return AssetRepository(session)


def get_session_repository(session: SessionDep) -> SessionRepository:
    return SessionRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


def get_edl_version_repository(session: SessionDep) -> EdlVersionRepository:
    return EdlVersionRepository(session)


def get_render_job_repository(session: SessionDep) -> RenderJobRepository:
    return RenderJobRepository(session)


ProjectRepoDep = Annotated[ProjectRepository, Depends(get_project_repository)]
AssetRepoDep = Annotated[AssetRepository, Depends(get_asset_repository)]
SessionRepoDep = Annotated[SessionRepository, Depends(get_session_repository)]
MessageRepoDep = Annotated[MessageRepository, Depends(get_message_repository)]
EdlVersionRepoDep = Annotated[EdlVersionRepository, Depends(get_edl_version_repository)]
RenderJobRepoDep = Annotated[RenderJobRepository, Depends(get_render_job_repository)]


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
    frame_extractor: FrameExtractorDep,
    llm: LLMClientDep,
    transcriber: TranscriberDep,
) -> AssetAnalysisService:
    return AssetAnalysisService(
        probe=probe,
        object_store=object_store,
        assets=assets,
        frame_extractor=frame_extractor,
        llm=llm,
        transcriber=transcriber,
    )


def get_render_enqueuer() -> TaskEnqueuer:
    """Production enqueuer.

    Always returns a :class:`CeleryRenderEnqueuer`. The caller's
    ``Settings.celery_eager`` decides whether the task runs in-process
    or is sent to the Redis broker - the API code path is identical.
    """
    return CeleryRenderEnqueuer()


RenderEnqueuerDep = Annotated[TaskEnqueuer, Depends(get_render_enqueuer)]


def get_render_service(
    settings: SettingsDep,
    renderer: RendererDep,
    object_store: ObjectStoreDep,
    projects: ProjectRepoDep,
    assets: AssetRepoDep,
    edl_versions: EdlVersionRepoDep,
    render_jobs: RenderJobRepoDep,
    enqueuer: RenderEnqueuerDep,
) -> RenderJobService:
    return RenderJobService(
        settings=settings,
        renderer=renderer,
        object_store=object_store,
        projects=projects,
        assets=assets,
        edl_versions=edl_versions,
        render_jobs=render_jobs,
        enqueuer=enqueuer,
    )


def get_planning_service(
    llm: LLMClientDep,
    projects: ProjectRepoDep,
    assets: AssetRepoDep,
) -> PlanningService:
    return PlanningService(llm=llm, projects=projects, assets=assets)


AssetServiceDep = Annotated[AssetService, Depends(get_asset_service)]
AssetAnalysisServiceDep = Annotated[AssetAnalysisService, Depends(get_asset_analysis_service)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
PlanningServiceDep = Annotated[PlanningService, Depends(get_planning_service)]
RenderServiceDep = Annotated[RenderJobService, Depends(get_render_service)]
