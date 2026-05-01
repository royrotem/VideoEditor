"""FastAPI application entry point.

Wires together configuration, logging, infrastructure clients, error
handlers, and the API routers. Run with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.engine import create_engine_and_sessionmaker, dispose_engine
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

    app.state.db_engine = engine
    app.state.db_sessionmaker = session_factory
    app.state.redis = redis_client
    app.state.object_store = object_store

    try:
        yield
    finally:
        log.info("backend.stopping")
        await redis_client.aclose()
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

    return app


app = create_app()
