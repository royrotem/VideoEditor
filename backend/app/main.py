"""FastAPI application entry point.

Wires together configuration, logging, infrastructure clients, error
handlers, and the API routers. Run with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anthropic import AsyncAnthropic
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Side-effect import: registers every concrete agent on the global
# registry. Aliased so the local ``app`` variable below (the FastAPI
# instance) does not shadow the package and confuse type checkers.
from app import agents as _agents_pkg  # noqa: F401
from app.agents.client import AnthropicLLMClient
from app.api.assets import router as assets_router
from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.planning import router as planning_router
from app.api.projects import router as projects_router
from app.api.render import router as render_router
from app.api.sessions import router as sessions_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.engine import create_engine_and_sessionmaker, dispose_engine
from app.pipeline.frame_extractor import FFmpegFrameExtractor
from app.pipeline.probe import FFprobeProbe
from app.pipeline.renderer import FFmpegRenderer
from app.pipeline.transcriber import WhisperTranscriber
from app.queue.redis_client import create_redis_client
from app.storage.s3 import S3ObjectStore


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Build infrastructure clients on startup, dispose them on shutdown.

    Clients are stored on ``app.state`` so route handlers and the
    readiness check can pull them out via dependency injection helpers.
    """
    settings: Settings = app.state.settings
    log = get_logger("startup")
    log.info("backend.starting", environment=settings.environment)

    engine, session_factory = create_engine_and_sessionmaker(settings)
    redis_client = create_redis_client(settings)
    object_store = S3ObjectStore(settings)
    # Anthropic SDK requires a non-empty key at construction time. In dev
    # / test environments where no key is set, we still want the app to
    # start (so health, projects, assets keep working) - chat routes
    # will fail with a clear error only if they are actually called.
    anthropic_client = AsyncAnthropic(
        api_key=settings.anthropic_api_key or "missing-anthropic-api-key"
    )
    llm_client = AnthropicLLMClient(anthropic_client)

    app.state.db_engine = engine
    app.state.db_sessionmaker = session_factory
    app.state.redis = redis_client
    app.state.object_store = object_store
    app.state.anthropic_client = anthropic_client
    app.state.llm_client = llm_client
    app.state.probe = FFprobeProbe()
    app.state.frame_extractor = FFmpegFrameExtractor()
    app.state.transcriber = WhisperTranscriber()
    app.state.renderer = FFmpegRenderer()

    try:
        yield
    finally:
        log.info("backend.stopping")
        await redis_client.aclose()
        await anthropic_client.close()
        await dispose_engine(engine)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a configured FastAPI application.

    Exposed as a factory so that tests can pass a custom :class:`Settings`
    instance without mutating the cached one.
    """
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="AI Video Editor",
        version="0.1.0",
        lifespan=_lifespan,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(assets_router)
    app.include_router(sessions_router)
    app.include_router(planning_router)
    app.include_router(render_router)

    return app


app = create_app()
