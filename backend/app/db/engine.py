"""SQLAlchemy async engine + session factory.

Application code should depend on the session factory (a callable that
yields an :class:`AsyncSession`) rather than on the engine directly. This
keeps tests free to inject in-memory or container-backed databases.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.core.errors import ExternalServiceError


def create_engine_and_sessionmaker(
    settings: Settings,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an :class:`AsyncEngine` and matching session factory.

    Both objects are tied to the process; call :func:`dispose_engine` at
    shutdown to release pooled connections.
    """
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sessionmaker


async def dispose_engine(engine: AsyncEngine) -> None:
    """Release every pooled connection."""
    await engine.dispose()


async def health_check(engine: AsyncEngine) -> None:
    """Run a trivial query to verify the database is reachable."""
    from sqlalchemy import text  # local import keeps module import cheap

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise ExternalServiceError(f"database unreachable: {exc}") from exc
